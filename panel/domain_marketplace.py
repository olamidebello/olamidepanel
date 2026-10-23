"""Bulk domain storefront requests and centrally enforced payment gateway assignments."""
import html
import json
import time
from urllib.parse import urlencode
import hosted_domains
from database import connect

SCHEMA = '''
CREATE TABLE IF NOT EXISTS domain_marketplaces (
 domain VARCHAR(253) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 enabled BOOLEAN NOT NULL DEFAULT FALSE,
 gateway_ids TEXT NOT NULL,
 state VARCHAR(32) NOT NULL,
 message VARCHAR(250) NOT NULL DEFAULT '',
 updated BIGINT NOT NULL
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS domain_marketplace_jobs (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 domain VARCHAR(253) CHARACTER SET ascii NOT NULL,
 operation VARCHAR(16) NOT NULL,
 gateway_ids TEXT NOT NULL,
 creator BIGINT NOT NULL,
 state VARCHAR(24) NOT NULL DEFAULT 'queued',
 created BIGINT NOT NULL,
 finished BIGINT,
 message VARCHAR(250) NOT NULL DEFAULT '',
 INDEX domain_queue(state,id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS domain_marketplace_orders (
 order_id BIGINT PRIMARY KEY,
 domain VARCHAR(253) CHARACTER SET ascii NOT NULL
) ENGINE=InnoDB;
'''

def authorize(user):
    if user.get('role') not in ('root', 'super_admin'):
        raise PermissionError('Super-admin access required')

def initialize(db=connect):
    with db() as con:
        for sql in SCHEMA.split(';'):
            if sql.strip(): con.execute(sql)

def validate_targets(body, inventory):
    domains = body.get('domains', [])
    if not isinstance(domains, list) or not domains or len(domains) > 1000 or any(not isinstance(d,str) for d in domains):
        raise ValueError('Select 1–1000 domains')
    if len(set(domains)) != len(domains) or not set(domains) <= set(inventory):
        raise ValueError('Select unique domains from the current hosting inventory')
    ids = body.get('gateway_ids', [])
    if not isinstance(ids, list) or any(type(g) is not int or g <= 0 for g in ids) or len(ids) > 100:
        raise ValueError('Invalid gateway selection')
    operation = body.get('operation')
    if operation not in ('deploy', 'disable'):
        raise ValueError('Choose deploy/update or disable')
    if operation == 'deploy' and not ids:
        raise ValueError('Select at least one shared payment gateway')
    if body.get('confirmed') is not True:
        raise ValueError('Confirm the selected domain count and shared gateways')
    return domains, sorted(set(ids)), operation

def handle(method, user, body=None, db=connect):
    authorize(user)
    inventory = hosted_domains.report(user, db)['domains']
    with db() as con:
        if method == 'GET':
            rows = {r['domain']: dict(r) for r in con.execute('SELECT * FROM domain_marketplaces').fetchall()}
            return {'domains': [dict(d, marketplace=rows.get(d['name'])) for d in inventory],
                    'gateways': con.execute('SELECT id,provider,label,mode,enabled FROM payment_gateways WHERE owner_id=0').fetchall(),
                    'jobs': con.execute('SELECT id,domain,operation,state,message,created,finished FROM domain_marketplace_jobs ORDER BY id DESC LIMIT 200').fetchall()}
        domains, ids, operation = validate_targets(body or {}, [d['name'] for d in inventory])
        # Serialize submissions, including overlapping bulk requests.
        con.execute('SELECT id FROM users ORDER BY id LIMIT 1 FOR UPDATE').fetchone()
        gateways = {r['id'] for r in con.execute('SELECT id FROM payment_gateways WHERE owner_id=0 AND enabled=1').fetchall()}
        if operation == 'deploy' and not set(ids) <= gateways:
            raise ValueError('Use enabled operator-owned gateways only')
        if con.execute("SELECT id FROM domain_marketplace_jobs WHERE state IN ('queued','running') LIMIT 1").fetchone():
            raise ValueError('A deployment batch is pending; wait for completion')
        now = int(time.time())
        for domain in domains:
            con.execute('INSERT INTO domain_marketplace_jobs(domain,operation,gateway_ids,creator,created) VALUES(?,?,?,?,?)',
                        (domain, operation, json.dumps(ids), user['id'], now))
        con.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)',
                    (user['username'], 'domain-marketplace:'+operation+':'+str(len(domains))+' domains', now))
        return {'ok': True, 'queued': len(domains)}

def assigned(con, domain):
    row = con.execute('SELECT * FROM domain_marketplaces WHERE domain=?', (domain,)).fetchone()
    if not row or not row['enabled'] or row['state'] != 'deployed':
        raise ValueError('This domain marketplace is unavailable')
    return json.loads(row['gateway_ids'])

def order_gateways(con, order_id):
    row = con.execute('SELECT domain FROM domain_marketplace_orders WHERE order_id=?', (order_id,)).fetchone()
    return assigned(con, row['domain']) if row else None

def storefront(domain, origin, db=connect):
    if not hosted_domains.DOMAIN.fullmatch(domain): raise ValueError('Invalid domain')
    with db() as con:
        ids = assigned(con, domain)
        plans = con.execute('SELECT id,name,description,price_cents,currency FROM hosting_plans WHERE seller_id=0 AND enabled=1 ORDER BY id').fetchall()
        gateways = [r for r in con.execute('SELECT id,label,provider,mode FROM payment_gateways WHERE owner_id=0 AND enabled=1').fetchall() if r['id'] in ids]
    esc = html.escape
    link = origin + '/?' + urlencode({'marketplace_domain': domain}) + '#tool=Hosting%20Plans'
    cards = ''.join('<article><h2>'+esc(p['name'])+'</h2><p>'+esc(p['description'])+'</p><p>'+esc(p['currency'])+' '+format(p['price_cents']/100,'.2f')+' / month</p></article>' for p in plans)
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(domain)+' Marketplace</title><link rel="stylesheet" href="'+esc(origin,quote=True)+'/style.css"><body><main><h1>'+esc(domain)+' Marketplace</h1><p>Hosting and reseller services, managed by Olamidepanel.</p>'+cards+'<p>Payment options: '+esc(', '.join(g['label']+' ('+g['mode']+')' for g in gateways))+'</p><a href="'+esc(link,quote=True)+'">Sign in to order and pay securely</a><p>Payments use the central panel checkout. Domain application integrations and billing remain separate.</p></main></body></html>').encode()
