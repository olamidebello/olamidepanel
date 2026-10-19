"""Administrator-only Namecheap accounts and conservative DNS provisioning."""
import ipaddress
import json
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from payments import cipher
from database import connect

NS = {'n': 'https://api.namecheap.com/xml.response'}
LOCK = threading.Lock()

def parse_response(payload):
    root = ET.fromstring(payload)
    namespaces = ('http://api.namecheap.com/xml.response', NS['n'])
    for node in root.iter():
        for namespace in namespaces:
            prefix = '{' + namespace + '}'
            if node.tag.startswith(prefix):
                local = node.tag[len(prefix):]
                node.tag = '{' + NS['n'] + '}' + ('host' if local == 'Host' else local)
                break
    if root.tag != '{' + NS['n'] + '}ApiResponse':
        raise ValueError('Unrecognized Namecheap XML response.')
    return root

def call(account, command, **params):
    endpoint = 'https://api.namecheap.com/xml.response' if account['mode'] == 'production' else 'https://api.sandbox.namecheap.com/xml.response'
    args = {k: account[k] for k in ('ApiUser', 'ApiKey', 'UserName', 'ClientIp')}
    args.update(Command='namecheap.' + command, **params)
    try:
        request = urllib.request.Request(endpoint, data=urllib.parse.urlencode(args).encode())
        with urllib.request.urlopen(request, timeout=30) as response:
            root = parse_response(response.read(2_000_000))
        if root.get('Status') != 'OK':
            raise ValueError('Namecheap rejected the request. Check API access, credentials, IP allowlist and domain DNS provider.')
        return root
    except ValueError:
        raise
    except Exception:
        raise ValueError('Namecheap request failed. Check connectivity and API configuration.') from None

def public(row):
    return {k: row[k] for k in ('id', 'label', 'mode', 'updated')} | {'credentials_stored': True}

def provision(account, body):
    sld, tld = body.get('sld', '').strip().lower(), body.get('tld', '').strip().lower()
    label = r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'
    if not re.fullmatch(label, sld) or not re.fullmatch(label + r'(?:\.' + label + r')*', tld):
        raise ValueError('Enter the registered domain SLD and TLD, for example example and co.uk.')
    names = list(dict.fromkeys(x.strip().lower() for x in body.get('hosts', '').split(',')))
    if not 1 <= len(names) <= 100 or any(not re.fullmatch(r'@|\*|' + label + r'(?:\.' + label + r')*', n) for n in names):
        raise ValueError('Enter up to 100 comma-separated host names, such as @, www, weathernigeria.')
    address = str(ipaddress.IPv4Address(body.get('address', '')))
    params = dict(SLD=sld, TLD=tld)
    def read():
        result = call(account, 'domains.dns.getHosts', **params).find('.//n:DomainDNSGetHostsResult', NS)
        if result is None or result.get('IsUsingOurDNS', '').lower() != 'true':
            raise ValueError('The domain must use Namecheap authoritative DNS.')
        return result, [dict(h.attrib) for h in result.findall('n:host', NS)]
    with LOCK:
        result, records = read()
        supported = {'A', 'AAAA', 'ALIAS', 'CNAME', 'MX', 'MXE', 'NS', 'TXT', 'URL', 'URL301', 'FRAME'}
        if any(r.get('Type') not in supported or r.get('IsDDNSEnabled', 'false').lower() == 'true' for r in records):
            raise ValueError('Unsupported records or Dynamic DNS require manual provisioning to preserve metadata.')
        updated = [dict(r) for r in records]
        for name in names:
            same = [r for r in updated if r['Name'].lower() == name]
            if any(r['Type'] != 'A' for r in same) or len(same) > 1:
                raise ValueError('Conflicting DNS records for ' + name)
            if same:
                same[0]['Address'] = address
            else:
                updated.append(dict(Name=name, Type='A', Address=address, TTL='300'))
        if updated == records:
            return {'status': 'DNS already configured'}
        args = dict(params)
        if any(r['Type'] in ('MX', 'MXE') for r in records):
            if not result.get('EmailType'):
                raise ValueError('Email metadata unavailable; use manual DNS provisioning.')
            args['EmailType'] = result.get('EmailType')
        for i, record in enumerate(updated, 1):
            for source, target in [('Name','HostName'), ('Type','RecordType'), ('Address','Address'), ('TTL','TTL'), ('MXPref','MXPref')]:
                if source in record:
                    args[target + str(i)] = record[source]
        fresh, hosts = read()
        if hosts != records or fresh.get('EmailType') != result.get('EmailType'):
            raise ValueError('DNS changed during provisioning. Refresh and retry.')
        reply = call(account, 'domains.dns.setHosts', **args).find('.//n:DomainDNSSetHostsResult', NS)
        if reply is None or reply.get('IsSuccess', '').lower() != 'true':
            raise ValueError('Namecheap did not confirm the DNS update.')
        _, hosts = read()
        expected = sorted((r['Name'].lower(), r['Type'], r['Address'], r.get('TTL', '1800'), r.get('MXPref', '') if r['Type'] in ('MX','MXE') else '') for r in updated)
        actual = sorted((r['Name'].lower(), r['Type'], r['Address'], r.get('TTL', '1800'), r.get('MXPref', '') if r['Type'] in ('MX','MXE') else '') for r in hosts)
        if actual != expected:
            raise ValueError('DNS update submitted, but verification differed. Inspect the zone before retrying.')
        return {'status': 'DNS records provisioned and verified', 'domain': sld + '.' + tld}

