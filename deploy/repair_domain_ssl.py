"""Conservative Nginx routing repair and per-domain Certbot commissioning."""
import argparse
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

DOMAIN=re.compile(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}')
TOKEN=r'#[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{};]|[^\s{};]+'

def run(args,timeout=30):
 return subprocess.run(args,capture_output=True,text=True,check=True,timeout=timeout).stdout

def blocks(text,domain):
 tokens=[m for m in re.finditer(TOKEN,text) if not m.group().startswith('#')];found=[]
 for i,t in enumerate(tokens[:-1]):
  if t.group()!='server' or tokens[i+1].group()!='{':continue
  depth=1;j=i+2;names=[]
  while j<len(tokens) and depth:
   v=tokens[j].group()
   if v=='{':depth+=1
   elif v=='}':depth-=1
   elif depth==1 and v=='server_name':
    k=j+1
    while k<len(tokens) and tokens[k].group()!=';':names.append(tokens[k].group().strip('\"\''));k+=1
   j+=1
  if depth:raise ValueError('Unbalanced Nginx configuration')
  if domain in names:found.append((tokens[i+1].end(),tokens[j-1].start(),names))
 return found

def root_proxy_patch(body,port):
 # Only an exact, plain root location; preserve all API/download/marketplace routes.
 tokens=[m for m in re.finditer(TOKEN,body) if not m.group().startswith('#')]
 matches=[]
 for i,t in enumerate(tokens[:-3]):
  if [x.group() for x in tokens[i:i+3]]!=['location','/','{']:continue
  depth=1;j=i+3
  while j<len(tokens) and depth:
   v=tokens[j].group()
   if v=='{':depth+=1
   elif v=='}':depth-=1
   elif depth==1 and v=='proxy_pass':
    if j+2>=len(tokens) or tokens[j+2].group()!=';' or not re.fullmatch(r'http://127\.0\.0\.1:[0-9]+',tokens[j+1].group()):raise ValueError('Nonstandard root proxy requires review')
    matches.append((tokens[j+1].start(),tokens[j+1].end()))
   j+=1
 if not matches:return body,False
 if len(matches)!=1:raise ValueError('Ambiguous root proxy')
 a,b=matches[0];return body[:a]+'http://127.0.0.1:'+str(port)+body[b:],True

def sources():
 dump=run(['nginx','-T']);parts=re.split(r'^# configuration file (.+):\s*$',dump,flags=re.M);result={}
 for i in range(1,len(parts),2):
  path=Path(parts[i].strip()).resolve()
  if path.is_relative_to('/etc/nginx') and path.is_file():result[path]=path.read_text()
 return result

def dns(domain,kind):
 # Answer records (not +short) avoid treating CNAMEs as addresses.
 output=run(['dig','+time=5','+tries=1','+noall','+answer',domain,kind])
 return {line.split()[4] for line in output.splitlines() if len(line.split())>=5 and line.split()[3]==kind}

def repair(domain,target,backup):
 configs=sources();originals={};changed={};locations=0;http_locations=0;root_hits=0
 if target:
  port=int(target['port'])
  if not 1024<=port<=65535 or not isinstance(target.get('contains'),str) or len(target['contains'])<3:raise ValueError('Explicit port and application identity marker required')
  path=target.get('health','/')
  if not isinstance(path,str) or not path.startswith('/') or any(c.isspace() for c in path):raise ValueError('Invalid health path')
  response=run(['curl','--noproxy','*','-fsS','--max-time','10','http://127.0.0.1:'+str(port)+path])
  if target['contains'] not in response:raise ValueError('Backend application identity did not match')
 for file,text in configs.items():
  spans=blocks(text,domain)
  if not spans:continue
  # Do not repair duplicates: Nginx can ignore one vhost, and the file can host unrelated services.
  for a,b,names in spans:
   body=text[a:b]
   if re.search(r'\blisten\s+[^;]*\b443\b',body):locations+=1
   if re.search(r'\blisten\s+[^;]*\b80\b',body) or not re.search(r'\blisten\s',body):http_locations+=1
  if target:
   updated=text;count=0
   for a,b,names in reversed(spans):
    if any(n not in (domain,'www.'+domain) for n in names):raise ValueError('Shared server block requires explicit domain review')
    new,hit=root_proxy_patch(text[a:b],port);count+=int(hit);updated=updated[:a]+new+updated[b:]
   root_hits+=count
   if updated!=text:
    stat=file.stat()
    if stat.st_uid!=0 or stat.st_mode&0o022:raise ValueError('Unsafe configuration file permissions')
    originals[file]=text;changed[file]=updated
 if locations>1 or http_locations>1:raise ValueError('Duplicate HTTPS vhosts require review; no file changed')
 if not any(blocks(t,domain) for t in configs.values()):raise ValueError('No exact domain vhost; deploy application first')
 if target and not root_hits:raise ValueError('No supported root proxy to repair')
 for file,text in originals.items():(backup/(hashlib.sha256(str(file).encode()).hexdigest()+'.conf')).write_text(text)
 try:
  for file,text in changed.items():file.write_text(text)
  run(['nginx','-t']);run(['systemctl','reload','nginx'])
 except Exception:
  for file,text in originals.items():file.write_text(text)
  run(['nginx','-t']);run(['systemctl','reload','nginx']);raise
 return bool(changed)

