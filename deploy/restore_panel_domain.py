"""Restore olamidepanel.com without replacing other hosted application vhosts."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

DOMAIN='olamidepanel.com'
CONF=Path('/etc/nginx/conf.d/00-olamidepanel-restored.conf')
BASE=Path('/var/lib/olamidepanel-domain-repair')
TOKEN=r'#[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{};]|[^\s{};]+'

def command(args,timeout=30):
 return subprocess.run(args,check=True,capture_output=True,text=True,timeout=timeout).stdout

def strip_domain(text):
 """Remove only the apex name; preserve server blocks naming other domains."""
 tokens=[m for m in re.finditer(TOKEN,text) if not m.group().startswith('#')]
 edits=[];count=0
 for i,t in enumerate(tokens[:-1]):
  if t.group()!='server' or tokens[i+1].group()!='{':continue
  depth=1;j=i+2;directives=[];names=[]
  while j<len(tokens) and depth:
   value=tokens[j].group()
   if value=='{':depth+=1
   elif value=='}':depth-=1
   elif depth==1 and value=='server_name':
    k=j+1;values=[]
    while k<len(tokens) and tokens[k].group()!=';':values.append(tokens[k]);k+=1
    if k==len(tokens):raise ValueError('Unterminated server_name')
    directives.append((tokens[j].start(),tokens[k].end(),values));names.extend(x.group().strip('\"\'') for x in values)
   j+=1
  if depth:raise ValueError('Unbalanced server block')
  if DOMAIN not in names:continue
  count+=1
  if all(n==DOMAIN for n in names):edits.append((t.start(),tokens[j-1].end(),''))
  else:
   for start,end,values in directives:
    kept=[v.group() for v in values if v.group().strip('\"\'')!=DOMAIN]
    edits.append((start,end,'server_name '+' '.join(kept)+';' if kept else ''))
 for start,end,replacement in sorted(edits,reverse=True):text=text[:start]+replacement+text[end:]
 return text,count

def panel_body(body):
 return '<title>OlamidePanel' in body and 'id="loginForm"' in body

def files():
 parts=re.split(r'^# configuration file (.+):\s*$',command(['nginx','-T']),flags=re.M);out={}
 for i in range(1,len(parts),2):
  p=Path(parts[i].strip()).resolve()
  if p.is_relative_to('/etc/nginx') and p.is_file():out[p]=p.read_text()
 return out

def site(tls=False):
 text='''# Managed by restore_panel_domain.py
server {
 listen 80;
 server_name olamidepanel.com;
 client_max_body_size 25m;
 location / {
  proxy_pass http://127.0.0.1:8090;
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;
 }
}
'''
 if tls:
  text+='''server {
 listen 443 ssl;
 server_name olamidepanel.com;
 ssl_certificate /etc/letsencrypt/live/olamidepanel.com/fullchain.pem;
 ssl_certificate_key /etc/letsencrypt/live/olamidepanel.com/privkey.pem;
 ssl_protocols TLSv1.2 TLSv1.3;
 client_max_body_size 25m;
 location / {
  proxy_pass http://127.0.0.1:8090;
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;
 }
}
'''
 return text

def valid_existing_cert():
 try:
  command(['openssl','x509','-in','/etc/letsencrypt/live/olamidepanel.com/fullchain.pem','-noout','-checkhost',DOMAIN,'-checkend','86400'])
  command(['openssl','verify','-CApath','/etc/ssl/certs','-untrusted','/etc/letsencrypt/live/olamidepanel.com/fullchain.pem','-verify_hostname',DOMAIN,'/etc/letsencrypt/live/olamidepanel.com/fullchain.pem'])
  return True
 except subprocess.SubprocessError:return False

def main():
 if os.geteuid()!=0:raise ValueError('Root execution required')
 os.umask(0o077);BASE.mkdir(parents=True,exist_ok=True,mode=0o700)
 with (BASE/'repair.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  stamp=BASE/str(time.time_ns());stamp.mkdir(mode=0o700)
  report={'domain':DOMAIN,'backup':str(stamp),'status':'failed'}
  originals={};changed={};started=False;old_conf=None;conf_existed=False
  try:
   body=command(['curl','--noproxy','*','-fsS','--max-time','10','http://127.0.0.1:8090/'])
   if not panel_body(body):raise ValueError('Port 8090 is not the OlamidePanel login. No gateway files changed.')
   original=files()
   if CONF.is_symlink():raise ValueError('Refuse symlink at managed configuration path')
   conf_existed=CONF.exists();old_conf=CONF.read_text() if conf_existed else None
   if conf_existed and (not old_conf.startswith('# Managed by restore_panel_domain.py') or CONF.stat().st_uid!=0 or CONF.stat().st_mode&0o022):raise ValueError('Managed filename contains an unrelated or unsafe configuration')
   removed=0
   for path,text in original.items():
    new,count=strip_domain(text);removed+=count
    if new!=text:
     stat=path.stat()
     if stat.st_uid!=0 or stat.st_mode&0o022:raise ValueError('Unsafe vhost permissions: '+str(path))
     originals[path]=text;changed[path]=new
   if conf_existed:originals.setdefault(CONF,old_conf)
   for path,text in originals.items():(stamp/(hashlib.sha256(str(path).encode()).hexdigest()+'.conf')).write_text(text)
   (stamp/'manifest.json').write_text(json.dumps([str(p) for p in originals],indent=2))
   started=True
   for path,text in changed.items():path.write_text(text)
   CONF.write_text(site(valid_existing_cert()));CONF.chmod(0o644)
   command(['nginx','-t']);command(['systemctl','reload','nginx'])
   body=command(['curl','--noproxy','*','-fsS','--max-time','10','--resolve',DOMAIN+':80:127.0.0.1','http://'+DOMAIN+'/'])
   if not panel_body(body):raise ValueError('Local domain routing is still incorrect; check included/wildcard vhosts')
   report.update(status='routing_restored_ssl_pending',removed_apex_claims=removed)
   def answers(kind):
    output=command(['dig','+time=5','+tries=1','+noall','+answer',DOMAIN,kind])
    return {line.split()[4] for line in output.splitlines() if len(line.split())>=5 and line.split()[3]==kind}
   if answers('A')!={'154.16.170.86'} or answers('AAAA'):
    report['status']='routing_restored_waiting_dns'
    report['reason']='Set apex A to 154.16.170.86 and remove stale AAAA before certificate issuance.'
   else:
    result=subprocess.run(['certbot','--nginx','--non-interactive','--agree-tos','--email','dobcalldemo@gmail.com','--redirect','--keep-until-expiring','-d',DOMAIN],capture_output=True,text=True,timeout=240)
    (stamp/'certbot.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise ValueError('Routing restored; certificate installation failed. Inspect private certbot.log.')
    command(['nginx','-t'])
    body=command(['curl','--noproxy','*','--resolve',DOMAIN+':443:127.0.0.1','-fsS','--max-time','20','https://'+DOMAIN+'/'])
    if not panel_body(body):raise ValueError('HTTPS returned the wrong application')
    report['status']='panel_routing_and_https_verified'
  except Exception as error:
   if started and report['status']=='failed':
    for path,text in originals.items():path.write_text(text)
    if conf_existed:CONF.write_text(old_conf)
    else:CONF.unlink(missing_ok=True)
    try:command(['nginx','-t']);command(['systemctl','reload','nginx']);report['rolled_back']=True
    except Exception:report['rolled_back']=False
   report['reason']=str(error) if isinstance(error,ValueError) else type(error).__name__
  (BASE/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
  return 0 if report['status']=='panel_routing_and_https_verified' else 1
if __name__=='__main__':raise SystemExit(main())
