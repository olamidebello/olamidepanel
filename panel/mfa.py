"""Authenticator TOTP with encrypted secrets, replay checks and single-use recovery."""
import base64,hashlib,hmac,json,secrets,struct,time
from urllib.parse import quote
from database import connect
from payments import cipher

def code(secret,step):
    digest=hmac.new(base64.b32decode(secret),struct.pack('>Q',step),hashlib.sha1).digest()
    offset=digest[-1]&15
    return str((struct.unpack('>I',digest[offset:offset+4])[0]&0x7fffffff)%1000000).zfill(6)

def match(secret,value,last_step=-1,now=None):
    if not isinstance(value,str) or len(value)!=6 or not value.isascii() or not value.isdigit():return None
    step=int(time.time() if now is None else now)//30
    for candidate in [step,step-1,step+1]:
        if candidate>last_step and hmac.compare_digest(code(secret,candidate),value):return candidate
    return None

def verify(uid,value):
    with connect() as con:
        row=con.execute('SELECT * FROM user_mfa WHERE user_id=? FOR UPDATE',(uid,)).fetchone()
        if not row or not row['enabled']:return True
        secret=cipher().decrypt(row['secret_cipher'].encode()).decode()
        step=match(secret,value,row['last_step'])
        if step is not None:
            con.execute('UPDATE user_mfa SET last_step=? WHERE user_id=?',(step,uid));return True
        codes=json.loads(row['recovery_hashes']);digest=hashlib.sha256(str(value).encode()).hexdigest()
        if digest in codes:
            codes.remove(digest);con.execute('UPDATE user_mfa SET recovery_hashes=? WHERE user_id=?',(json.dumps(codes),uid));return True
        return False

def status(uid):
    with connect() as con:row=con.execute('SELECT enabled FROM user_mfa WHERE user_id=?',(uid,)).fetchone()
    return {'enabled':bool(row and row['enabled'])}

def manage(user,body):
    uid=user['id'];action=body.get('action')
    if action=='setup':
        secret=base64.b32encode(secrets.token_bytes(20)).decode();encrypted=cipher().encrypt(secret.encode()).decode()
        with connect() as con:
            row=con.execute('SELECT enabled FROM user_mfa WHERE user_id=? FOR UPDATE',(uid,)).fetchone()
            if row and row['enabled']:raise ValueError('Disable existing two-factor authentication first')
            con.execute('INSERT INTO user_mfa(user_id,secret_cipher,enabled,recovery_hashes,last_step) VALUES(?,?,0,?,-1) ON DUPLICATE KEY UPDATE secret_cipher=VALUES(secret_cipher),recovery_hashes=VALUES(recovery_hashes),last_step=-1',(uid,encrypted,'[]'))
        return {'secret':secret,'uri':'otpauth://totp/'+quote('OlamidePanel:'+user['username'],safe='')+'?secret='+secret+'&issuer=OlamidePanel&algorithm=SHA1&digits=6&period=30'}
    if action=='enable':
        with connect() as con:
            row=con.execute('SELECT * FROM user_mfa WHERE user_id=? FOR UPDATE',(uid,)).fetchone()
            if not row or row['enabled']:raise ValueError('Start enrollment first')
            step=match(cipher().decrypt(row['secret_cipher'].encode()).decode(),body.get('code'))
            if step is None:raise ValueError('Invalid authenticator code')
            recovery=[secrets.token_hex(12) for _ in range(8)]
            con.execute('UPDATE user_mfa SET enabled=1,last_step=?,recovery_hashes=? WHERE user_id=?',(step,json.dumps([hashlib.sha256(c.encode()).hexdigest() for c in recovery]),uid))
            con.execute('UPDATE users SET session_version=session_version+1 WHERE id=?',(uid,))
        return {'enabled':True,'recovery_codes':recovery,'notice':'Save these codes now. Each works once. Sign in again using a fresh authenticator code.'}
    if action=='disable':
        if not verify(uid,body.get('code','')):raise ValueError('Invalid or previously used code')
        with connect() as con:
            con.execute('DELETE FROM user_mfa WHERE user_id=?',(uid,));con.execute('UPDATE users SET session_version=session_version+1 WHERE id=?',(uid,))
        return {'enabled':False,'notice':'Sign in again.'}
    raise ValueError('Unknown two-factor action')