def handle(method, user, body=None):
    if user['role'] not in ('root', 'super_admin'):
        return 403, {'error': 'Super-admin access required'}
    body = body or {}
    with connect() as con:
        if method == 'GET':
            return 200, [public(r) for r in con.execute('SELECT id,label,mode,updated FROM namecheap_accounts ORDER BY id').fetchall()]
        action = body.get('action')
        row = con.execute('SELECT * FROM namecheap_accounts WHERE id=?', (int(body.get('id') or 0),)).fetchone()
        if action == 'save':
            label = str(body.get('label', '')).strip()
            mode = body.get('mode')
            if not label or len(label) > 120 or mode not in ('sandbox', 'production'):
                raise ValueError('Enter an account label and choose sandbox or production.')
            previous = json.loads(cipher().decrypt(row['credentials'].encode())) if row else {}
            account = {k: str(body.get(k, '')).strip() or previous.get(k, '') for k in ('ApiUser', 'ApiKey', 'UserName', 'ClientIp')}
            account['UserName'] = account['UserName'] or account['ApiUser']
            if not all(account.values()) or any(len(v) > 256 for v in account.values()):
                raise ValueError('API user, API key and allowlisted IPv4 are required.')
            ipaddress.IPv4Address(account['ClientIp'])
            encrypted = cipher().encrypt(json.dumps(account).encode()).decode()
            values = (label, mode, encrypted, int(time.time()))
            if row:
                con.execute('UPDATE namecheap_accounts SET label=?,mode=?,credentials=?,updated=? WHERE id=?', values + (row['id'],))
            else:
                con.execute('INSERT INTO namecheap_accounts(label,mode,credentials,updated) VALUES(?,?,?,?)', values)
            result = {'status': 'Namecheap account saved'}
        else:
            if not row:
                raise ValueError('Select a saved Namecheap account.')
            if action == 'delete':
                con.execute('DELETE FROM namecheap_accounts WHERE id=?', (row['id'],))
                result = {'status': 'Account removed from panel'}
            else:
                account = json.loads(cipher().decrypt(row['credentials'].encode())) | {'mode': row['mode']}
                if action in ('test', 'domains'):
                    page = int(body.get('page', 1))
                    if page < 1 or page > 100000:
                        raise ValueError('Invalid page')
                    root = call(account, 'domains.getList', Page=page, PageSize=100)
                    result = {'status': 'Connection successful', 'domains': [dict(r.attrib) for r in root.findall('.//n:DomainGetListResult/n:Domain', NS)], 'page': page, 'total': root.findtext('.//n:Paging/n:TotalItems', default='0', namespaces=NS)}
                elif action == 'provision':
                    result = provision(account, body)
                else:
                    raise ValueError('Unknown Namecheap operation')
        con.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)', (user['username'], 'namecheap:' + action, int(time.time())))
    return 200, result
