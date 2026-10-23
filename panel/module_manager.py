"""Fixed module adapters, MySQL audit state and authorized operator job queue."""
import hashlib
import json
from pathlib import Path
import time
from database import connect

# Only these existing source adapters can be repaired by the privileged runner.
ADAPTERS={
 'core':(['ai_billing.py','api_keys.py','domain_marketplace.py','server.py','database.py','module_manager.py','modules.py','module-audit.json','schema.sql','static/app.js'],['pymysql']),
 'files':(['storage.py'],['PIL']),
 'websites':(['websites.py','site_controls.py'],['dns.resolver']),
 'marketplace':(['marketplace.py','fulfillment.py'],[]),
 'payments':(['payments.py'],['cryptography']),
 'security':(['mfa.py'],['cryptography']),
 'dns':(['dns_tools.py'],['dns.resolver']),
 'hosting':(['hosted_domains.py'],[]),
 'watchdog':(['watchdog.py'],[]),
}
SCHEMA=[
 '''CREATE TABLE IF NOT EXISTS module_jobs(id BIGINT AUTO_INCREMENT PRIMARY KEY,
 adapter VARCHAR(32) NOT NULL, operation VARCHAR(16) NOT NULL, creator BIGINT NOT NULL,
 state VARCHAR(24) NOT NULL DEFAULT 'queued', created BIGINT NOT NULL, finished BIGINT,
 summary VARCHAR(500) NOT NULL DEFAULT '', INDEX module_queue(state,id)) ENGINE=InnoDB''',
 '''CREATE TABLE IF NOT EXISTS module_status(adapter VARCHAR(32) PRIMARY KEY,
 checked_at BIGINT NOT NULL, last_repair BIGINT NOT NULL DEFAULT 0, state VARCHAR(32) NOT NULL, checks TEXT NOT NULL) ENGINE=InnoDB'''
]
def initialize(db=connect):
 with db() as c:
  for sql in SCHEMA:c.execute(sql)

def authorize(user):
 if user.get('role') not in ('root','super_admin'):raise PermissionError('Super-admin access required')

def report(user,db=connect):
 authorize(user)
 with db() as c:
  status={r['adapter']:dict(r) for r in c.execute('SELECT * FROM module_status').fetchall()}
  jobs=[dict(r) for r in c.execute('SELECT * FROM module_jobs ORDER BY id DESC LIMIT 200').fetchall()]
 for value in status.values():value['checks']=json.loads(value['checks'])
 tools=json.loads((Path(__file__).parent/'module-audit.json').read_text())
 return {'adapters':[{'id':key,'files':files,'prerequisites':deps,'status':status.get(key)} for key,(files,deps) in ADAPTERS.items()],
         'jobs':jobs,'tools':tools,'notice':'Repairs restore existing adapters and install their prerequisites. Partial and unavailable features retain their implementation status; absent adapters require development or provider configuration.'}

def queue(user,body,db=connect):
 authorize(user)
 operation=body.get('operation');adapter=body.get('adapter')
 if operation=='cancel':
  with db() as c:
   c.execute("UPDATE module_jobs SET state='cancelled',finished=?,summary='Cancelled by super administrator' WHERE state='queued'",(int(time.time()),))
   c.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)',(user['username'],'modules:cancel-queued',int(time.time())))
  return {'queued':0}
 if operation not in ('audit','repair'):raise ValueError('Invalid module operation')
 if adapter!='all' and adapter not in ADAPTERS:raise ValueError('Unknown module adapter')
 targets=list(ADAPTERS) if adapter=='all' else [adapter]
 with db() as c:
  # A named row lock serializes GUI queue submissions without arbitrary commands.
  c.execute('SELECT id FROM users ORDER BY id LIMIT 1 FOR UPDATE',()).fetchone()
  if c.execute("SELECT id FROM module_jobs WHERE state IN ('queued','running') LIMIT 1").fetchone():raise ValueError('Module operations already pending; wait for the queue to finish')
  for target in targets:c.execute('INSERT INTO module_jobs(adapter,operation,creator,created) VALUES(?,?,?,?)',(target,operation,user['id'],int(time.time())))
  c.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)',(user['username'],'modules:'+operation+':'+adapter,int(time.time())))
 return {'queued':len(targets)}
