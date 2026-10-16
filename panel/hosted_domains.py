"""Read-only operator inventory; never grants ownership or publishing rights."""
import json
import re
from pathlib import Path

SNAPSHOT = Path('/var/lib/olamidepanel/hosted-domains.json')
DOMAIN = re.compile(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}')

def report(user, connect, snapshot=None):
    if user.get('role') not in ('root', 'super_admin'):
        raise PermissionError('Super-admin access required')
    with connect() as con:
        rows = con.execute('SELECT d.name,u.username AS owner FROM domains d JOIN users u ON u.id=d.owner ORDER BY d.name').fetchall()
    inventory = {r['name']: {'name': r['name'], 'owner': r['owner'],
                            'status': 'inventory_only', 'source': 'Panel inventory'} for r in rows}
    notice = ''
    try:
        data = json.loads((snapshot or SNAPSHOT).read_text())
        if not isinstance(data, dict) or not isinstance(data.get('domains'), list):
            raise ValueError('Invalid hosting status snapshot')
        updated = int(data['updated_at'])
        for row in data['domains'][:1000]:
            name = row.get('domain', '')
            if not isinstance(name, str) or not DOMAIN.fullmatch(name):
                continue
            item = inventory.setdefault(name, {'name': name, 'owner': 'Server operator'})
            item.update(source='Server hosting automation',
                        status=str(row.get('status', 'unknown'))[:100],
                        checked_at=row.get('checked_at'), www=row.get('www', ''),
                        document_root=str(row.get('document_root', ''))[:500],
                        configuration=str(row.get('configuration', ''))[:500])
    except (OSError, ValueError, TypeError, KeyError):
        updated = None
        notice = 'Server hosting status is unavailable. Run the hosting playbook to export its domain inventory.'
    return {'domains': sorted(inventory.values(), key=lambda x:x['name']),
            'updated_at': updated, 'notice': notice}
