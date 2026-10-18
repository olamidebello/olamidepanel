#!/usr/bin/python3
"""Root broker: fixed adapters, fixed prerequisites, sequential auditable jobs."""
import ast
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
sys.path.insert(0,'/opt/olamidepanel/panel')
import module_manager as manager
from database import connect
SOURCE=Path('/opt/olamidepanel-module-source')
PANEL=Path('/opt/olamidepanel/panel')
PYTHON='/opt/olamidepanel/venv/bin/python'

def run(args,timeout=180):
 subprocess.run(args,check=True,timeout=timeout,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def check(adapter):
 files,deps=manager.ADAPTERS[adapter];checks={}
 for name in files:
  path=PANEL/name
  try:
   checks[name]=path.is_file()
   if path.suffix=='.py':ast.parse(path.read_text())
   if path.suffix=='.json':json.loads(path.read_text())
   trusted=SOURCE/'panel'/name
   checks['source:'+name]=trusted.is_file() and path.is_file() and hashlib.sha256(path.read_bytes()).digest()==hashlib.sha256(trusted.read_bytes()).digest()
  except (OSError,ValueError,SyntaxError):checks[name]=False
 for name in deps:
  result=subprocess.run([PYTHON,'-c','import importlib; importlib.import_module('+repr(name)+')'],capture_output=True,timeout=20)
  checks['dependency:'+name]=result.returncode==0
 return checks

def repair(adapter):
 files,deps=manager.ADAPTERS[adapter]
 # Only fixed official Debian packages and the installed project's pinned requirements.
 run(['apt-get','update'],300)
 run(['apt-get','install','-y','python3-venv','nginx','curl','ca-certificates'],600)
 requirements=SOURCE/'requirements.txt'
 if requirements.is_symlink() or requirements.stat().st_uid!=0 or requirements.stat().st_mode&0o022:raise ValueError('Untrusted requirements')
 run([PYTHON,'-m','pip','install','-r',str(requirements)],600)
 changed=False
 for name in files:
  src=SOURCE/'panel'/name;dst=PANEL/name
  if src.is_symlink() or src.stat().st_uid!=0 or src.stat().st_mode&0o022:raise ValueError('Untrusted module source')
  if src.suffix=='.py':ast.parse(src.read_text())
  if dst.is_symlink():raise ValueError('Refusing symlink destination')
  if not dst.exists() or dst.read_bytes()!=src.read_bytes():
   backup=Path('/var/backups/olamidepanel-modules')/str(int(time.time()))/name
   backup.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
   if dst.exists():shutil.copy2(dst,backup)
   dst.parent.mkdir(parents=True,exist_ok=True)
   temporary=dst.with_name(dst.name+'.module-tmp');temporary.write_bytes(src.read_bytes());os.chmod(temporary,0o644);temporary.replace(dst);changed=True
 if changed:run(['systemctl','restart','olamidepanel.service'],60)
 return check(adapter)

def main():
 with open('/run/olamidepanel-modules.lock','w') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return
  with connect() as c:
   c.execute("UPDATE module_jobs SET state='uncertain',finished=?,summary='Runner interrupted; inspect before resubmitting' WHERE state='running'",(int(time.time()),))
   job=c.execute("SELECT j.*,u.role,u.active FROM module_jobs j JOIN users u ON u.id=j.creator WHERE j.state='queued' ORDER BY j.id LIMIT 1 FOR UPDATE").fetchone()
   if not job:
    # Re-audit installed adapters every 15 minutes. Repair failed checks at most hourly.
    statuses={r['adapter']:dict(r) for r in c.execute('SELECT * FROM module_status').fetchall()}
    owner=c.execute("SELECT id FROM users WHERE active=1 AND role IN ('root','super_admin') ORDER BY id LIMIT 1").fetchone()
    if not owner:return
    now=int(time.time())
    for adapter in manager.ADAPTERS:
     previous=statuses.get(adapter,{})
     if now-int(previous.get('checked_at',0))<900:continue
     checks=check(adapter)
     operation='repair' if not all(checks.values()) and now-int(previous.get('last_repair',0))>=3600 else 'audit'
     c.execute('INSERT INTO module_jobs(adapter,operation,creator,created,summary) VALUES(?,?,?,?,?)',(adapter,operation,owner['id'],now,'Automatic scheduled check'))
     return
    return
   valid=job['role'] in ('root','super_admin') and job['active'] and job['adapter'] in manager.ADAPTERS and job['operation'] in ('audit','repair')
   c.execute('UPDATE module_jobs SET state=? WHERE id=?',('running' if valid else 'rejected',job['id']))
  if not valid:return
  state='completed';summary='Adapter prerequisites and source checks passed; implementation coverage is unchanged.'
  try:
   checks=repair(job['adapter']) if job['operation']=='repair' else check(job['adapter'])
   if not all(checks.values()):state='needs_attention';summary='Adapter checks failed; inspect module status.'
   with connect() as c:c.execute('INSERT INTO module_status(adapter,checked_at,last_repair,state,checks) VALUES(?,?,?,?,?) ON DUPLICATE KEY UPDATE checked_at=VALUES(checked_at),last_repair=IF(VALUES(last_repair)>0,VALUES(last_repair),last_repair),state=VALUES(state),checks=VALUES(checks)',(job['adapter'],int(time.time()),int(time.time()) if job['operation']=='repair' else 0,state,json.dumps(checks)))
  except Exception as error:
   state='failed';checks={'operation':False};
   with connect() as c:c.execute('INSERT INTO module_status(adapter,checked_at,last_repair,state,checks) VALUES(?,?,?,?,?) ON DUPLICATE KEY UPDATE checked_at=VALUES(checked_at),last_repair=VALUES(last_repair),state=VALUES(state),checks=VALUES(checks)',(job['adapter'],int(time.time()),int(time.time()),state,json.dumps(checks)))
   summary='Module operation failed: '+type(error).__name__+'. Inspect server prerequisites and trusted source.'
  with connect() as c:
   c.execute('UPDATE module_jobs SET state=?,finished=?,summary=? WHERE id=?',(state,int(time.time()),summary,job['id']))
  print(json.dumps({'job':job['id'],'adapter':job['adapter'],'state':state,'summary':summary}),flush=True)

if __name__=='__main__':main()
