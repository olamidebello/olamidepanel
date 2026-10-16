"""OlamidePanel: unprivileged hosting control-plane starter."""
import argparse, base64, hashlib, hmac, json, os, re, secrets, shutil, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from database import connect, initialize_schema, IntegrityError

DATA = Path(os.environ.get('PANEL_DATA', '/var/lib/olamidepanel')).resolve()
STATIC = Path(__file__).parent / 'static'
TERMS_VERSION = '2026-10-15'
SESSIONS = {}
ROLE_LEVELS = {'root':100, 'super_admin':90, 'admin':70, 'reseller':50, 'user':20, 'readonly':10}
ROLE_PERMISSIONS = {role: ['files.read', 'domains.read', 'metrics.read'] + (['files.write', 'domains.write'] if level >= 20 else []) + (['users.manage', 'audit.read'] if level >= 90 else []) for role, level in ROLE_LEVELS.items()}

def allowed(user, permission):
    return permission in ROLE_PERMISSIONS.get(user['role'], [])


def db():
    return connect()

def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

def initialize():
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    initialize_schema()

def home(uid):
    path = DATA / 'homes' / str(uid)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path

def safe_path(uid, name):
    root = home(uid)
    path = (root / name).resolve()
    if not path.is_relative_to(root) or any(p.is_symlink() for p in [root / name, * (root / name).parents] if p.is_relative_to(root)):
        raise ValueError('Path is outside your account or traverses a symbolic link')
    return path

