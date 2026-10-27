"""Root coordinator: continue domain repair after individual failures, retain evidence."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

BASE=Path('/var/lib/olamide-all-domain-repair')

def call(argv,timeout=30):
 return subprocess.run(argv,capture_output=True,text=True,timeout=timeout)

def load_approved(path):
 path=Path(path)
 if not path.exists():return {}
 info=path.lstat()
 if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode&0o077:
  raise ValueError('Approved mapping must be a root-owned regular file, mode 0600 or 0400')
 value=json.loads(path.read_text())
 if not isinstance(value,dict) or not isinstance(value.get('targets',{}),dict):raise ValueError('Expected an object containing targets')
 return value.get('targets',{})

HOSTNAME=re.compile(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}')
SAVED_INVENTORIES=[
 '/var/lib/olamidepanel/hosted-domains.json',
 '/etc/olamidepanel/domain-feature-report.json',
 '/var/lib/olamide-domain-restore/report.json',
 '/etc/olamide-six-domains.json',
 '/etc/olamidepanel/mail-policy.json',
]

def inventory_names(value):
 names=set();remaining=20000
 def walk(node,key=''):
  nonlocal remaining
  remaining-=1
  if remaining<0:raise ValueError('Inventory exceeds supported entry count')
  if isinstance(node,dict):
   for k,v in node.items():
    if isinstance(k,str) and HOSTNAME.fullmatch(k.lower()):names.add(k.lower())
    walk(v,k)
  elif isinstance(node,list):
   for item in node:walk(item,key)
  elif isinstance(node,str) and key in ('domain','name','hostname','domains','mail_domains','mail_extra_domains') and HOSTNAME.fullmatch(node.lower()):names.add(node.lower())
 walk(value);return names

def saved_domains(paths=SAVED_INVENTORIES):
 names=set();notes=[]
 for filename in paths:
  path=Path(filename)
  if not path.exists():continue
  info=path.lstat()
  if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022 or info.st_size>2097152:
   notes.append({'path':filename,'state':'unsafe_or_oversize_skipped'});continue
  try:names.update(inventory_names(json.loads(path.read_text())))
  except (ValueError,OSError):notes.append({'path':filename,'state':'invalid_inventory_skipped'})
 return names,notes

def select_domains(domains,parents):
 if not isinstance(parents,list) or any(not isinstance(p,str) or not HOSTNAME.fullmatch(p) for p in parents):raise ValueError('Invalid parent domain selection')
 result={name for name in domains if any(name==p or name.endswith('.'+p) for p in parents)}
 if any(not any(n==p or n.endswith('.'+p) for n in result) for p in parents):raise ValueError('Selected domain and subdomains absent from inventory')
 return result


def run_stage(argv,log,timeout):
 try:
  result=call(argv,timeout)
  log.write_text(result.stdout+result.stderr)
  return {'state':'passed' if result.returncode==0 else 'failed','rc':result.returncode,'log':str(log)}
 except subprocess.TimeoutExpired:
  log.write_text('Stage exceeded its deadline; inspect its own report before rerunning.\n')
  return {'state':'failed','reason':'timeout','log':str(log)}


def main(config,source):
 if os.geteuid()!=0:raise ValueError('Run as root')
 os.umask(0o077);BASE.mkdir(parents=True,exist_ok=True,mode=0o700)
 with (BASE/'repair.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  attempt=BASE/str(time.time_ns());attempt.mkdir(mode=0o700)
  report={'run':str(attempt),'status':'incomplete','stages':{},'services':[], 'domains':[],
          'notice':'No DNS provider changes, application rebuilds, database repairs or credential resets. Unmapped application identities are unverified.'}
  try:
   targets=load_approved(config.get('approved_mapping','/etc/olamidepanel/domain-routing-approved.json'))
   # A root-only policy saved by the previous installer is also an approved source.
   if not targets:targets=load_approved('/var/lib/olamide-domain-ssl-repair/config.json')
   report['approved_mapping_count']=len(targets)
   for service in sorted({'nginx.service','olamidepanel.service'} | {t['service'] for t in targets.values() if isinstance(t,dict) and t.get('service')}):
    if not re.fullmatch(r'[A-Za-z0-9_.@-]+\.service',service):raise ValueError('Invalid approved service name')
    current=call(['systemctl','is-active',service]);row={'service':service,'before':current.stdout.strip()}
    if row['before'] in ('failed','inactive') and not config.get('diagnostics_only'):
     result=call(['systemctl','start',service],60);row['start_ok']=result.returncode==0
    row['after']=call(['systemctl','is-active',service]).stdout.strip();report['services'].append(row)
   preflight=call(['nginx','-t']);(attempt/'nginx-preflight.log').write_text(preflight.stdout+preflight.stderr)
   if preflight.returncode:raise ValueError('Invalid Nginx configuration; inspect nginx-preflight.log. No gateway files were edited.')
   report['stages']['panel']={'state':'diagnostics_only'} if config.get('diagnostics_only') else run_stage(['python3',str(source/'restore_panel_domain.py')],attempt/'panel.log',600)
   # Panel routing failure is recorded, but does not prevent other domain checks.
   discover=call(['python3',str(source/'repair_domain_ssl.py'),'--discover'])
   if discover.returncode:raise ValueError('Nginx domain discovery failed; inspect diagnostics')
   domains=set(json.loads(discover.stdout))|set(targets)
   saved,notes=saved_domains();domains.update(saved);report['inventory_notes']=notes
   extra=config.get('extra_domains',[])
   if not isinstance(extra,list) or any(not isinstance(d,str) or not HOSTNAME.fullmatch(d) for d in extra):raise ValueError('Invalid extra domain list')
   domains.update(extra)
   nginx_dump=call(['nginx','-T'])
   wildcards=sorted(set(re.findall(r'(?<![a-zA-Z0-9_-])\*\.(?:[a-z0-9-]+\.)+[a-z]{2,63}',nginx_dump.stdout)))
   report['wildcards']=[{'name':n,'state':'dns_01_certificate_review_required'} for n in wildcards]
   inventory=call(['runuser','-u','olamidepanel','--','env','PANEL_DB_CONFIG=/etc/olamidepanel/database.json','/opt/olamidepanel/venv/bin/python','/opt/olamidepanel/repo/deploy/export_domain_accounts.py'])
   (attempt/'inventory.log').write_text(inventory.stderr)
   if inventory.returncode:
    report['inventory_state']='panel_inventory_failed_using_nginx_and_approved_mapping'
   else:
    domains.update(r['domain'] for r in json.loads(inventory.stdout) if r.get('active'))
    report['inventory_state']='panel_and_nginx'
   selected=config.get('domains')
   if selected:
    domains=select_domains(domains,selected)
    report['wildcards']=[w for w in report['wildcards'] if any(w['name'][2:]==p or w['name'][2:].endswith('.'+p) for p in selected)]
   if not domains:raise ValueError('No domains discovered')
   report['discovered_domains']=sorted(domains)
   report['coverage']='Known apex and subdomain inventory; undisclosed external DNS names are not discoverable here'
   policy={'ipv4':config.get('ipv4','154.16.170.86'),'email':config.get('email','dobcalldemo@gmail.com'),
           'domains':sorted(domains),'diagnostics_only':bool(config.get('diagnostics_only')),'targets':{d:t for d,t in targets.items() if d in domains}}
   (attempt/'policy.json').write_text(json.dumps(policy,indent=2))
   report['stages']['domains']=run_stage(['python3',str(source/'repair_domain_ssl.py'),'--config',str(attempt/'policy.json')],attempt/'domains.log',max(600,len(domains)*300))
   # Use this stage's stdout rather than a possibly stale global report.
   stage_text=(attempt/'domains.log').read_text()
   try:
    decoder=json.JSONDecoder();outcome,_=decoder.raw_decode(stage_text.lstrip())
    report['domains']=outcome['domains']
    for row in report['domains']:
     row['application_identity_verified']=row['status']=='routing_and_https_verified'
     if row['domain']=='olamidepanel.com' and report['stages']['panel']['state']=='passed':row['application_identity_verified']=True
   except (ValueError,KeyError,TypeError):report['domain_report_state']='stage_did_not_produce_valid_report'
   report['requires_mapping']=[r['domain'] for r in report['domains'] if not r['application_identity_verified'] and r['status']!='excluded_reserved_or_placeholder']
   health=call(['nginx','-t']);report['nginx_ok']=health.returncode==0
   tls=call(['curl','--noproxy','*','--resolve','olamidepanel.com:443:127.0.0.1','-fsS','--max-time','20','https://olamidepanel.com/'])
   report['panel_https_identity_ok']=tls.returncode==0 and '<title>OlamidePanel' in tls.stdout and 'id="loginForm"' in tls.stdout
   report['renewal_timer_ok']=call(['systemctl','is-enabled','certbot.timer'] if config.get('diagnostics_only') else ['systemctl','enable','--now','certbot.timer']).returncode==0
   passed=all(stage['state']=='passed' for stage in report['stages'].values())
   report['status']='checks_passed_identity_review_required' if passed and report['nginx_ok'] and report['panel_https_identity_ok'] and report['renewal_timer_ok'] else 'incomplete'
   if report['status']!='incomplete' and not report['requires_mapping'] and not report.get('wildcards'):report['status']='verified_repairs_complete'
  except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as error:
   report['reason']=str(error) if isinstance(error,ValueError) else type(error).__name__
  if config.get('diagnostics_only'):report['mode']='diagnostics_only_no_routing_or_certificate_changes'
  report['finished']=int(time.time());(BASE/'report.json').write_text(json.dumps(report,indent=2)+'\n')
  (attempt/'report.json').write_text(json.dumps(report,indent=2)+'\n')
  print(json.dumps(report))
  return 0 if report['status']=='verified_repairs_complete' or config.get('diagnostics_only') and 'reason' not in report else 1

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);args=parser.parse_args()
 raise SystemExit(main(json.loads(Path(args.config).read_text()),Path(__file__).resolve().parent))
