"""Administrative credential vault; no browser or application secret-export API."""
import fcntl
import json
import os
import re
import tempfile
import time
from pathlib import Path
from cryptography.fernet import Fernet

PROVIDERS = ('openai', 'anthropic', 'stripe', 'twilio', 'smtp', 'custom')

def public(row):
    return {k: v for k, v in row.items() if k != 'encrypted_secret'}

def validate(body):
    provider = body.get('provider', '')
    label = str(body.get('label', '')).strip()
    if provider not in PROVIDERS or not 1 <= len(label) <= 80:
        raise ValueError('Choose a provider and a label of 1–80 characters')
    domains = body.get('domains', [])
    if not isinstance(domains, list) or len(domains) > 200:
        raise ValueError('Supply at most 200 domain names')
    for domain in domains:
        if not isinstance(domain, str) or len(domain) > 253 or not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', domain):
            raise ValueError('Use lowercase domain names without URLs or wildcards')
    expires = body.get('expires', 0)
    if type(expires) is not int or expires < 0:
        raise ValueError('Invalid expiry time')
    enabled = body.get('enabled', False)
    if type(enabled) is not bool:
        raise ValueError('Enabled must be true or false')
    return dict(provider=provider, label=label, domains=sorted(set(domains)), expires=expires, enabled=enabled)

def handle(method, user, body=None):
    if user.get('role') not in ('root', 'super_admin'):
        return 403, {'error': 'Super-admin access required'}
    root = Path(os.environ.get('PANEL_DATA', '/var/lib/olamidepanel'))
    path = root / 'api-provider-keys.json'
    lockpath = root / 'api-provider-keys.lock'
    if path.is_symlink() or lockpath.is_symlink():
        raise ValueError('Invalid vault storage path')
    with lockpath.open('a') as lock:
        os.chmod(lockpath, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(path.read_text()) if path.exists() else {'next_id': 1, 'keys': []}
        if method == 'GET':
            now = int(time.time())
            return 200, {'providers': PROVIDERS, 'keys': [dict(public(r), expired=bool(r['expires'] and r['expires'] <= now)) for r in state['keys']], 'integration': 'vault_only'}
        body = body or {}
        action = body.get('action')
        key_id = body.get('id', 0)
        if type(key_id) is not int or key_id < 0:
            raise ValueError('Invalid key identifier')
        row = next((r for r in state['keys'] if r['id'] == key_id), None)
        if action == 'save':
            values = validate(body)
            if key_id and row is None:
                raise ValueError('Unknown saved key')
            secret = body.get('secret', '')
            if not isinstance(secret, str) or len(secret) > 8192 or any(c in secret for c in '\r\n\0'):
                raise ValueError('Invalid credential format')
            if not row and not secret:
                raise ValueError('Enter a credential for the new record')
            encrypted = None
            if secret:
                try:
                    cipher = Fernet(Path(os.environ.get('PANEL_PAYMENT_KEY', '/etc/olamidepanel/payment.key')).read_bytes().strip())
                    encrypted = cipher.encrypt(secret.encode()).decode()
                except Exception:
                    raise ValueError('Credential encryption unavailable; contact the server administrator') from None
            now = int(time.time())
            if not row:
                row = dict(id=state['next_id'], created=now, version=0)
                state['next_id'] += 1
                state['keys'].append(row)
            row.update(values, updated=now)
            if encrypted:
                row.update(encrypted_secret=encrypted, version=row['version'] + 1, rotated=now)
            event = 'rotate' if encrypted else 'settings'
        elif action == 'delete':
            if row is None:
                raise ValueError('Unknown saved key')
            state['keys'].remove(row)
            event = 'delete'
        else:
            raise ValueError('Unknown key action')
        fd, temp = tempfile.mkstemp(prefix='.provider-', dir=root)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(state, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            if os.path.exists(temp): os.unlink(temp)
        return 200, {'ok': True, 'id': row['id'], 'event': event, 'integration': 'vault_only'}


def resolve_openai(key_id, domain):
    """Server-only resolver; no HTTP route returns this value."""
    root = Path(os.environ.get('PANEL_DATA', '/var/lib/olamidepanel'))
    path = root / 'api-provider-keys.json'
    lockpath = root / 'api-provider-keys.lock'
    if path.is_symlink() or lockpath.is_symlink():
        raise ValueError('Invalid vault storage path')
    with lockpath.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        state = json.loads(path.read_text()) if path.exists() else {'keys': []}
        row = next((r for r in state['keys'] if r['id'] == key_id), None)
        if not row or row['provider'] != 'openai' or not row['enabled']:
            raise ValueError('Selected OpenAI credential is disabled or unavailable')
        if row['expires'] and row['expires'] <= int(time.time()):
            raise ValueError('Selected OpenAI credential has expired')
        if domain not in row['domains']:
            raise ValueError('OpenAI credential is not assigned to this domain')
        try:
            cipher = Fernet(Path(os.environ.get('PANEL_PAYMENT_KEY', '/etc/olamidepanel/payment.key')).read_bytes().strip())
            return cipher.decrypt(row['encrypted_secret'].encode()).decode()
        except Exception:
            raise ValueError('OpenAI credential cannot be decrypted') from None