class Handler(BaseHTTPRequestHandler):
    server_version = 'OlamidePanel'
    def log_message(self, fmt, *args):
        pass
    def reply(self, status, value):
        payload = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers(); self.wfile.write(payload)
    def user(self):
        cookie = dict(x.strip().split('=', 1) for x in self.headers.get('Cookie', '').split(';') if '=' in x)
        session = SESSIONS.get(cookie.get('panel_session', ''))
        if not session or session['expires'] <= time.time(): return None
        with db() as con: current = con.execute('SELECT role, active, session_version FROM users WHERE id=?', (session['id'],)).fetchone()
        if not current or not current['active'] or current['session_version'] != session.get('session_version', 0): return None
        session['role'] = current['role']
        return session
    def do_GET(self):
        try:
            if self.path.startswith('/api/'):
                u = self.user()
                if not u: return self.reply(401, {'error':'Sign in required'})
                if self.path == '/api/profile':
                    with db() as con: row=con.execute('SELECT username,email,display_name,role FROM users WHERE id=?',(u['id'],)).fetchone()
                    return self.reply(200, dict(row))
                if self.path == '/api/me': return self.reply(200, {**{k:u[k] for k in ['id','username','role','csrf']}, 'permissions':ROLE_PERMISSIONS[u['role']]})
                if self.path == '/api/roles' and allowed(u, 'users.manage'):
                    return self.reply(200, [{'role':r,'level':v,'permissions':ROLE_PERMISSIONS[r]} for r,v in ROLE_LEVELS.items() if v <= ROLE_LEVELS[u['role']]])
                if self.path == '/api/users' and allowed(u, 'users.manage'):
                    with db() as con: rows=con.execute('SELECT id,username,role,active,email,display_name FROM users ORDER BY id').fetchall()
                    return self.reply(200, [dict(r) for r in rows])
                if self.path == '/api/metrics':
                    usage = shutil.disk_usage(DATA)
                    return self.reply(200, {'disk_total':usage.total,'disk_used':usage.used,'load':os.getloadavg(), 'hostname':os.uname().nodename})
                if self.path == '/api/domains':
                    with db() as con: rows = con.execute('SELECT id,name,created FROM domains WHERE owner=?',(u['id'],)).fetchall()
                    return self.reply(200, [dict(x) for x in rows])
                if self.path.startswith('/api/files?'):
                    from urllib.parse import parse_qs, urlsplit
                    q = parse_qs(urlsplit(self.path).query); path = safe_path(u['id'], q.get('path',[''])[0])
                    if path.is_file(): return self.reply(200, {'content':path.read_text()[:1048576]})
                    return self.reply(200, [{'name':x.name,'directory':x.is_dir(),'size':x.stat().st_size} for x in sorted(path.iterdir()) if not x.is_symlink()])
                if self.path == '/api/audit' and allowed(u, 'audit.read'):
                    with db() as con: rows=con.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 100').fetchall()
                    return self.reply(200,[dict(x) for x in rows])
                return self.reply(404, {'error':'Unknown operation'})
            name = {'/':'index.html','/app.js':'app.js','/style.css':'style.css','/terms':'terms.html','/privacy':'privacy.html','/copyright':'copyright.html'}.get(self.path)
            if not name: return self.reply(404, {'error':'Not found'})
            payload=(STATIC/name).read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', {'html':'text/html','js':'text/javascript','css':'text/css'}[name.split('.')[-1]])
            self.send_header('Content-Security-Policy', "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(payload)
        except (ValueError, OSError) as e: self.reply(400, {'error':str(e)})
    def do_POST(self):
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length > 1100000: return self.reply(413, {'error':'Request too large'})
            body=json.loads(self.rfile.read(length))
            if self.path == '/api/login':
                # Fixed-cost verification and a bounded per-address attempt window.
                now=time.time(); key=self.client_address[0]
                attempts=self.server.attempts.setdefault(key,[]); attempts[:]=[t for t in attempts if t>now-300]
                if len(attempts)>=10: return self.reply(429,{'error':'Too many attempts. Try in five minutes.'})
                attempts.append(now)
                with db() as con: row=con.execute('SELECT * FROM users WHERE username=?',(body.get('username',''),)).fetchone()
                digest=password_hash(body.get('password',''),row['salt'] if row else '00'*16)
                if not row or not row['active'] or not hmac.compare_digest(digest,row['password']): return self.reply(401,{'error':'Invalid credentials'})
                if body.get('accept_terms') is not True: return self.reply(400, {'error':'Confirm the Terms and acknowledge the Privacy Notice to sign in'})
                with db() as con:
                    con.execute('INSERT INTO legal_acceptances(user_id,version,accepted_at) VALUES(?,?,?) ON DUPLICATE KEY UPDATE accepted_at=VALUES(accepted_at)',(row['id'],TERMS_VERSION,int(now)))
                token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32)
                for old in list(SESSIONS):
                    if SESSIONS[old]['expires']<now: del SESSIONS[old]
                SESSIONS[token]={'id':row['id'],'username':row['username'],'role':row['role'],'csrf':csrf,'expires':now+3600,'session_version':row['session_version']}
                self.send_response(200)
                secure='; Secure' if os.environ.get('PANEL_SECURE_COOKIE','1')=='1' else ''
                self.send_header('Set-Cookie',f'panel_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=3600{secure}')
                self.end_headers(); return
            u=self.user()
            if not u: return self.reply(401,{'error':'Sign in required'})
            if not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),u['csrf']): return self.reply(403,{'error':'Invalid CSRF token'})
            if self.path == '/api/logout':
                for token in list(SESSIONS):
                    if SESSIONS[token] is u: del SESSIONS[token]
                return self.reply(200,{'ok':True})
            if self.path == '/api/domains':
                if not allowed(u, 'domains.write'): return self.reply(403, {'error':'Read-only access'})
                name=body['name'].lower().rstrip('.')
                if len(name)>253 or not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}',name): raise ValueError('Enter a valid domain name')
                with db() as con: con.execute('INSERT INTO domains(owner,name,created) VALUES(?,?,?)',(u['id'],name,int(time.time())))
                result={'ok':True,'status':'Recorded; web-server and DNS provisioning not implemented'}
            elif self.path == '/api/files':
                if not allowed(u, 'files.write'): return self.reply(403, {'error':'Read-only access'})
                path=safe_path(u['id'],body['path'])
                if path==home(u['id']): raise ValueError('Choose a file or folder')
                action=body['action']
                if action=='mkdir': path.mkdir()
                elif action=='write':
                    content=body['content']
                    if len(content.encode())>1048576: raise ValueError('File limit is 1 MiB')
                    path.write_text(content); path.chmod(0o600)
                elif action in ['rename','copy']:
                    target=safe_path(u['id'],body['destination'])
                    if not path.is_file() or target.exists(): raise ValueError('Choose a file and an unused destination')
                    if action=='rename': path.rename(target)
                    else:
                        if path.stat().st_size>1048576: raise ValueError('Copy limit is 1 MiB')
                        shutil.copyfile(path,target);target.chmod(0o600)
                elif action=='delete':
                    if path.is_dir(): path.rmdir()
                    else: path.unlink()
                else: raise ValueError('Unsupported file operation')
                result={'ok':True}
            elif self.path == '/api/users' and allowed(u, 'users.manage'):
                role=body.get('role','user')
                if role not in ROLE_LEVELS or ROLE_LEVELS[role] > ROLE_LEVELS[u['role']]: return self.reply(403, {'error':'Cannot grant a higher role'})
                create_user(body['username'],body['password'],role); result={'ok':True}
            elif self.path == '/api/domains/delete':
                if not allowed(u, 'domains.write'): return self.reply(403, {'error':'Read-only access'})
                with db() as con:
                    result=con.execute('DELETE FROM domains WHERE id=? AND owner=?',(int(body['id']),u['id']))
                    if result.rowcount!=1: raise ValueError('Unknown domain')
                result={'ok':True}
            elif self.path == '/api/users/action' and allowed(u, 'users.manage'):
                manage_user(u,body);result={'ok':True}
            elif self.path == '/api/profile':
                update_profile(u,body);result={'ok':True}
            elif self.path == '/api/users/update' and allowed(u, 'users.manage'):
                update_user(u, body); result={'ok':True}
            else: return self.reply(404,{'error':'Unknown operation'})
            with db() as con: con.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)',(u['username'],self.path+':'+body.get('action','create')+':target='+str(body.get('id',body.get('username','self'))),int(time.time())))
            self.reply(200,result)
        except (ValueError, KeyError, OSError, IntegrityError) as e: self.reply(400,{'error':str(e)})

