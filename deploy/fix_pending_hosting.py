"""Run independent hosting repairs without hiding unresolved work."""
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys

def retry_time(text):
    dates = re.findall(r'retry after (\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d) UTC', text)
    return max((datetime.datetime.fromisoformat(x).replace(tzinfo=datetime.timezone.utc)
                for x in dates), default=None)

def main():
    root = Path(sys.argv[1]).resolve()
    logs = Path('/var/log/olamidepanel-repair')
    logs.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(logs, 0o700)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    results = []
    def record(name, status, detail):
        results.append(dict(task=name, status=status, detail=detail))
    def run(name, args):
        p = subprocess.run(args, text=True, capture_output=True)
        path = logs / (stamp + '-' + name + '.log')
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as out:
            out.write(p.stdout + '\n' + p.stderr)
        record(name, 'passed' if p.returncode == 0 else 'failed', str(path))
        return p
    def play(name, file, extra=None):
        args = ['ansible-playbook','-i','localhost,','-c','local',str(root/file)]
        if extra:
            args += ['-e', json.dumps(extra)]
        return run(name,args)
    email = os.environ.get('PENDING_EMAIL','dobcalldemo@gmail.com')
    # Only byte-identical nginx aliases can be removed without selecting a site.
    nginx = run('nginx-safe-repair',['python3',str(root.parent/'deploy/weather/nginx_repair.py')])
    if nginx.returncode == 0:
        payload = json.loads(nginx.stdout)
        if 'conflicting server name' in payload.get('warnings',''):
            record('nginx-conflicts','blocked','Distinct vhosts conflict. Select the canonical AfricanCreativity configuration before disabling others.')
        if payload.get('changed'):
            run('nginx-reload',['systemctl','reload','nginx'])

    log = Path('/var/log/letsencrypt/letsencrypt.log')
    retry = retry_time(log.read_text(errors='replace') if log.exists() else '')
    limited = retry is not None and datetime.datetime.now(datetime.timezone.utc) < retry
    cert = Path('/etc/letsencrypt/live/africandroid-world-wildcard/fullchain.pem')
    credentials = bool(os.environ.get('CLOUDFLARE_API_TOKEN') and os.environ.get('CLOUDFLARE_ZONE_ID'))
    if credentials and not limited:
        play('wildcard','enable-africandroid-wildcard.yml',{'wildcard_email':email})
    elif not cert.exists():
        reason = 'CA retry time: ' + retry.isoformat() if limited else 'Configure active authoritative Cloudflare DNS, Zone ID and scoped token.'
        record('wildcard','blocked',reason)
    # Avoid per-country requests while the registered-domain limit is active.
    if cert.exists() or not limited:
        play('weather','provision-africa-weather.yml',{
            'dns_provider':'manual','tls_email':email,
            'weather_only': [] if cert.exists() else ['cotedivoire','tunisia','uganda','zambia','zimbabwe']})
    else:
        record('weather','blocked','Waiting for wildcard issuance or CA retry time; existing sites retained.')
    # Always run these after rebuilding weather HTML, even when TLS work failed.
    play('adsense','install-africandroid-adsense.yml')
    play('hosting-gui','update-weather-domain-gui.yml',{
        'panel_install':os.environ.get('PENDING_PANEL_INSTALL','/opt/olamidepanel')})
    report = dict(complete=all(x['status']=='passed' for x in results),
                  changed=any(x['status']=='passed' for x in results), results=results)
    path = logs / (stamp + '-summary.json')
    path.write_text(json.dumps(report,indent=2))
    os.chmod(path,0o600)
    print(json.dumps(report))

if __name__ == '__main__':
    main()
