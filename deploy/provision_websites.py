"""Narrow root worker: DNS-proven static HTML websites only, no arbitrary commands."""
import fcntl,ipaddress,json,os,re,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,'/opt/olamidepanel/panel')
from database import connect
from websites import page
from site_controls import defaults
from apply_site_controls import apply
import dns.resolver

STATE=Path('/var/lib/olamidepanel-provisioner')
AVAILABLE=Path('/etc/nginx/sites-available')
ENABLED=Path('/etc/nginx/sites-enabled')
ROOT=Path('/var/www/olamidepanel-static')
DOMAIN=re.compile(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}')

def command(args,timeout=30):
    r=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    if r.returncode:raise RuntimeError('Server command failed: '+args[0]+'. Operator should inspect service logs.')

def status(uid,state,message):
    with connect() as con:con.execute('UPDATE website_requests SET state=?,message=?,updated=? WHERE domain_id=?',(state,message,int(time.time()),uid))

def run():
    config=json.loads(Path('/etc/olamidepanel/provisioning.json').read_text())
    ip=str(ipaddress.IPv4Address(config['public_ipv4']))
    reserved=config['panel_hostname'].lower()
    email=config['acme_email']
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise ValueError('Invalid ACME email')
    resolver=dns.resolver.Resolver();resolver.lifetime=8
    manifest_path=STATE/'managed.json';manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    with connect() as con:
        valid=con.execute("SELECT d.id FROM domains d JOIN users u ON u.id=d.owner WHERE u.active=1").fetchall()
        jobs=con.execute("SELECT s.*,d.name,c.settings AS site_settings,c.revision AS controls_revision FROM website_requests s JOIN domains d ON d.id=s.domain_id LEFT JOIN website_controls c ON c.domain_id=d.id JOIN users u ON u.id=d.owner WHERE (s.state='queued' OR (s.state='waiting_dns' AND s.updated<=UNIX_TIMESTAMP()-60)) AND u.active=1 ORDER BY s.updated LIMIT 5").fetchall()
    active={str(r['id']) for r in valid}
    for uid in list(manifest):
        if uid not in active:
            (ENABLED/('olamide-static-'+uid)).unlink(missing_ok=True)
            (AVAILABLE/('olamide-static-'+uid)).unlink(missing_ok=True)
            del manifest[uid]
            command(['nginx','-t']);command(['systemctl','reload','nginx'])
    for job in jobs:
        uid=int(job['domain_id']);domain=job['name']
        try:
            if uid<=0 or len(domain)>253 or not DOMAIN.fullmatch(domain) or domain==reserved:raise ValueError('Domain is invalid or reserved for the panel')
            try:
                answers=resolver.resolve('_olamidepanel.'+domain,'TXT')
                proofs=[b''.join(answer.strings).decode('utf-8') for answer in answers]
                if job['token'] not in proofs:raise ValueError('Ownership TXT value does not match')
                addresses={str(answer) for answer in resolver.resolve(domain,'A')}
                if addresses!={ip}:raise ValueError('A records must point only to '+ip+' before publishing')
                try:
                    if list(resolver.resolve(domain,'AAAA')):raise ValueError('Remove AAAA records for this IPv4-only publisher')
                except (dns.resolver.NoAnswer,dns.resolver.NXDOMAIN):pass
            except (dns.exception.DNSException, ValueError) as error:
                message = str(error) if isinstance(error, ValueError) else 'DNS proof/address lookup failed. Check TXT/A records.'
                status(uid,'waiting_dns',message[:350]+'; automatic checks continue every minute. No resubmission needed.')
                continue
            site=ROOT/str(uid)
            if site.is_symlink():raise ValueError('Unsafe site directory')
            site.mkdir(mode=0o755,parents=True,exist_ok=True)
            index=site/'index.html'
            if index.is_symlink():raise ValueError('Unsafe index path')
            index.write_text(page(job['title'],job['tagline']));index.chmod(0o644)
            target=AVAILABLE/('olamide-static-'+str(uid));link=ENABLED/target.name
            previous=target.read_text() if target.exists() else None
            # Avoid replacing unrelated nginx configurations using this domain.
            for item in ENABLED.iterdir():
                if item==link or not item.is_file():continue
                if re.search(r'\bserver_name\s+[^;]*\b'+re.escape(domain)+r'(?=\s|;)',item.read_text(errors='ignore')):raise ValueError('Another enabled Nginx site already uses this domain')
            if str(uid) not in manifest or not target.exists():
                target.write_text('server {\n listen 80;\n server_name '+domain+';\n root '+str(site)+';\n index index.html;\n location / { try_files $uri $uri/ =404; }\n location ~ /\\. { deny all; }\n}\n')
                target.chmod(0o644)
                if not link.exists():link.symlink_to(target)
                try:command(['nginx','-t']);command(['systemctl','reload','nginx'])
                except Exception:
                    if previous is None:link.unlink(missing_ok=True);target.unlink(missing_ok=True)
                    else:target.write_text(previous)
                    raise
            manifest[str(uid)]=domain
            manifest_path.write_text(json.dumps(manifest))
            command(['certbot','--nginx','--non-interactive','--agree-tos','--email',email,'-d',domain,'--redirect','--keep-until-expiring'],timeout=120)
            settings=json.loads(job['site_settings']) if job.get('site_settings') else defaults()
            apply(site,target,Path('/etc/nginx/olamidepanel-static')/(str(uid)+'.conf'),settings,domain,lambda:command(['nginx','-t']),lambda:command(['systemctl','reload','nginx']))
            # A concurrent settings edit must remain queued for the next worker pass.
            with connect() as con:
                current=con.execute('SELECT revision FROM website_controls WHERE domain_id=? FOR UPDATE',(uid,)).fetchone()
                request=con.execute('SELECT title,tagline,updated FROM website_requests WHERE domain_id=? FOR UPDATE',(uid,)).fetchone()
                same_request=request and all(request[k]==job[k] for k in ['title','tagline','updated'])
                if same_request and current and current['revision']==job.get('controls_revision'):
                    con.execute('UPDATE website_controls SET applied_revision=? WHERE domain_id=?',(current['revision'],uid))
                    con.execute("UPDATE website_requests SET state='published',message='HTTPS static site and controls applied',updated=? WHERE domain_id=?",(int(time.time()),uid))
                elif same_request and not current:
                    con.execute("UPDATE website_requests SET state='published',message='HTTPS static site published',updated=? WHERE domain_id=?",(int(time.time()),uid))

        except ValueError as e:status(uid,'needs_attention',str(e)[:500])
        except Exception:status(uid,'needs_attention','Server provisioning failed. Operator should inspect Nginx/Certbot status and retry.')
    manifest_path.write_text(json.dumps(manifest))

if __name__=='__main__':
    if os.geteuid()!=0:raise SystemExit('Run through the root provisioning service')
    STATE.mkdir(mode=0o700,parents=True,exist_ok=True)
    ROOT.mkdir(mode=0o755,parents=True,exist_ok=True)
    with open(STATE/'worker.lock','w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:sys.exit(0)
        run()