def create_user(username,password,role):
    if not re.fullmatch('[a-z][a-z0-9_]{2,31}',username): raise ValueError('Username must be 3–32 lowercase letters, numbers, underscores')
    if len(password)<14: raise ValueError('Password must have at least 14 characters')
    if role not in ROLE_LEVELS: raise ValueError('Invalid role')
    salt=secrets.token_hex(16)
    with db() as con:
        uid=con.execute('INSERT INTO user_ids DEFAULT VALUES').lastrowid
        con.execute('INSERT INTO users(id,username,salt,password,role) VALUES(?,?,?,?,?)',(uid,username,salt,password_hash(password,salt),role))

def update_user(actor, body):
    uid=int(body['id']); role=body['role']; active=body['active']
    if role not in ROLE_LEVELS or type(active) is not bool: raise ValueError('Invalid role or active flag')
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        if not row: raise ValueError('Unknown user')
        if uid==actor['id']: raise ValueError('Use another privileged account to change your own access')
        if ROLE_LEVELS[row['role']] >= ROLE_LEVELS[actor['role']] or ROLE_LEVELS[role] >= ROLE_LEVELS[actor['role']]:
            raise ValueError('Only strictly lower access levels can be managed')
        con.execute('UPDATE users SET role=?,active=?,session_version=session_version+1 WHERE id=?',(role,int(active),uid))
    for token in list(SESSIONS):
        if SESSIONS[token]['id']==uid: del SESSIONS[token]

def validate_contact(body):
    email=body.get('email','').strip();name=body.get('display_name','').strip()
    if len(email)>254 or (email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email)): raise ValueError('Invalid email address')
    if len(name)>100: raise ValueError('Display name too long')
    return email,name

