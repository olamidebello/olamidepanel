"""MySQL-only runtime database adapter. Credentials never enter logs."""
import json
import os
from pathlib import Path
import pymysql
from pymysql.cursors import DictCursor

IntegrityError = pymysql.IntegrityError

def configuration():
    path=Path(os.environ.get('PANEL_DB_CONFIG','/etc/olamidepanel/database.json'))
    config=json.loads(path.read_text())
    if not config.get('password'): raise ValueError('MySQL password is required')
    options={key:config[key] for key in ['host','port','user','password','database','unix_socket'] if key in config}
    if config.get('ssl_ca'):
        options.update(ssl_ca=config['ssl_ca'],ssl_verify_cert=True,ssl_verify_identity=True)
    if not config.get('unix_socket') and config.get('host','localhost') not in ['localhost','127.0.0.1','::1'] and not config.get('ssl_ca'):
        raise ValueError('Remote MySQL requires a trusted TLS CA')
    return dict(options,charset='utf8mb4',cursorclass=DictCursor,autocommit=False,connect_timeout=10,read_timeout=30,write_timeout=30)

class Connection:
    def __init__(self): self.raw=pymysql.connect(**configuration())
    def execute(self,sql,args=()):
        cur=self.raw.cursor()
        if sql=='BEGIN IMMEDIATE':
            self.raw.begin()
            cur.execute('SELECT id FROM users ORDER BY id FOR UPDATE')
            cur.fetchall()
            return cur
        if sql=='INSERT INTO user_ids DEFAULT VALUES': sql='INSERT INTO user_ids () VALUES ()'
        cur.execute(sql.replace('?', '%s'),args)
        return cur
    def __enter__(self): return self
    def __exit__(self,kind,value,tb):
        try:
            if kind: self.raw.rollback()
            else: self.raw.commit()
        finally: self.raw.close()

def connect(): return Connection()

def initialize_schema():
    statements=(Path(__file__).parent/'schema.sql').read_text().split(';')
    with connect() as con:
        for sql in statements:
            if sql.strip(): con.execute(sql)
