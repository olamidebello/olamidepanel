"""Static-site request API. A separate root worker verifies and provisions."""
import html,json,secrets,time
from database import connect

def page(title,tagline):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><body style="margin:0;background:#102e27;color:#ecf4e6;font:20px system-ui;display:grid;place-items:center;min-height:100vh"><main style="max-width:800px;padding:40px"><small>WELCOME</small><h1 style="font-size:clamp(36px,7vw,80px)">'+html.escape(title)+'</h1><p>'+html.escape(tagline)+'</p></main></body></html>'

def handle(method,path,user,body=None):
    if method=='GET':
        with connect() as con:
            rows=con.execute('SELECT d.id,d.name,s.token,s.state,s.message,s.title,s.tagline,s.updated FROM domains d LEFT JOIN website_requests s ON s.domain_id=d.id WHERE d.owner=? ORDER BY d.id',(user['id'],)).fetchall()
        return 200,rows
    if user['role']=='readonly':return 403,{'error':'Read-only access'}
    title=str(body.get('title','')).strip();tagline=str(body.get('tagline','')).strip()
    if not 1<=len(title)<=100 or len(tagline)>500:raise ValueError('Provide a title (1–100 characters) and tagline (up to 500)')
    with connect() as con:
        domain=con.execute('SELECT * FROM domains WHERE id=? AND owner=? FOR UPDATE',(int(body['domain_id']),user['id'])).fetchone()
        if not domain:return 404,{'error':'Unknown domain'}
        old=con.execute('SELECT * FROM website_requests WHERE domain_id=? FOR UPDATE',(domain['id'],)).fetchone()
        token=old['token'] if old else secrets.token_urlsafe(32)
        con.execute("INSERT INTO website_requests(domain_id,token,state,message,title,tagline,updated) VALUES(?,?,'queued','Awaiting server ownership checks',?,?,?) ON DUPLICATE KEY UPDATE state='queued',message='Awaiting server ownership checks',title=VALUES(title),tagline=VALUES(tagline),updated=VALUES(updated)",(domain['id'],token,title,tagline,int(time.time())))
        con.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)',(user['username'],'static website queued '+domain['name'],int(time.time())))
    return 200,{'ok':True,'token':token,'txt_name':'_olamidepanel.'+domain['name'],'message':'Publish requested. Add the displayed DNS TXT proof and point the domain A record to this server, the worker automatically checks DNS and publishes when ready. The provisioning worker must be installed.'}