def excluded_name(domain):
 return domain.endswith(('.invalid','.test','.localhost','.example')) or domain in ('mail.your-domain.com',)

def failure_details(error,phase):
 if isinstance(error,subprocess.CalledProcessError):
  tool=Path(error.cmd[0]).name if isinstance(error.cmd,(list,tuple)) else 'command'
  detail=(error.stderr or '').strip()[:600]
  return {'reason':phase+' failed: '+tool+' exit '+str(error.returncode), 'phase':phase,'exit_code':error.returncode,'detail':detail}
 if isinstance(error,subprocess.TimeoutExpired):return {'reason':phase+' timed out','phase':phase}
 return {'reason':str(error) if isinstance(error,ValueError) else type(error).__name__,'phase':phase}

def main(config):
 ip=str(ipaddress.IPv4Address(config['ipv4']));email=config['email']
 if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise ValueError('ACME email required')
 domains=config['domains'];targets=config.get('targets',{})
 if not domains:raise ValueError('No hosted domains selected')
 if any(not DOMAIN.fullmatch(d) for d in domains) or set(targets)-set(domains):raise ValueError('Invalid or unapproved domain mapping')
 base=Path('/var/lib/olamide-domain-ssl-repair');base.mkdir(mode=0o700,parents=True,exist_ok=True)
 with (base/'repair.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  backup=base/str(time.time_ns());backup.mkdir(mode=0o700)
  results=[]
  for domain in domains:
   row={'domain':domain,'status':'needs_attention'};phase='routing'
   if excluded_name(domain):
    row.update(status='excluded_reserved_or_placeholder',reason='Retired/reserved or documented placeholder; no certificate request made')
    results.append(row);continue
   try:
    phase='dns';a=dns(domain,'A');aaaa=dns(domain,'AAAA')
    row['dns']={'A':sorted(a),'AAAA':sorted(aaaa),'local_repair_server':ip}
    row['routing_changed']=False
    if a!={ip} or aaaa:
     if config.get('follow_current_dns') and (a or aaaa):
      phase='current_dns_https'
      run(['curl','--noproxy','*','-fsS','--max-time','20','https://'+domain+'/','-o','/dev/null'])
      row.update(status='https_verified_on_current_dns_server',repair_scope='remote_check_only',
                 reason='Current DNS destination preserved. Remote mapping and certificate repair require execution on that host.')
     else:
      row['status']='waiting_dns';row['reason']='No DNS address, or destination differs from local repair host'
     results.append(row);continue
    row['repair_scope']='local_host'
    phase='routing'
    if config.get('diagnostics_only'):
     if not any(blocks(text,domain) for text in sources().values()):raise ValueError('No exact domain vhost; deploy application first')
    else:row['routing_changed']=repair(domain,targets.get(domain),backup)
    # Certbot manages certificate installation and its own Nginx rollback on failure.
    phase='certificate_installation'
    if not config.get('diagnostics_only'):
     result=subprocess.run(['certbot','--nginx','--non-interactive','--agree-tos','--email',email,'--redirect','--keep-until-expiring','-d',domain],capture_output=True,text=True,timeout=240)
     (backup/(domain+'.certbot.log')).write_text(result.stdout+result.stderr)
     if result.returncode:raise ValueError('Certificate failed; inspect root-only Certbot log')
    run(['nginx','-t'])
    phase='https_response'
    run(['curl','--noproxy','*','--resolve',domain+':443:127.0.0.1','-fsS','--max-time','20','https://'+domain+'/','-o','/dev/null'])
    if domain in targets:
     t=targets[domain];body=run(['curl','--noproxy','*','--resolve',domain+':443:127.0.0.1','-fsS','--max-time','20','https://'+domain+t.get('health','/')])
     if t['contains'] not in body:raise ValueError('HTTPS application identity mismatch')
    row['status']='https_verified' if domain not in targets else 'routing_and_https_verified'
   except (ValueError,OSError,subprocess.SubprocessError) as e:
    row.update(failure_details(e,phase))
    (backup/(domain+'.failure.log')).write_text(str(e)+'\n'+(getattr(e,'stderr','') or ''))
   results.append(row)
  report={'domains':results,'backup':str(backup),'notice':'No application rebuild, database restore or DNS provider edits performed. Unmapped application identity remains unverified.'}
  (base/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
  return 0 if all(r['status'] in ('https_verified','routing_and_https_verified','https_verified_on_current_dns_server','excluded_reserved_or_placeholder') for r in results) else 1

if __name__=='__main__':
 os.umask(0o077)
 parser=argparse.ArgumentParser();parser.add_argument('--config');parser.add_argument('--discover',action='store_true');args=parser.parse_args()
 if args.discover:
  names=set()
  for text in sources().values():
   tokens=[m.group() for m in re.finditer(TOKEN,text) if not m.group().startswith('#')]
   for i,value in enumerate(tokens):
    if value!='server_name':continue
    for name in tokens[i+1:]:
     if name==';':break
     name=name.strip('"\'')
     if DOMAIN.fullmatch(name):names.add(name)
  print(json.dumps(sorted(names)))
 elif args.config:raise SystemExit(main(json.loads(Path(args.config).read_text())))
 else:parser.error('--config or --discover required')
