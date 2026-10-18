#!/usr/bin/python3
"""Root-only worker. Never executes inventory-supplied commands or edits site data."""
import concurrent.futures
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
sys.path.insert(0,'/opt/olamidepanel/panel')
import hosted_domains
import watchdog
from database import connect

CONFIG=Path('/etc/olamidepanel/watchdog.json')
LOCK=Path('/run/olamidepanel-watchdog.lock')

def command(args, timeout=20):
 return subprocess.run(args,capture_output=True,text=True,timeout=timeout)

def probe(domain, target):
 checks={}
 try:
  # No redirects, shell, environment proxy, user URLs or external backend requests.
  r=command(['curl','--silent','--show-error','--noproxy','*','--max-time','8',
             '--resolve',domain+':443:127.0.0.1','--output','/dev/null',
             '--write-out','%{http_code}','https://'+domain+'/'],12)
  checks['https']=r.returncode==0 and r.stdout.strip().isdigit() and 200<=int(r.stdout.strip())<400
 except (OSError,subprocess.TimeoutExpired):checks['https']=False
 for index, endpoint in enumerate(target.get('checks', [])):
  key='backend_'+str(index+1)
  try:
   port=int(endpoint['port']);path=endpoint['path']
   if not 1024<port<65536 or not re.fullmatch(r'/[A-Za-z0-9/_-]*',path):raise ValueError('Invalid backend')
   r=command(['curl','--silent','--show-error','--noproxy','*','--max-time','5',
              '--max-filesize','65536','--write-out','\n%{http_code}',
              'http://127.0.0.1:'+str(port)+path],8)
   body,code=r.stdout.rsplit('\n',1)
   checks[key]=r.returncode==0 and int(code)==int(endpoint.get('status',200))
   if 'field' in endpoint:checks[key]=checks[key] and json.loads(body).get(endpoint['field'])==endpoint['value']
  except (KeyError,TypeError,ValueError,OSError,subprocess.TimeoutExpired):checks[key]=False
 return checks

def decide(checks, previous, now, target):
 failures=0 if all(checks.values()) else int(previous.get('failures',0))+1
 if not failures:return failures,'healthy'
 if failures<2:return failures,'observing'
 if not target.get('service'):return failures,'operator_required'
 if now-int(previous.get('last_restart',0))<900:return failures,'cooldown'
 # A web/TLS failure alone does not justify restarting a healthy application.
 if not any(not v for k,v in checks.items() if k.startswith('backend_')):return failures,'routing_or_tls_attention'
 return failures,'restart_pending'

def save(domain, checks, failures, last_restart, action):
 now=int(time.time());healthy=all(checks.values());payload=json.dumps(checks)
 with connect() as c:
  c.execute('INSERT INTO watchdog_domains(domain,checked_at,healthy,failures,last_restart,action,checks) VALUES(?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE checked_at=VALUES(checked_at),healthy=VALUES(healthy),failures=VALUES(failures),last_restart=VALUES(last_restart),action=VALUES(action),checks=VALUES(checks)',(domain,now,healthy,failures,last_restart,action,payload))
  c.execute('INSERT INTO watchdog_events(domain,checked_at,healthy,action,checks) VALUES(?,?,?,?,?)',(domain,now,healthy,action,payload))
 print(json.dumps({'domain':domain,'action':action,'healthy':healthy}),flush=True)

def main():
 with LOCK.open('w') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return
  config=json.loads(CONFIG.read_text());targets=config.get('targets',{})
  # Only root-writable configuration can name restartable units.
  st=CONFIG.stat()
  if st.st_uid!=0 or st.st_mode & 0o022:raise ValueError('Unsafe watchdog configuration ownership')
  for domain,target in targets.items():
   if not hosted_domains.DOMAIN.fullmatch(domain):raise ValueError('Invalid configured domain')
   if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]*\.service',target.get('service','')):raise ValueError('Invalid configured unit')
   if not target.get('checks') or len(target['checks'])>8:raise ValueError('One to eight backend checks required')
  watchdog.initialize()
  inventory=hosted_domains.report({'role':'root'},connect)['domains']
  domains=sorted({r['name'] for r in inventory if hosted_domains.DOMAIN.fullmatch(r['name'])}|set(targets))
  with connect() as c:previous={r['domain']:dict(r) for r in c.execute('SELECT * FROM watchdog_domains').fetchall()}
  nginx_ok=command(['nginx','-t']).returncode==0
  # Recover only a stopped nginx with valid configuration, never rewrite vhosts.
  if nginx_ok and command(['systemctl','is-active','nginx.service']).returncode!=0:
   command(['systemctl','start','nginx.service'],40)
  def check(domain):return domain,probe(domain,targets.get(domain,{}))
  with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
   results=list(pool.map(check,domains))
  restarted=set()
  for domain,checks in results:
   checks['nginx_config']=nginx_ok
   old=previous.get(domain,{});target=targets.get(domain,{})
   now=int(time.time());last=int(old.get('last_restart',0))
   failures,action=decide(checks,old,now,target)
   if action=='restart_pending':
    service=target['service']
    # Shared backends restart once per run and obey the longest stored cooldown.
    shared_last=max([int(v.get('last_restart',0)) for d,v in previous.items() if targets.get(d,{}).get('service')==service]+[0])
    if service in restarted or now-shared_last<900:action='shared_service_cooldown'
    else:
     last=now;save(domain,checks,failures,last,action);restarted.add(service)
     try:
      result=command(['systemctl','restart',service],40)
      action='restart_failed'
      if result.returncode==0:
       for attempt in range(3):
        time.sleep(2);checks=probe(domain,target);checks['nginx_config']=nginx_ok
        if all(checks.values()):failures=0;action='recovered';break
       else:action='operator_required'
     except (OSError,subprocess.TimeoutExpired):action='restart_failed'
   save(domain,checks,failures,last,action)
  with connect() as c:
   c.execute('DELETE FROM watchdog_events WHERE checked_at<?',(int(time.time())-90*86400,))
   # Keep old domain snapshots visible as stale rather than silently hiding them.

if __name__=='__main__':main()
