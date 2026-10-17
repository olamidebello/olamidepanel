"""Read-only implementation coverage. Never equate a catalog entry with readiness."""
import json
import sys
import time
sys.path.insert(0, '/opt/olamidepanel/panel')
from database import connect
from modules import report


def build_report(domains, inventory):
    tools = inventory['tools']
    counts = {status: sum(tool['status'] == status for tool in tools)
              for status in sorted({tool['status'] for tool in tools})}
    return {
        'generated_at': int(time.time()),
        'notice': 'Source implementation inventory only. Service health, DNS and public delivery are not verified.',
        'coverage_complete': bool(tools) and all(t['status'] == 'implemented' for t in tools),
        'counts': counts,
        'tools': tools,
        'domains': [{'domain': d['domain'], 'owner_id': d['owner_id'],
                     'tool_inventory': 'tools', 'service_readiness': 'not_verified'} for d in domains if d['active']],
        'operator_mail_adapter': {'scope': 'SMTP/IMAP/DKIM Ansible provisioning',
                                  'mailbox_gui': False, 'public_delivery_verified': False},
    }

if __name__ == '__main__':
    with connect() as con:
        domains = con.execute('SELECT d.name AS domain,d.owner AS owner_id,u.active FROM domains d JOIN users u ON u.id=d.owner ORDER BY d.id').fetchall()
    print(json.dumps(build_report(domains, report()), indent=2))
