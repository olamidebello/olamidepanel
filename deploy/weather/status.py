"""Merge country deployment results into the existing operator inventory atomically."""
import fcntl
import grp
import json
import os
import pathlib
import sys
import time

report = json.loads(pathlib.Path(sys.argv[1]).read_text())
root = pathlib.Path('/var/lib/olamidepanel')
root.mkdir(parents=True, exist_ok=True)
with (root / 'weather-status.lock').open('w') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    path = root / 'hosted-domains.json'
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        data = {'domains': []}
    rows = {r['domain']: r for r in data['domains']}
    rows[report['domain']] = report
    data.update(updated_at=int(time.time()), domains=list(rows.values()))
    temporary = root / 'hosted-domains.weather.tmp'
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    os.chmod(temporary, 0o640)
    os.chown(temporary, 0, grp.getgrnam('olamidepanel').gr_gid)
    os.replace(temporary, path)
