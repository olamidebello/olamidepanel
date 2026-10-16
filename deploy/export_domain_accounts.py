"""Read-only inventory for the operator-run per-domain SSH playbook."""
import json,sys
sys.path.insert(0,'/opt/olamidepanel/panel')
from database import connect

if __name__=='__main__':
    with connect() as con:
        rows=con.execute('SELECT d.name AS domain,d.owner AS owner_id,u.active FROM domains d JOIN users u ON u.id=d.owner ORDER BY d.id').fetchall()
    print(json.dumps(rows))
