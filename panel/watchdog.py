"""MySQL-backed operator watchdog reports; root worker owns recovery actions."""
import json
import time
from database import connect

SCHEMA = [
 """CREATE TABLE IF NOT EXISTS watchdog_domains (
 domain VARCHAR(253) CHARACTER SET ascii PRIMARY KEY,
 checked_at BIGINT NOT NULL, healthy BOOLEAN NOT NULL, failures INT NOT NULL,
 last_restart BIGINT NOT NULL DEFAULT 0, action VARCHAR(64) NOT NULL,
 checks TEXT NOT NULL) ENGINE=InnoDB""",
 """CREATE TABLE IF NOT EXISTS watchdog_events (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, domain VARCHAR(253) CHARACTER SET ascii NOT NULL,
 checked_at BIGINT NOT NULL, healthy BOOLEAN NOT NULL, action VARCHAR(64) NOT NULL,
 checks TEXT NOT NULL, INDEX watchdog_time(checked_at), INDEX watchdog_domain(domain,id)
 ) ENGINE=InnoDB""",
]

def initialize(db=connect):
 with db() as c:
  for sql in SCHEMA:c.execute(sql)

def report(user, db=connect):
 if user.get('role') not in ('root','super_admin'):raise PermissionError('Super-admin access required')
 with db() as c:
  domains=[dict(r) for r in c.execute('SELECT * FROM watchdog_domains ORDER BY domain').fetchall()]
  events=[dict(r) for r in c.execute('SELECT * FROM watchdog_events ORDER BY id DESC LIMIT 500').fetchall()]
  totals=[dict(r) for r in c.execute('SELECT action,count(*) AS count FROM watchdog_events WHERE checked_at>=? GROUP BY action',(int(time.time())-86400,)).fetchall()]
 for row in domains+events:row['checks']=json.loads(row['checks'])
 now=int(time.time())
 for row in domains:row['stale']=now-row['checked_at']>600
 return {'domains':domains,'events':events,'totals':totals,'retention_days':90,'event_limit':500,'summary_hours':24}
