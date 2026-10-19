"""Audit manual DNS and export only the requested country hostname A records."""
import base64
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import json
from pathlib import Path
import re
import socket
import sys


def audit(countries, address, resolver=socket.getaddrinfo):
    ipaddress.IPv4Address(address)
    names = [c['domain'] for c in countries]
    if not all(re.fullmatch(r'weather[a-z]+\.africandroid\.world', n) for n in names):
        raise ValueError('Unexpected domain in country catalog')
    def check(name):
        try:
            addresses = sorted({r[4][0] for r in resolver(name, 443, type=socket.SOCK_STREAM)})
            return {'domain': name, 'addresses': addresses, 'ready': addresses == [address]}
        except socket.gaierror:
            return {'domain': name, 'addresses': [], 'ready': False}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(check, names))
    zone = '; Country weather records only. Import into the authoritative africandroid.world zone.\n'
    zone += '\n'.join(f'{name}. 300 IN A {address}' for name in names) + '\n'
    return results, zone


if __name__ == '__main__':
    countries = json.loads(base64.b64decode(sys.argv[1]))
    results, zone = audit(countries, sys.argv[2])
    target = Path('/var/lib/olamidepanel/africa-weather-dns.zone')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(zone)
    target.chmod(0o644)
    print(json.dumps({'ready': all(r['ready'] for r in results),
                      'missing_or_wrong': [r for r in results if not r['ready']],
                      'import_file': str(target)}))
