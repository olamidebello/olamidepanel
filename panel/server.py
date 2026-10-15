"""OlamidePanel: unprivileged hosting control-plane starter."""
import argparse, base64, hashlib, hmac, json, os, re, secrets, shutil, sqlite3, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

DATA = Path(os.environ.get('PANEL_DATA', '/var/lib/olamidepanel')).resolve()
STATIC = Path(__file__).parent / 'static'
SESSIONS = {}

def db():
    con = sqlite3.connect(DATA / 'panel.db')
    con.row_factory = sqlite3.Row
    return con

def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

def initialize():
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    with db() as con:
        con.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, salt TEXT, password TEXT, role TEXT);
CREATE TABLE IF NOT EXISTS domains(id INTEGER PRIMARY KEY, owner INTEGER, name TEXT UNIQUE, created INTEGER);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, actor TEXT, action TEXT, created INTEGER);''')

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
        return session if session and session['expires'] > time.time() else None
    def do_GET(self):
        try:
            if self.path.startswith('/api/'):
                u = self.user()
                if not u: return self.reply(401, {'error':'Sign in required'})
                if self.path == '/api/me': return self.reply(200, {k:u[k] for k in ['id','username','role','csrf']})
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
                if self.path == '/api/audit' and u['role']=='admin':
                    with db() as con: rows=con.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 100').fetchall()
                    return self.reply(200,[dict(x) for x in rows])
                return self.reply(404, {'error':'Unknown operation'})
            name = {'/':'index.html','/app.js':'app.js','/style.css':'style.css'}.get(self.path)
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
                if not row or not hmac.compare_digest(digest,row['password']): return self.reply(401,{'error':'Invalid credentials'})
                token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32)
                for old in list(SESSIONS):
                    if SESSIONS[old]['expires']<now: del SESSIONS[old]
                SESSIONS[token]={'id':row['id'],'username':row['username'],'role':row['role'],'csrf':csrf,'expires':now+3600}
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
                name=body['name'].lower().rstrip('.')
                if len(name)>253 or not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}',name): raise ValueError('Enter a valid domain name')
                with db() as con: con.execute('INSERT INTO domains(owner,name,created) VALUES(?,?,?)',(u['id'],name,int(time.time())))
                result={'ok':True,'status':'Recorded; web-server and DNS provisioning not implemented'}
            elif self.path == '/api/files':
                path=safe_path(u['id'],body['path'])
                if path==home(u['id']): raise ValueError('Choose a file or folder')
                action=body['action']
                if action=='mkdir': path.mkdir()
                elif action=='write':
                    content=body['content']
                    if len(content.encode())>1048576: raise ValueError('File limit is 1 MiB')
                    path.write_text(content); path.chmod(0o600)
                elif action=='delete':
                    if path.is_dir(): path.rmdir()
                    else: path.unlink()
                else: raise ValueError('Unsupported file operation')
                result={'ok':True}
            elif self.path == '/api/users' and u['role']=='admin':
                create_user(body['username'],body['password'],body.get('role','user')); result={'ok':True}
            else: return self.reply(404,{'error':'Unknown operation'})
            with db() as con: con.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)',(u['username'],self.path+':'+body.get('action','create'),int(time.time())))
            self.reply(200,result)
        except (ValueError, KeyError, OSError, sqlite3.IntegrityError) as e: self.reply(400,{'error':str(e)})

def create_user(username,password,role):
    if not re.fullmatch('[a-z][a-z0-9_]{2,31}',username): raise ValueError('Username must be 3–32 lowercase letters, numbers, underscores')
    if len(password)<14: raise ValueError('Password must have at least 14 characters')
    if role not in ['admin','user']: raise ValueError('Invalid role')
    salt=secrets.token_hex(16)
    with db() as con: con.execute('INSERT INTO users(username,salt,password,role) VALUES(?,?,?,?)',(username,salt,password_hash(password,salt),role))

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--create-admin'); parser.add_argument('--port',type=int,default=8090); args=parser.parse_args(); initialize()
    if args.create_admin:
        import getpass
        create_user(args.create_admin,getpass.getpass('New admin password: '),'admin')
    else:
        server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler); server.attempts={}; server.serve_forever()
