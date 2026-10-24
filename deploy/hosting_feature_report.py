"""Read-only feature implementation and package evidence; never claims parity."""
import argparse
import json
from pathlib import Path
import subprocess

PROFILES = {
    'web_runtime': ['php8.2-fpm', 'php8.2-cli', 'php8.2-mysql', 'php8.2-pgsql',
                    'php8.2-sqlite3', 'php8.2-mbstring', 'php8.2-xml', 'php8.2-curl',
                    'php8.2-zip', 'php8.2-gd', 'php8.2-intl', 'nodejs', 'npm', 'ruby', 'perl'],
    'file_tools': ['git', 'rsync', 'zip', 'unzip', 'sqlite3'],
    'statistics': ['goaccess', 'awstats'],
    'malware_scanner': ['clamav', 'clamav-freshclam'],
    'postgresql': ['postgresql', 'postgresql-client'],
}
COMMERCIAL = ['cPanel and WHM', 'Sitejet Builder', 'SocialBee', 'WP Toolkit',
              'WP Squared', 'WHMCS', 'CloudLinux', 'KernelCare', 'LiteSpeed', 'JetBackup']

def report(root):
    tools = json.loads((root / 'panel/module-audit.json').read_text())
    packages = {}
    for package in sorted({p for group in PROFILES.values() for p in group}):
        result = subprocess.run(['dpkg-query', '-W', '-f=${Status}', package],
                                capture_output=True, text=True, check=False)
        packages[package] = result.returncode == 0 and result.stdout == 'install ok installed'
    return {'exact_cpanel_parity': False, 'tools': tools, 'packages_installed': packages,
            'commercial_products': [{'name': name, 'state': 'license_and_supported_adapter_required'}
                                    for name in COMMERCIAL],
            'scope': 'Package presence is not service readiness, tenant isolation or a working GUI. Public marketing menus are website content, not server services.',
            'remaining_tools': [t['name'] for t in tools if t['status'] != 'implemented']}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(report(args.root), indent=2))
