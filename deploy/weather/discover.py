"""Read only documented weather/Certbot configuration; never print secrets to a terminal."""
import configparser
import json
import os
from pathlib import Path
import re


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return {}


def discover(root=Path('/'), environ=None):
    env = os.environ if environ is None else environ
    cfg = read_json(root / 'etc/olamide-weather/provision.json')
    def value(key, variable):
        return env.get(variable, '').strip() or str(cfg.get(key, '')).strip()
    email = value('tls_email', 'WEATHER_TLS_EMAIL')
    if not email:
        cli = root / 'etc/letsencrypt/cli.ini'
        if cli.exists():
            parser = configparser.ConfigParser()
            parser.read_string('[certbot]\n' + cli.read_text())
            email = parser.get('certbot', 'email', fallback='').strip()
    if not email:
        # Only production ACME accounts; never infer an address from unrelated files.
        for registration in sorted((root / 'etc/letsencrypt/accounts/acme-v02.api.letsencrypt.org/directory').glob('*/regr.json')):
            contacts = read_json(registration).get('body', {}).get('contact', [])
            for contact in contacts:
                if contact.startswith('mailto:'):
                    email = contact[7:]
                    break
            if email:
                break
    if not email:
        email = str(read_json(root / 'etc/olamide-github-deploy.json').get('admin_email', '')).strip()
    if not re.fullmatch(r'[^ @]+@[^ @]+\.[^ @]+', email):
        raise ValueError('No valid certificate email found. Run with -e tls_email=YOUR_EMAIL. A blank email cannot provision HTTPS.')
    token = value('dns_api_token', 'CLOUDFLARE_API_TOKEN')
    zone = value('dns_zone_id', 'CLOUDFLARE_ZONE_ID')
    credentials = root / 'etc/letsencrypt/cloudflare.ini'
    if not token and credentials.exists():
        parser = configparser.ConfigParser()
        parser.read_string('[cloudflare]\n' + credentials.read_text())
        token = parser.get('cloudflare', 'dns_cloudflare_api_token', fallback='').strip()
    provider = env.get('WEATHER_DNS_PROVIDER', '').strip() or cfg.get('dns_provider') or ('cloudflare' if token else 'manual')
    return dict(tls_email=email, dns_api_token=token, dns_zone_id=zone,
                dns_provider=provider, dns_ipv4=value('dns_ipv4', 'WEATHER_IPV4') or '181.214.149.146')


if __name__ == '__main__':
    try:
        print(json.dumps(discover()))
    except (ValueError, OSError, configparser.Error) as error:
        # Ansible suppresses this task's output. The playbook prints a safe diagnostic.
        raise SystemExit('Weather configuration unavailable: ' + type(error).__name__)
