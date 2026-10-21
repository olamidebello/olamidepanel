"""Mailbox requests for explicitly operator-approved domain owners."""
import re
import subprocess
import time

DOMAIN = re.compile(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}')
ADDRESS = re.compile(r'[a-z0-9][a-z0-9._-]{0,63}@(?:[a-z0-9-]+\.)+[a-z]{2,63}')


def validate_address(value):
    if not isinstance(value, str) or len(value) > 254 or not ADDRESS.fullmatch(value):
        raise ValueError('Use a lowercase mailbox address with a valid local part')
    local, domain = value.split('@')
    if not DOMAIN.fullmatch(domain) or local in ('.', '..'):
        raise ValueError('Invalid mailbox domain')
    return domain


def hash_password(password):
    if not isinstance(password, str) or not 14 <= len(password) <= 256 or any(c in password for c in '\n\r\x00'):
        raise ValueError('Use a password of 14 to 256 characters without line breaks')
    result = subprocess.run(['/usr/bin/openssl', 'passwd', '-6', '-stdin'],
                            input=password+'\n', text=True, capture_output=True, check=True, timeout=15)
    value = '{SHA512-CRYPT}'+result.stdout.strip()
    if not re.fullmatch(r'\{SHA512-CRYPT\}\$6\$[./a-zA-Z0-9$]+', value):
        raise ValueError('Mailbox password hashing failed')
    return value


def permitted_domains(con, user):
    if user['role'] in ('root', 'super_admin'):
        return [r['domain'] for r in con.execute('SELECT domain FROM mail_delegations ORDER BY domain').fetchall()]
    # Inventory alone cannot establish mail ownership. A local operator must approve it.
    return [r['domain'] for r in con.execute(
        'SELECT m.domain FROM mail_delegations m JOIN domains d ON d.name=m.domain AND d.owner=m.owner WHERE m.owner=? ORDER BY m.domain',
        (user['id'],)).fetchall()]


def handle(method, user, connect, body=None):
    with connect() as con:
        domains = permitted_domains(con, user)
        if method == 'GET':
            accounts = con.execute('SELECT address,updated FROM mail_inventory ORDER BY address').fetchall()
            requests = con.execute('SELECT address,operation,state,summary,creator FROM mail_requests ORDER BY id DESC LIMIT 500').fetchall()
            return 200, {'domains': domains,
                         'accounts': [dict(r) for r in accounts if r['address'].split('@')[-1] in domains],
                         'requests': [dict(r) for r in requests if r['address'].split('@')[-1] in domains and (r['creator']==user['id'] or user['role'] in ('root','super_admin'))][:100]}
        if user['role'] == 'readonly':
            return 403, {'error': 'Read-only accounts cannot manage mailboxes'}
        address = body.get('address', '')
        domain = validate_address(address)
        if domain not in domains:
            return 403, {'error': 'Domain email management requires operator approval'}
        operation = body.get('operation')
        if operation not in ('upsert', 'disable'):
            raise ValueError('Choose upsert or disable')
        # Serialize request limits and duplicate submissions per actor.
        con.execute('SELECT id FROM users WHERE id=? FOR UPDATE', (user['id'],)).fetchone()
        pending = con.execute("SELECT id FROM mail_requests WHERE creator=? AND state IN ('queued','applying') LIMIT 20", (user['id'],)).fetchall()
        if len(pending) >= 20:
            return 429, {'error': 'Wait for pending mailbox changes to finish'}
        password_hash = hash_password(body.get('password')) if operation == 'upsert' else ''
        con.execute('INSERT INTO mail_requests(address,creator,operation,password_hash,created) VALUES(?,?,?,?,?)',
                    (address, user['id'], operation, password_hash, int(time.time())))
        con.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)',
                    (user['username'], 'mail:'+operation+':'+address, int(time.time())))
    return 202, {'state': 'queued', 'message': 'Awaiting mail worker; this does not confirm delivery readiness'}
