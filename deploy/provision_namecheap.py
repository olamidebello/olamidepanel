"""Local Ansible adapter using encrypted accounts saved by panel super admins."""
import json
import sys
from pathlib import Path
sys.path.insert(0, '/opt/olamidepanel/panel')
from database import connect
from payments import cipher
from namecheap import provision
import time


def run(config):
    account_id = int(config['account_id'])
    zones = config['zones']
    if not isinstance(zones, list) or not zones or len(zones) > 100:
        raise ValueError('Supply 1–100 DNS zones.')
    # Validate all zone inputs before the first external mutation.
    import ipaddress, re
    label = r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'
    for zone in zones:
        if not isinstance(zone, dict):
            raise ValueError('Each zone must be an object.')
        for key in ('sld', 'tld', 'hosts', 'address'):
            if not isinstance(zone.get(key), str) or not zone[key].strip():
                raise ValueError('Each zone needs sld, tld, hosts and address strings.')
        if not re.fullmatch(label, zone['sld']) or not re.fullmatch(label + r'(?:\.' + label + ')*', zone['tld']):
            raise ValueError('Invalid registered domain SLD or TLD.')
        hosts = zone['hosts'].split(',')
        if not 1 <= len(hosts) <= 100 or any(not re.fullmatch(r'@|\*|' + label + r'(?:\.' + label + ')*', h.strip().lower()) for h in hosts):
            raise ValueError('Invalid host list.')
        ipaddress.IPv4Address(zone['address'])
    with connect() as con:
        row = con.execute('SELECT * FROM namecheap_accounts WHERE id=?', (account_id,)).fetchone()
    if not row:
        raise ValueError('Saved account not found. Add it in Administration → Namecheap Accounts first.')
    if row['mode'] != config.get('mode', 'production'):
        raise ValueError('Saved account mode differs from requested mode.')
    account = json.loads(cipher().decrypt(row['credentials'].encode())) | {'mode': row['mode']}
    results = []
    for zone in zones:
        try:
            result = provision(account, zone)
            changed = result['status'] != 'DNS already configured'
            results.append(dict(domain=zone['sld']+'.'+zone['tld'], changed=changed))
            with connect() as con:
                con.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)', ('ansible', 'namecheap:provision:account:'+str(account_id)+':'+zone['sld']+'.'+zone['tld'], int(time.time())))
        except Exception:
            # DNS writes are not transactional across zones; never hide partial progress.
            print(json.dumps({'ok':False, 'completed':results, 'failed_domain':zone['sld']+'.'+zone['tld'], 'error':'Provisioning stopped. Inspect Namecheap DNS and account settings before retrying.'}))
            return 1
    print(json.dumps({'ok':True, 'changed':any(r['changed'] for r in results), 'zones':results}))
    return 0

if __name__ == '__main__':
    try:
        sys.exit(run(json.load(sys.stdin)))
    except Exception:
        print(json.dumps({'ok':False, 'error':'Unable to load saved Namecheap account or validate input. Check account ID, mode, zone fields, database configuration and encryption key.'}))
        sys.exit(1)
