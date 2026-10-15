"""Offline one-shot importer. Stop the panel and back up both databases first."""
import argparse, sqlite3, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'panel'))
from database import connect, initialize_schema

parser=argparse.ArgumentParser();parser.add_argument('source');args=parser.parse_args()
source=Path(args.source).resolve()
if not source.is_file(): parser.error('SQLite source does not exist')
old=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True);old.row_factory=sqlite3.Row
initialize_schema()
tables=['user_ids','users','domains','audit']
try:
    with connect() as con:
        for table in tables:
            if con.execute('SELECT COUNT(*) AS total FROM '+table).fetchone()['total']:
                raise ValueError('Migration requires an empty MySQL target')
        for table in tables:
            if not old.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():continue
            rows=old.execute('SELECT * FROM '+table).fetchall()
            for row in rows:
                values=dict(row)
                if table=='users':
                    for key,value in [('active',1),('email',''),('display_name',''),('session_version',0)]:values.setdefault(key,value)
                columns=list(values)
                con.execute('INSERT INTO '+table+' ('+','.join('`'+c+'`' for c in columns)+') VALUES ('+','.join('?' for _ in columns)+')',tuple(values.values()))
        con.execute('INSERT IGNORE INTO user_ids(id) SELECT id FROM users')
        # Preserve IDs belonging to retained home directories as well.
        homes=source.parent/'homes'
        if homes.is_dir():
            for entry in homes.iterdir():
                if entry.name.isdecimal(): con.execute('INSERT IGNORE INTO user_ids(id) VALUES(?)',(int(entry.name),))
    print('Migration complete. Account IDs, password hashes and audit history preserved. SQLite source unchanged.')
finally:old.close()