def update_profile(actor,body):
    email,name=validate_contact(body)
    with db() as con:
        if body.get('password'):
            row=con.execute('SELECT * FROM users WHERE id=?',(actor['id'],)).fetchone()
            if not hmac.compare_digest(password_hash(body.get('current_password',''),row['salt']),row['password']): raise ValueError('Current password is incorrect')
            if len(body['password'])<14: raise ValueError('Password must have at least 14 characters')
            salt=secrets.token_hex(16)
            con.execute('UPDATE users SET salt=?,password=?,session_version=session_version+1 WHERE id=?',(salt,password_hash(body['password'],salt),actor['id']))
        con.execute('UPDATE users SET email=?,display_name=? WHERE id=?',(email,name,actor['id']))

def manage_user(actor,body):
    uid=int(body['id']); action=body['action']
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        if not row or uid==actor['id'] or ROLE_LEVELS[row['role']]>=ROLE_LEVELS[actor['role']]: raise ValueError('Only lower-level accounts may be managed')
        if action=='profile':
            email,name=validate_contact(body)
            con.execute('UPDATE users SET email=?,display_name=? WHERE id=?',(email,name,uid))
        elif action=='password':
            password=body['password']
            if len(password)<14: raise ValueError('Password must have at least 14 characters')
            salt=secrets.token_hex(16)
            con.execute('UPDATE users SET salt=?,password=?,session_version=session_version+1 WHERE id=?',(salt,password_hash(password,salt),uid))
        elif action=='revoke_sessions': con.execute('UPDATE users SET session_version=session_version+1 WHERE id=?',(uid,))
        elif action=='delete':
            if row['active']: raise ValueError('Suspend the account before deletion')
            if body.get('confirmation')!=row['username']: raise ValueError('Type the username to confirm deletion')
            con.execute('DELETE FROM domains WHERE owner=?',(uid,))
            con.execute('DELETE FROM users WHERE id=?',(uid,))
            # Account files remain on disk for operator-controlled recovery/retention.
        else: raise ValueError('Unknown account operation')

def provision_user(body):
    username=body['username']; role=body.get('role','user'); active=body.get('active',True)
    if role not in ROLE_LEVELS or type(active) is not bool: raise ValueError('Invalid provisioning data')
    with db() as con: row=con.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
    if row:
        if row['role']!=role or bool(row['active'])!=active:
            # Local bootstrap can administer root, while preserving a usable top-level account.
            with db() as con:
                con.execute('BEGIN IMMEDIATE')
                if row['role']=='root' and row['active'] and (role!='root' or not active):
                    if con.execute("SELECT COUNT(*) AS total FROM users WHERE role='root' AND active=1").fetchone()['total']<=1:
                        raise ValueError('Cannot remove the last active panel root')
                con.execute('UPDATE users SET role=?,active=?,session_version=session_version+1 WHERE id=?',(role,int(active),row['id']))
            changed=True
        else: changed=False
    else:
        create_user(username,body['password'],role)
        with db() as con: con.execute('UPDATE users SET active=? WHERE username=?',(int(active),username))
        changed=True
    if changed:
        with db() as con: con.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)',('local-provision','provision user '+username,int(time.time())))
    return {'changed':changed}

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--create-admin'); parser.add_argument('--provision-user',action='store_true'); parser.add_argument('--port',type=int,default=8090); args=parser.parse_args(); initialize()
    if args.provision_user:
        import sys
        try: print(json.dumps(provision_user(json.load(sys.stdin))))
        except (ValueError, KeyError, IntegrityError):
            print('Invalid account configuration or protected last root',file=sys.stderr);sys.exit(1)
    elif args.create_admin:
        import getpass
        create_user(args.create_admin,getpass.getpass('New admin password: '),'root')
    else:
        server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler); server.attempts={}; server.serve_forever()
