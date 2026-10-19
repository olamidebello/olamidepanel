"""Read-only operator inventory; never grants ownership or publishing rights."""
import json
import re
from pathlib import Path

SNAPSHOT = Path('/var/lib/olamidepanel/hosted-domains.json')
# Country inventory mirrors ansible/weather/countries.json; tests enforce parity.
WEATHER_DOMAINS = {'weatheralgeria.africandroid.world': 'Algeria',
 'weatherangola.africandroid.world': 'Angola',
 'weatherbenin.africandroid.world': 'Benin',
 'weatherbotswana.africandroid.world': 'Botswana',
 'weatherburkinafaso.africandroid.world': 'Burkina Faso',
 'weatherburundi.africandroid.world': 'Burundi',
 'weathercaboverde.africandroid.world': 'Cabo Verde',
 'weathercameroon.africandroid.world': 'Cameroon',
 'weathercentralafricanrepublic.africandroid.world': 'Central African Republic',
 'weatherchad.africandroid.world': 'Chad',
 'weathercomoros.africandroid.world': 'Comoros',
 'weatherdemocraticrepublicofthecongo.africandroid.world': 'Democratic Republic of the Congo',
 'weatherrepublicofthecongo.africandroid.world': 'Republic of the Congo',
 'weathercotedivoire.africandroid.world': 'Côte d’Ivoire',
 'weatherdjibouti.africandroid.world': 'Djibouti',
 'weatheregypt.africandroid.world': 'Egypt',
 'weatherequatorialguinea.africandroid.world': 'Equatorial Guinea',
 'weathereritrea.africandroid.world': 'Eritrea',
 'weathereswatini.africandroid.world': 'Eswatini',
 'weatherethiopia.africandroid.world': 'Ethiopia',
 'weathergabon.africandroid.world': 'Gabon',
 'weathergambia.africandroid.world': 'Gambia',
 'weatherghana.africandroid.world': 'Ghana',
 'weatherguinea.africandroid.world': 'Guinea',
 'weatherguineabissau.africandroid.world': 'Guinea-Bissau',
 'weatherkenya.africandroid.world': 'Kenya',
 'weatherlesotho.africandroid.world': 'Lesotho',
 'weatherliberia.africandroid.world': 'Liberia',
 'weatherlibya.africandroid.world': 'Libya',
 'weathermadagascar.africandroid.world': 'Madagascar',
 'weathermalawi.africandroid.world': 'Malawi',
 'weathermali.africandroid.world': 'Mali',
 'weathermauritania.africandroid.world': 'Mauritania',
 'weathermauritius.africandroid.world': 'Mauritius',
 'weathermorocco.africandroid.world': 'Morocco',
 'weathermozambique.africandroid.world': 'Mozambique',
 'weathernamibia.africandroid.world': 'Namibia',
 'weatherniger.africandroid.world': 'Niger',
 'weatherrwanda.africandroid.world': 'Rwanda',
 'weathersaotomeandprincipe.africandroid.world': 'São Tomé and Príncipe',
 'weathersenegal.africandroid.world': 'Senegal',
 'weatherseychelles.africandroid.world': 'Seychelles',
 'weathersierraleone.africandroid.world': 'Sierra Leone',
 'weathersomalia.africandroid.world': 'Somalia',
 'weathersouthafrica.africandroid.world': 'South Africa',
 'weathersouthsudan.africandroid.world': 'South Sudan',
 'weathersudan.africandroid.world': 'Sudan',
 'weathertanzania.africandroid.world': 'Tanzania',
 'weathertogo.africandroid.world': 'Togo',
 'weathertunisia.africandroid.world': 'Tunisia',
 'weatheruganda.africandroid.world': 'Uganda',
 'weatherzambia.africandroid.world': 'Zambia',
 'weatherzimbabwe.africandroid.world': 'Zimbabwe',
 'weatherwesternsahara.africandroid.world': 'Western Sahara'}
OPERATOR_DOMAINS = ('africaweather.africandroid.world', 'prod.dobhrap.com', 'sip.dobhrap.com', 'justisolve.com', 'africanappsstore.space', 'olamidepanel.com', 'nekkeddating.com', 'olamideolatayobello.com', 'africanbrowser.com', 'dobhrap.com', 'aicourtsystem.com', 'africancreativity.io', 'africandroid.world', 'africandroid.space', 'olamidemedical.health', 'weathernigeria.africandroid.world') + tuple(WEATHER_DOMAINS)

DOMAIN = re.compile(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}')

def report(user, connect, snapshot=None, operator_domains=OPERATOR_DOMAINS):
    if user.get('role') not in ('root', 'super_admin'):
        raise PermissionError('Super-admin access required')
    with connect() as con:
        rows = con.execute('SELECT d.name,u.username AS owner FROM domains d JOIN users u ON u.id=d.owner ORDER BY d.name').fetchall()
    inventory = {r['name']: {'name': r['name'], 'owner': r['owner'],
                            'status': 'inventory_only', 'source': 'Panel inventory'} for r in rows}
    for name in operator_domains:
        if DOMAIN.fullmatch(name):
            inventory.setdefault(name, {'name': name, 'owner': 'Server operator',
                                      'status': 'verification_pending',
                                      'source': 'Operator hosting configuration'})
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
                        configuration=str(row.get('configuration', ''))[:500],
                        deployment_status=str(row.get('deployment_status', ''))[:100],
                        deployment_checked_at=row.get('deployment_checked_at'),
                        backend=str(row.get('backend', ''))[:100],
                        repo=str(row.get('repo', ''))[:200],
                        commit=str(row.get('commit', ''))[:40],
                        error=str(row.get('error', ''))[:500])
    except (OSError, ValueError, TypeError, KeyError):
        updated = None
        notice = 'Server hosting status is unavailable. Run the hosting playbook to export its domain inventory.'
    for name, item in inventory.items():
        if name in WEATHER_DOMAINS:
            item['country'] = WEATHER_DOMAINS[name]
            item['category'] = 'country_weather'
        elif name == 'weathernigeria.africandroid.world':
            item['country'] = 'Nigeria'
            item['category'] = 'country_weather'
    return {'domains': sorted(inventory.values(), key=lambda x:x['name']),
            'updated_at': updated, 'notice': notice}

