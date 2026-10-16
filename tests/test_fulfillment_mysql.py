"""Real MySQL acceptance test, only against the explicitly configured disposable CI DB."""
import concurrent.futures,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'panel'))
import database,fulfillment,marketplace,payments,storage

@unittest.skipUnless(os.environ.get('PANEL_TEST_MYSQL')=='1','requires disposable MySQL integration database')
class MySQLFulfillmentTests(unittest.TestCase):
    def test_verified_payment_and_concurrent_workers_activate_once(self):
        import server
        from cryptography.fernet import Fernet
        database.initialize_schema()
        with tempfile.TemporaryDirectory() as tmp,patch.object(server,'DATA',Path(tmp)),patch.object(storage,'DATA',Path(tmp)):
            server.create_user('fulfillbuyer','fulfillment-test-password','user')
            with database.connect() as con:buyer=con.execute("SELECT * FROM users WHERE username='fulfillbuyer'").fetchone()
            operator={'id':999,'role':'root','username':'operator'}
            _,plan=marketplace.handle('POST','/api/marketplace/plans/save',operator,{'name':'Automatic test','description':'CI','price_cents':1500,'disk_gb':2,'bandwidth_gb':100,'websites':3,'enabled':True,'featured':False})
            _,order=marketplace.handle('POST','/api/marketplace/orders/create',buyer,{'plan_id':plan['id'],'expected_price_cents':1500,'request_key':'fulfillment-mysql-0001','confirmed':True})
            with database.connect() as con:
                gid=con.execute("INSERT INTO payment_gateways(owner_id,provider,label,mode,enabled,credentials,updated) VALUES(0,'stripe','CI','live',1,'unused',0)").lastrowid
                pid=con.execute("INSERT INTO payment_transactions(order_id,buyer_id,seller_id,gateway_id,provider,mode,amount_cents,currency,state,token,provider_reference,created) VALUES(?,?,0,?,'stripe','live',1500,'USD','checkout','fulfillment-mysql-unique-token','cs_live_mysql',0)",(order['id'],buyer['id'],gid)).lastrowid
                payment=con.execute('SELECT * FROM payment_transactions WHERE id=?',(pid,)).fetchone()
            response={'id':'cs_live_mysql','payment_status':'paid','amount_total':1500,'currency':'usd','metadata':{'panel_payment':payment['token']},'livemode':True}
            with patch.object(payments,'request_api',return_value=response):
                payments.verify(payment,{'provider':'stripe','mode':'live'},{'secret':'hidden'})
                payments.verify(payment,{'provider':'stripe','mode':'live'},{'secret':'hidden'})
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                for result in pool.map(lambda _:fulfillment.run_batch(),range(2)):pass
            with database.connect() as con:
                self.assertEqual(con.execute('SELECT COUNT(*) AS n FROM hosting_services WHERE order_id=?',(order['id'],)).fetchone()['n'],1)
                self.assertEqual(con.execute('SELECT state FROM provisioning_jobs WHERE order_id=?',(order['id'],)).fetchone()['state'],'active')
            self.assertEqual(fulfillment.limits(buyer['id'])['disk_bytes'],2*1024**3)
            with patch.object(storage,'FILE_MAX',3*1024**3),patch.object(storage,'usage',return_value=(2*1024**3,0)):
                with self.assertRaises(ValueError):storage.write(buyer['id'],storage.path(buyer['id'],'too-full'),b'x')
