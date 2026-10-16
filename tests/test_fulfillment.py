"""Transactional behavior tests with SQLite; MySQL locking is covered in CI integration."""
import json,sqlite3,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'panel'))
import fulfillment,payments,storage

class Connection:
    def __init__(self,path):
        self.raw=sqlite3.connect(path);self.raw.row_factory=lambda c,r:dict(zip([x[0] for x in c.description],r))
    def execute(self,sql,args=()):
        sql=sql.replace(' FOR UPDATE SKIP LOCKED','').replace(' FOR UPDATE','').replace('INSERT IGNORE','INSERT OR IGNORE')
        sql=sql.replace('ON DUPLICATE KEY UPDATE enabled=1','ON CONFLICT(user_id) DO UPDATE SET enabled=1')
        return self.raw.execute(sql,args)
    def __enter__(self):return self
    def __exit__(self,kind,value,tb):
        if kind:self.raw.rollback()
        else:self.raw.commit()
        self.raw.close()

class FulfillmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'test.db';self.db=lambda:Connection(self.path)
        for obj,name,value in [(fulfillment,'connect',self.db),(payments,'connect',self.db),(storage,'DATA',Path(self.tmp.name)/'data')]:
            p=patch.object(obj,name,value);p.start();self.addCleanup(p.stop)
        with self.db() as con:
            for statement in [
                'CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT,email TEXT,role TEXT,active INTEGER)',
                'CREATE TABLE hosting_orders(id INTEGER PRIMARY KEY,owner INTEGER,seller_id INTEGER,status TEXT,price_cents INTEGER,currency TEXT,plan_snapshot TEXT)',
                'CREATE TABLE payment_transactions(id INTEGER PRIMARY KEY,order_id INTEGER,buyer_id INTEGER,seller_id INTEGER,state TEXT,mode TEXT,verified_at INTEGER,amount_cents INTEGER,currency TEXT)',
                'CREATE TABLE provisioning_jobs(order_id INTEGER PRIMARY KEY,payment_id INTEGER UNIQUE,state TEXT,attempts INTEGER,next_attempt INTEGER,message TEXT,updated INTEGER)',
                'CREATE TABLE hosting_services(order_id INTEGER PRIMARY KEY,payment_id INTEGER UNIQUE,owner INTEGER,seller_id INTEGER,kind TEXT,disk_bytes INTEGER,websites INTEGER,bandwidth_gb INTEGER,state TEXT,activated_at INTEGER,expires_at INTEGER,role_granted INTEGER)',
                'CREATE TABLE marketplace_vendors(user_id INTEGER PRIMARY KEY,enabled INTEGER)',
                'CREATE TABLE marketplace_stores(owner_id INTEGER PRIMARY KEY,name TEXT,description TEXT,contact_email TEXT,updated INTEGER)',
                'CREATE TABLE audit(actor TEXT,action TEXT,created INTEGER)']:con.execute(statement)
            con.execute("INSERT INTO users VALUES(1,'buyer','buyer@example.com','user',1)")
            self.plan={'plan_kind':'hosting','disk_gb':2,'websites':3,'bandwidth_gb':100}
            con.execute("INSERT INTO hosting_orders VALUES(1,1,0,'approved',1500,'USD',?)",(json.dumps(self.plan),))
            con.execute("INSERT INTO payment_transactions VALUES(1,1,1,0,'checkout','live',NULL,1500,'USD')")
    def payment(self):
        with self.db() as con:return con.execute('SELECT * FROM payment_transactions WHERE id=1').fetchone()
    def verify(self,live=True,amount=1500):
        row={**self.payment(),'provider_reference':'cs_live_example','token':'proof'}
        result={'id':'cs_live_example','metadata':{'panel_payment':'proof'},'livemode':live,'payment_status':'paid','amount_total':amount,'currency':'usd'}
        with patch.object(payments,'request_api',return_value=result):return payments.verify(row,{'provider':'stripe','mode':'live' if live else 'test'},{'secret':'hidden'})
    def count(self,table):
        with self.db() as con:return con.execute('SELECT COUNT(*) AS n FROM '+table).fetchone()['n']
    def test_confirmed_live_payment_creates_one_account_allocation_and_preserves_login(self):
        self.verify();self.verify();self.assertEqual(self.count('provisioning_jobs'),1)
        fulfillment.run_batch();fulfillment.run_batch()
        self.assertEqual(self.count('hosting_services'),1)
        self.assertTrue(storage.home(1).is_dir())
        self.assertEqual(fulfillment.limits(1),{'disk_bytes':2*1024**3,'websites':3})
        with self.db() as con:self.assertEqual(con.execute('SELECT state FROM provisioning_jobs').fetchone()['state'],'active')
    def test_queue_failure_rolls_back_paid_flag(self):
        with patch.object(payments,'enqueue',side_effect=RuntimeError('queue unavailable')):
            with self.assertRaises(RuntimeError):self.verify()
        self.assertEqual(self.payment()['state'],'checkout')
        self.assertEqual(self.count('provisioning_jobs'),0)
    def test_test_payments_and_invalid_amount_do_not_activate(self):
        with self.db() as con:con.execute("UPDATE payment_transactions SET mode='test'")
        self.verify(live=False);fulfillment.run_batch();self.assertEqual(self.count('hosting_services'),0)
        self.assertEqual(self.count('provisioning_jobs'),0)
        with self.assertRaises(ValueError):self.verify(amount=1501)
    def test_failure_rolls_back_and_retries_without_second_payment(self):
        self.verify()
        with patch.object(storage,'home',side_effect=OSError('disk unavailable')):fulfillment.run_batch()
        self.assertEqual(self.count('hosting_services'),0)
        with self.db() as con:
            self.assertEqual(con.execute('SELECT state FROM provisioning_jobs').fetchone()['state'],'retrying')
            con.execute('UPDATE provisioning_jobs SET next_attempt=0')
        fulfillment.run_batch();self.assertEqual(self.count('hosting_services'),1);self.assertEqual(self.count('payment_transactions'),1)
    def test_reseller_purchase_and_expiration(self):
        with self.db() as con:con.execute('UPDATE hosting_orders SET plan_snapshot=?',(json.dumps({**self.plan,'plan_kind':'reseller'}),))
        self.verify();fulfillment.run_batch()
        with self.db() as con:
            self.assertEqual(con.execute('SELECT role FROM users').fetchone()['role'],'reseller')
            self.assertEqual(con.execute('SELECT enabled FROM marketplace_vendors').fetchone()['enabled'],1)
            con.execute('UPDATE hosting_services SET expires_at=0')
        fulfillment.run_batch()
        with self.db() as con:
            self.assertEqual(con.execute('SELECT role FROM users').fetchone()['role'],'user')
            self.assertEqual(con.execute('SELECT state FROM hosting_services').fetchone()['state'],'expired')
    def test_suspended_account_does_not_activate(self):
        self.verify()
        with self.db() as con:con.execute('UPDATE users SET active=0')
        fulfillment.run_batch();self.assertEqual(self.count('hosting_services'),0)
    def test_unpaid_jobs_and_changed_orders_cannot_grant_resources(self):
        with self.db() as con:fulfillment.enqueue(con,{**self.payment(),'state':'paid'})
        fulfillment.run_batch();self.assertEqual(self.count('hosting_services'),0)
        self.verify()
        with self.db() as con:
            con.execute('UPDATE provisioning_jobs SET next_attempt=0')
            con.execute('UPDATE hosting_orders SET price_cents=9999')
        fulfillment.run_batch();self.assertEqual(self.count('hosting_services'),0)
    def test_unsupported_service_never_claims_activation(self):
        self.verify()
        with self.db() as con:con.execute('UPDATE hosting_orders SET plan_snapshot=?',(json.dumps({**self.plan,'plan_kind':'vps'}),))
        fulfillment.run_batch();self.assertEqual(self.count('hosting_services'),0)

if __name__=='__main__':unittest.main()
