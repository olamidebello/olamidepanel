"""Persistent mailbox bootstrap and conservative RFC2136 DNS provisioning."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import tempfile

NAME = re.compile(r'^(?:[a-z0-9_-]+\.)+[a-z0-9-]+\.?$')


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as out:
            json.dump(value, out, indent=2)
            out.write('\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def accounts(domains, localparts, existing, saved):
    merged = {a['address']: a for a in saved}
    merged.update({a['address']: a for a in existing})
    for domain in domains:
        if not NAME.fullmatch(domain):
            raise ValueError('Invalid domain')
        for local in localparts:
            if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,63}', local):
                raise ValueError('Invalid mailbox localpart')
            address = local + '@' + domain
            if address not in merged:
                password = secrets.token_urlsafe(24)
                result = subprocess.run(['openssl', 'passwd', '-6', '-stdin'], input=password+'\n',
                                        text=True, capture_output=True, check=True)
                merged[address] = {'address': address, 'password': password,
                                   'password_hash': '{SHA512-CRYPT}' + result.stdout.strip()}
    return list(merged.values())


def canonical(kind, value):
    if kind in ('PTR', 'CNAME'):
        return value.lower().rstrip('.') + '.'
    if kind == 'MX':
        priority, host = value.split()
        return str(int(priority)) + ' ' + host.lower().rstrip('.') + '.'
    if kind == 'TXT':
        return ''.join(shlex.split(value))
    return value.strip()


def dns_lines(name, kind, value, present):
    if not NAME.fullmatch(name) or kind not in ('A', 'MX', 'TXT', 'PTR'):
        raise ValueError('Invalid DNS record')
    if '\n' in value or '\r' in value:
        raise ValueError('Invalid multiline DNS value')
    desired = canonical(kind, value)
    current = [canonical(kind, v) for v in present]
    if desired in current:
        return []
    # Unrelated apex TXT records may coexist; SPF must remain a single policy.
    conflicts = current
    if kind == 'TXT' and desired.startswith('v=spf1'):
        conflicts = [v for v in current if v.startswith('v=spf1')]
    if conflicts:
        raise ValueError('Existing DNS record differs; migrate it explicitly: ' + name + ' ' + kind)
    wire = value
    if kind == 'TXT':
        wire = ' '.join(json.dumps(desired[i:i+200]) for i in range(0, len(desired), 200))
    # Guard the server-side snapshot to avoid racing another operator.
    prereqs = ['prereq yxrrset ' + name + '. TXT ' + json.dumps(v) for v in current] if current else ['prereq nxrrset ' + name + '. ' + kind]
    return prereqs + ['update add ' + name + '. 3600 ' + kind + ' ' + wire]


def query(name, kind, server=None):
    args = ['dig', '+tcp', '+time=5', '+tries=1', '+noall', '+answer', '+comments']
    if server:
        args.append('@' + server)
    result = subprocess.run(args + [name + '.', kind], text=True, capture_output=True, check=True)
    if not re.search(r'status: (NOERROR|NXDOMAIN),', result.stdout):
        raise RuntimeError('DNS lookup failed for ' + name)
    values = []
    for line in result.stdout.splitlines():
        fields = line.split(None, 4)
        if len(fields) == 5 and fields[0].lower() == name.lower() + '.' and fields[3] == kind:
            values.append(fields[4])
        elif len(fields) == 5 and fields[3] == 'CNAME':
            raise ValueError('CNAME requires explicit migration: ' + name)
    return values


def records(policy, domains, phase):
    host = policy['mail_hostname']
    ip = str(ipaddress.IPv4Address(policy['panel_public_ipv4']))
    if phase == 'address':
        return [(host, 'A', ip)]
    if phase == 'ptr':
        return [(ipaddress.ip_address(ip).reverse_pointer, 'PTR', host + '.')]
    result = []
    for domain in domains:
        selector = policy.get('mail_selector', 'panel')
        if not re.fullmatch('[a-z][a-z0-9]{0,30}', selector):
            raise ValueError('Invalid DKIM selector')
        keyfile = Path('/etc/opendkim/olamidepanel') / domain / (selector + '.txt')
        text = keyfile.read_text().split('; -----')[0]
        dkim = ''.join(re.findall(r'"([^"\n]*)"', text))
        if not dkim.startswith('v=DKIM1;') or 'p=' not in dkim:
            raise ValueError('Invalid generated DKIM record')
        result.extend([(domain, 'MX', '10 ' + host + '.'),
                       (domain, 'TXT', '"v=spf1 mx ~all"'),
                       ('_dmarc.' + domain, 'TXT', '"v=DMARC1; p=none"'),
                       (selector + '._domainkey.' + domain, 'TXT', json.dumps(dkim))])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['accounts', 'address', 'domain-dns', 'ptr'])
    parser.add_argument('--policy', required=True)
    parser.add_argument('--inventory', required=True)
    args = parser.parse_args()
    policy = json.loads(Path(args.policy).read_text())
    rows = json.loads(Path(args.inventory).read_text())
    domains = sorted(set(r['domain'] for r in rows if r['active']) | set(policy.get('mail_extra_domains', [])))
    if any(not NAME.fullmatch(d) or '/' in d for d in domains):
        raise ValueError('Invalid domain inventory')
    if args.action == 'accounts':
        store = Path('/etc/olamidepanel/mail-bootstrap-credentials.json')
        saved = json.loads(store.read_text()) if store.exists() else []
        merged = accounts(domains, policy.get('mail_bootstrap_localparts', ['admin']), policy.get('mail_accounts', []), saved)
        atomic_json(store, merged)
        # Restrict the active map but retain disabled-domain credentials for recovery.
        effective = [{k: a[k] for k in ('address', 'password_hash')} for a in merged if a['address'].split('@')[1] in domains]
        atomic_json('/etc/olamidepanel/mail-bootstrap-accounts.json', {'mail_accounts': effective})
        print(json.dumps({'mailboxes': len(effective)}))
        return
    desired = records(policy, domains, args.action)
    dns = policy.get('mail_reverse_dns' if args.action == 'ptr' else 'mail_dns', {})
    mode = dns.get('mode', 'manual')
    if mode not in ('manual', 'rfc2136'):
        raise ValueError('Supported DNS modes: manual, rfc2136')
    plans = []
    # Preflight every record before applying this phase.
    for name, kind, value in desired:
        present = query(name, kind, dns.get('server') if mode == 'rfc2136' else None)
        conflict = None
        try:
            lines = dns_lines(name, kind, value, present)
        except ValueError as error:
            if mode != 'manual':
                raise
            conflict = str(error)
            lines = []
        plans.append({'name': name, 'type': kind, 'value': value,
                      'pending': bool(lines) or conflict is not None,
                      'conflict': conflict, 'lines': lines})
    if mode == 'rfc2136':
        server = dns['server']
        ipaddress.ip_address(server)
        key = Path(dns['key_file'])
        if not key.is_file() or key.stat().st_mode & 0o077:
            raise ValueError('TSIG key file must be private (0600)')
        for plan in plans:
            if plan['lines']:
                payload = '\n'.join(['server ' + server] + plan['lines'] + ['send', ''])
                subprocess.run(['nsupdate', '-v', '-t', '20', '-k', str(key)], input=payload,
                               text=True, capture_output=True, check=True)
                observed = query(plan['name'], plan['type'], server)
                if canonical(plan['type'], plan['value']) not in [canonical(plan['type'], v) for v in observed]:
                    raise RuntimeError('DNS update did not verify: ' + plan['name'])
                plan['pending'] = False
    atomic_json('/etc/olamidepanel/mail-bootstrap-' + args.action + '-report.json', plans)
    print(json.dumps({'mode': mode, 'pending': sum(p['pending'] for p in plans)}))


if __name__ == '__main__':
    main()
