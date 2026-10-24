"""Backend-only durable SIP provisioning and SMTP notices for hosted applications.

Call enqueue only after the application's verified, committed registration.
Never pass this configuration or token to a browser.
"""
import argparse
from email.message import EmailMessage
import json
import os
from pathlib import Path
import smtplib
import sqlite3
import ssl
import time
import urllib.request
import urllib.error


def connect(path):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    # Set permissions before SQLite can populate a newly created file.
    fd=os.open(p,os.O_CREAT|os.O_RDWR,0o600);os.close(fd)
    db=sqlite3.connect(p,timeout=30);db.row_factory=sqlite3.Row
    db.execute('''CREATE TABLE IF NOT EXISTS registrations(subject TEXT PRIMARY KEY,
      identity TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'queued',attempts INTEGER NOT NULL DEFAULT 0,
      next_attempt INTEGER NOT NULL DEFAULT 0,result TEXT,notice_sent INTEGER NOT NULL DEFAULT 0)''')
    return db


def enqueue(database, *, subject, email, name, account_type, email_verified, organization_id=None):
    if email_verified is not True:raise ValueError('Email must be verified by the application first')
    if account_type not in ('individual','business','court','organization'):raise ValueError('Unsupported account type')
    if account_type!='individual' and not organization_id:raise ValueError('Stable organization ID required')
    body={'subject':str(subject),'email':email,'name':name,'accountType':account_type,
          'emailVerified':True,'organizationId':organization_id}
    payload=json.dumps(body,sort_keys=True)
    with connect(database) as db:
        prior=db.execute('SELECT identity FROM registrations WHERE subject=?',(str(subject),)).fetchone()
        if prior and prior['identity']!=payload:raise ValueError('Identity change requires review')
        db.execute('INSERT OR IGNORE INTO registrations(subject,identity) VALUES(?,?)',(str(subject),payload))
    return status(database,str(subject))


def status(database, subject):
    with connect(database) as db:
        row=db.execute('SELECT state,result FROM registrations WHERE subject=?',(str(subject),)).fetchone()
    if not row:return {'state':'not_requested','portal':'https://sip.dobhrap.com/'}
    return {'state':row['state'],'phone':json.loads(row['result']) if row['result'] else None,
            'portal':'https://sip.dobhrap.com/'}


def send_notice(config,identity):
    smtp=config.get('smtp')
    if not smtp:return False
    if smtp.get('port',587) not in (465,587):raise ValueError('TLS SMTP port required')
    message=EmailMessage();message['From']=smtp['from'];message['To']=identity['email']
    message['Subject']='Your phone services workspace'
    message.set_content('Your phone services workspace has been created. Open https://sip.dobhrap.com/ and use password recovery to set your separate phone password. Business and court accounts have a PBX workspace. Switch readiness and paid calling permissions are managed separately.')
    context=ssl.create_default_context()
    if smtp.get('port',587)==465:
        client=smtplib.SMTP_SSL(smtp['host'],465,timeout=20,context=context)
    else:
        client=smtplib.SMTP(smtp['host'],587,timeout=20);client.starttls(context=context)
    with client:
        client.login(smtp['username'],smtp['password']);client.send_message(message)
    return True


def run(config):
    token=config['token'];app=config['app_id']
    if len(token)<32:raise ValueError('Application token is not configured')
    # Endpoint is fixed, preventing caller-supplied URLs from receiving credentials.
    with connect(config['database']) as db:
        # Serialize deliveries across workers. No account passwords are transmitted.
        db.execute('BEGIN IMMEDIATE')
        rows=db.execute("SELECT * FROM registrations WHERE state IN ('queued','retry','notice_retry') AND next_attempt<=? LIMIT 10",(int(time.time()),)).fetchall()
        for row in rows:
            identity=json.loads(row['identity']);result=row['result']
            try:
                if not result:
                    request=urllib.request.Request('https://sip.dobhrap.com/api/integrations/hosted-apps/provision',
                        data=row['identity'].encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+token,'X-Hosted-App':app},method='POST')
                    # Refuse redirects so the bearer credential cannot leave its origin.
                    class NoRedirect(urllib.request.HTTPRedirectHandler):
                        def redirect_request(self,*args,**kwargs):return None
                    with urllib.request.build_opener(NoRedirect).open(request,timeout=25) as response:
                        result=json.dumps(json.load(response))
                    db.execute('UPDATE registrations SET result=? WHERE subject=?',(result,row['subject']))
                sent=bool(row['notice_sent']) or send_notice(config,identity)
                db.execute("UPDATE registrations SET state='provisioned',notice_sent=? WHERE subject=?",(int(sent),row['subject']))
            except urllib.error.HTTPError as e:
                state='needs_review' if e.code in (400,403,409) else 'retry'
                db.execute('UPDATE registrations SET state=?,attempts=attempts+1,next_attempt=? WHERE subject=?',
                           (state,int(time.time())+min(3600,30*2**min(row['attempts'],7)),row['subject']))
            except (OSError,ValueError,smtplib.SMTPException):
                db.execute('UPDATE registrations SET state=?,attempts=attempts+1,next_attempt=? WHERE subject=?',
                           ('notice_retry' if result else 'retry',int(time.time())+min(3600,30*2**min(row['attempts'],7)),row['subject']))
        db.commit()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);args=parser.parse_args()
    run(json.loads(Path(args.config).read_text()))
