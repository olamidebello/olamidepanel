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
    if row['before'] in ('failed','inactive'):
     result=call(['systemctl','start',service],60);row['start_ok']=result.returncode==0
    row['after']=call(['systemctl','is-active',service]).stdout.strip();report['services'].append(row)
   preflight=call(['nginx','-t']);(attempt/'nginx-preflight.log').write_text(preflight.stdout+preflight.stderr)
   if preflight.returncode:raise ValueError('Invalid Nginx configuration; inspect nginx-preflight.log. No gateway files were edited.')
   report['stages']['panel']=run_stage(['python3',str(source/'restore_panel_domain.py')],attempt/'panel.log',600)
   # Panel routing failure is recorded, but does not prevent other domain checks.
   discover=call(['python3',str(source/'repair_domain_ssl.py'),'--discover'])
   if discover.returncode:raise ValueError('Nginx domain discovery failed; inspect diagnostics')
   domains=set(json.loads(discover.stdout))|set(targets)
   inventory=call(['runuser','-u','olamidepanel','--','env','PANEL_DB_CONFIG=/etc/olamidepanel/database.json','/opt/olamidepanel/venv/bin/python','/opt/olamidepanel/repo/deploy/export_domain_accounts.py'])
   (attempt/'inventory.log').write_text(inventory.stderr)
   if inventory.returncode:
    report['inventory_state']='panel_inventory_failed_using_nginx_and_approved_mapping'
   else:
    domains.update(r['domain'] for r in json.loads(inventory.stdout) if r.get('active'))
    report['inventory_state']='panel_and_nginx'
   selected=config.get('domains')
   if selected:
    if not isinstance(selected,list) or set(selected)-domains:raise ValueError('Selected domain is absent from discovered or approved inventory')
    domains=set(selected)
   if not domains:raise ValueError('No domains discovered')
   policy={'ipv4':config.get('ipv4','154.16.170.86'),'email':config.get('email','dobcalldemo@gmail.com'),
           'domains':sorted(domains),'targets':{d:t for d,t in targets.items() if d in domains}}
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
   report['requires_mapping']=[r['domain'] for r in report['domains'] if not r['application_identity_verified']]
   health=call(['nginx','-t']);report['nginx_ok']=health.returncode==0
   tls=call(['curl','--noproxy','*','--resolve','olamidepanel.com:443:127.0.0.1','-fsS','--max-time','20','https://olamidepanel.com/'])
   report['panel_https_identity_ok']=tls.returncode==0 and '<title>OlamidePanel' in tls.stdout and 'id="loginForm"' in tls.stdout
   report['renewal_timer_ok']=call(['systemctl','enable','--now','certbot.timer']).returncode==0
   passed=all(stage['state']=='passed' for stage in report['stages'].values())
   report['status']='checks_passed_identity_review_required' if passed and report['nginx_ok'] and report['panel_https_identity_ok'] and report['renewal_timer_ok'] else 'incomplete'
   if report['status']!='incomplete' and not report['requires_mapping']:report['status']='verified_repairs_complete'
  except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as error:
   report['reason']=str(error) if isinstance(error,ValueError) else type(error).__name__
  report['finished']=int(time.time());(BASE/'report.json').write_text(json.dumps(report,indent=2)+'\n')
  (attempt/'report.json').write_text(json.dumps(report,indent=2)+'\n')
  print(json.dumps(report))
  return 0 if report['status']=='verified_repairs_complete' else 1

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);args=parser.parse_args()
 raise SystemExit(main(json.loads(Path(args.config).read_text()),Path(__file__).resolve().parent))
