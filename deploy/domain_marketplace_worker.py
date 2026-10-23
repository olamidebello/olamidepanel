#!/usr/bin/env python3
"""Root broker: deploy fixed storefront routes into existing domain vhosts only."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
sys.path.insert(0,'/opt/olamidepanel/panel')
from database import connect
from domain_marketplace import assigned

BASE=Path('/var/lib/olamide-domain-marketplaces')
FRAGMENTS=Path('/etc/nginx/olamide-marketplaces')

def run(args):
    return subprocess.run(args,check=True,capture_output=True,text=True,timeout=30).stdout

def server_blocks(text,domain):
    # Tokenize braces, quoted values and comments; match exact server_name tokens.
    tokens=[m for m in re.finditer(r'#[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{};]|[^\s{};]+',text) if not m.group().startswith('#')]
    found=[]
    for i,t in enumerate(tokens[:-1]):
        if t.group()!='server' or tokens[i+1].group()!='{':continue
        depth=1;j=i+2;names=[]
        while j<len(tokens) and depth:
            value=tokens[j].group()
            if value=='{':depth+=1
            elif value=='}':depth-=1
            elif depth==1 and value=='server_name':
                k=j+1
                while k<len(tokens) and tokens[k].group()!=';':
                    names.append(tokens[k].group().strip('\"\''));k+=1
            j+=1
        if depth:raise ValueError('Unbalanced Nginx configuration')
        if domain in names:found.append((tokens[i+1].end(),tokens[j-1].end()))
    return found

def configured_files(domain):
    dump=run(['nginx','-T'])
    parts=re.split(r'^# configuration file (.+):\s*$',dump,flags=re.M)
    result=[]
    for i in range(1,len(parts),2):
        path=Path(parts[i].strip()).resolve()
        if not path.is_relative_to(Path('/etc/nginx')) or not path.is_file():continue
        text=path.read_text()
        blocks=server_blocks(text,domain)
        if blocks:
            stat=path.stat()
            if stat.st_uid!=0 or stat.st_mode & 0o022:raise ValueError('Vhost is not root-owned and protected')
            result.append((path,text,blocks))
    if not result:raise ValueError('No exact existing Nginx vhost for domain; configure hosting first')
    return result

def deploy(domain,operation):
    if not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}',domain):raise ValueError('Invalid domain')
    configs=configured_files(domain)
    fragment=FRAGMENTS/(domain+'.conf')
    include='\n  include '+str(fragment)+';\n'
    originals={p:t for p,t,_ in configs}
    old=fragment.read_text() if fragment.exists() else None
    stamp=BASE/'backups'/str(time.time_ns())
    stamp.mkdir(parents=True,mode=0o700)
    for path,text,blocks in configs:
        (stamp/(hashlib.sha256(str(path).encode()).hexdigest()+'.conf')).write_text(text)
        for start,end in blocks:
            block=text[start:end]
            if include.strip() not in block and re.search(r'\blocation\s+[^;{}]*?/marketplace',block):
                raise ValueError('Existing marketplace route requires operator review')
    try:
        action='proxy_pass http://127.0.0.1:8090/storefront/'+domain+';' if operation=='deploy' else 'return 404;'
        fragment.write_text('# Managed domain storefront\nlocation = /marketplace { '+action+' }\nlocation = /marketplace/ { return 308 /marketplace; }\n')
        fragment.chmod(0o644)
        for path,text,blocks in configs:
            for start,end in reversed(blocks):
                if include.strip() not in text[start:end]:text=text[:start]+include+text[start:]
            path.write_text(text)
        run(['nginx','-t']);run(['systemctl','reload','nginx'])
    except Exception:
        for path,text in originals.items():path.write_text(text)
        if old is None:fragment.unlink(missing_ok=True)
        else:fragment.write_text(old)
        run(['nginx','-t']);run(['systemctl','reload','nginx'])
        raise


def main():
    os.umask(0o077)
    with (BASE/'worker.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        with connect() as con:
            con.execute("UPDATE domain_marketplace_jobs SET state='needs_attention',message='Worker interrupted; submit deployment again',finished=? WHERE state='running'",(int(time.time()),))
        for _ in range(1000):
            with connect() as con:
                job=con.execute("SELECT * FROM domain_marketplace_jobs WHERE state='queued' ORDER BY id LIMIT 1 FOR UPDATE").fetchone()
                if not job:return
                con.execute("UPDATE domain_marketplace_jobs SET state='running' WHERE id=?",(job['id'],))
            try:
                with connect() as con:
                    user=con.execute('SELECT role,active FROM users WHERE id=?',(job['creator'],)).fetchone()
                    if not user or not user['active'] or user['role'] not in ('root','super_admin'):raise ValueError('Requester no longer authorized')
                    ids=json.loads(job['gateway_ids'])
                    gateways={g['id'] for g in con.execute('SELECT id FROM payment_gateways WHERE owner_id=0 AND enabled=1').fetchall()}
                    if job['operation']=='deploy' and (not ids or not set(ids)<=gateways):raise ValueError('Selected operator gateways are no longer enabled')
                deploy(job['domain'],job['operation'])
                with connect() as con:
                    now=int(time.time());enabled=job['operation']=='deploy'
                    con.execute("INSERT INTO domain_marketplaces(domain,enabled,gateway_ids,state,message,updated) VALUES(?,?,?,'deployed','',?) ON DUPLICATE KEY UPDATE enabled=VALUES(enabled),gateway_ids=VALUES(gateway_ids),state=VALUES(state),message='',updated=VALUES(updated)",(job['domain'],enabled,job['gateway_ids'],now))
                if enabled:
                    run(['curl','--fail','--silent','--show-error','--max-time','15','--resolve',job['domain']+':443:127.0.0.1','https://'+job['domain']+'/marketplace','-o','/dev/null'])
                state,message='completed','Marketplace enabled and local HTTPS verified' if enabled else 'Marketplace disabled'
            except Exception as exc:
                state='needs_attention'
                message=str(exc) if isinstance(exc,ValueError) else 'Deployment or HTTPS check failed; inspect host configuration'
                with connect() as con:
                    con.execute("UPDATE domain_marketplaces SET state='needs_attention',message=? WHERE domain=?",(message,job['domain']))
            with connect() as con:
                con.execute('UPDATE domain_marketplace_jobs SET state=?,message=?,finished=? WHERE id=?',(state,message,int(time.time()),job['id']))
                con.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)',('domain-marketplace-worker',state+':'+job['domain'],int(time.time())))

if __name__=='__main__':main()
