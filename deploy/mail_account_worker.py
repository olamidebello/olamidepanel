"""Root-only mailbox policy broker. Never run the web service as root."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'panel'))
from database import connect, initialize_schema
from mail_accounts import validate_address, hash_password, permitted_domains
from mail_bootstrap import atomic_json

POLICY = Path('/etc/olamidepanel/mail-policy.json')


def apply_requests(policy, jobs, authorize):
    accounts = {a['address']: a for a in policy.get('mail_accounts', [])}
    accepted, denied = [], []
    for job in jobs:
        try:
            domain = validate_address(job['address'])
            if not authorize(job, domain):
                denied.append(job['id']); continue
            if job['operation'] == 'upsert':
                import re
                if not re.fullmatch(r'\{SHA512-CRYPT\}\$6\$[./a-zA-Z0-9$]+', job['password_hash']):
                    raise ValueError('Invalid password hash')
                if job['address'] not in accounts and sum(a.endswith('@'+domain) for a in accounts) >= 100:
                    denied.append(job['id']); continue
                accounts[job['address']] = {'address':job['address'], 'password_hash':job['password_hash']}
            elif job['operation'] == 'disable':
                accounts.pop(job['address'], None)
            else:
                raise ValueError('Invalid operation')
            accepted.append(job['id'])
        except (ValueError, KeyError, TypeError):
            denied.append(job['id'])
    return {**policy, 'mail_accounts':list(accounts.values())}, accepted, denied


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--approve', nargs=2, metavar=('DOMAIN','PANEL_USERNAME'))
    p.add_argument('--bootstrap-support', action='store_true')
    args=p.parse_args()
    if os.geteuid()!=0: p.error('Run locally as root')
    with open('/run/lock/olamidepanel-mail.lock','w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        initialize_schema()
        policy=json.loads(POLICY.read_text())
        if args.approve:
            domain,username=args.approve
            validate_address('support@'+domain)
            if domain not in policy.get('mail_extra_domains',[])+policy.get('mail_domains',[]):
                # An inventory entry must also be an active, operator-reviewed mail domain.
                raise ValueError('Add this verified domain to mail_extra_domains in the root mail policy first')
            with connect() as con:
                user=con.execute('SELECT id,role,active FROM users WHERE username=?',(username,)).fetchone()
                if not user or not user['active']: raise ValueError('Active panel account required')
                if args.bootstrap_support and user['role'] not in ('root','super_admin'):
                    raise ValueError('Support bootstrap requires a panel root or super-admin account')
                old=con.execute('SELECT owner FROM mail_delegations WHERE domain=?',(domain,)).fetchone()
                if old and old['owner']!=user['id']: raise ValueError('Existing delegation requires manual mailbox transfer review')
                if user['role'] not in ('root','super_admin'):
                    owned=con.execute('SELECT id FROM domains WHERE name=? AND owner=?',(domain,user['id'])).fetchone()
                    if not owned: raise ValueError('Domain inventory must belong to this panel account')
                con.execute('INSERT INTO mail_delegations(domain,owner) VALUES(?,?) ON DUPLICATE KEY UPDATE owner=VALUES(owner)',(domain,user['id']))
            if not args.bootstrap_support: return
        if args.bootstrap_support:
            if not args.approve or args.approve[0]!='afribulkhub.com':
                raise ValueError('Bootstrap requires --approve afribulkhub.com OPERATOR_USERNAME')
            address='support@afribulkhub.com'
            if not any(a['address']==address for a in policy.get('mail_accounts',[])):
                credentials=Path('/etc/olamidepanel/afribulkhub-support-credentials.json')
                if credentials.exists():
                    saved=json.loads(credentials.read_text());password=saved['password']
                else:
                    password=secrets.token_urlsafe(24)
                    atomic_json(credentials,{'address':address,'password':password,'hostname':policy['mail_hostname'],'imap_port':993,'smtp_starttls_port':587})
                with connect() as con:
                    pending=con.execute("SELECT id FROM mail_requests WHERE address=? AND state='queued'",(address,)).fetchone()
                    if not pending:
                        con.execute('INSERT INTO mail_requests(address,creator,operation,password_hash,created) VALUES(?,?,?,?,?)',
                                    (address,user['id'],'upsert',hash_password(password),int(time.time())))
        with connect() as con:
            # A prior process may have failed after changing policy or services. Do not blindly replay it.
            con.execute("UPDATE mail_requests SET state='uncertain',password_hash='',summary='Worker interrupted; inspect mail services before resubmitting' WHERE state='applying'")
            jobs=con.execute("SELECT * FROM mail_requests WHERE state='queued' ORDER BY id LIMIT 100").fetchall()
            def authorize(job,domain):
                actor=con.execute('SELECT id,role,active FROM users WHERE id=?',(job['creator'],)).fetchone()
                return bool(actor and actor['active'] and actor['role']!='readonly' and domain in permitted_domains(con,actor))
            policy,accepted,denied=apply_requests(policy,jobs,authorize)
            for jid in denied:
                con.execute("UPDATE mail_requests SET state='denied',password_hash='',summary='Ownership, account access or mailbox limit changed' WHERE id=?",(jid,))
            for jid in accepted:
                con.execute("UPDATE mail_requests SET state='applying' WHERE id=?",(jid,))
        atomic_json(POLICY,policy)
        result=subprocess.run(['/usr/bin/ansible-playbook','-i','/etc/olamidepanel/mail-local.ini',str(ROOT/'ansible/deploy-domain-email.yml'),'-e','@'+str(POLICY)],
                              stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=850)
        with connect() as con:
            for jid in accepted:
                con.execute('UPDATE mail_requests SET state=?,password_hash=\'\',summary=? WHERE id=?',
                            ('applied' if result.returncode==0 else 'failed',
                             'Mail configuration applied; public delivery needs DNS verification' if result.returncode==0 else 'Deployment failed; inspect mail configuration and rerun reconciliation',jid))
            if result.returncode==0:
                con.execute('DELETE FROM mail_inventory')
                for account in policy['mail_accounts']:
                    con.execute('INSERT INTO mail_inventory(address,updated) VALUES(?,?)',(account['address'],int(time.time())))
            con.execute("DELETE FROM mail_requests WHERE state NOT IN ('queued','applying') AND created<?",(int(time.time())-90*86400,))
        if result.returncode: raise RuntimeError('Mail deployment failed; review certificate, DNS and service prerequisites')


if __name__=='__main__':
    main()
