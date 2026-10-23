import json,os,sqlite3,sys,tempfile,unittest
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from cryptography.fernet import Fernet
sys.path.insert(0,str(Path(__file__).parents[1]/'panel'))
import ai_billing as ai
import api_keys

class BillingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'key').write_bytes(Fernet.generate_key())
        self.env=patch.dict(os.environ,PANEL_PAYMENT_KEY=str(self.root/'key'),PANEL_DATA=str(self.root));self.env.start()
        self.raw=sqlite3.connect(':memory:');self.raw.row_factory=sqlite3.Row
        self.raw.executescript('''
        CREATE TABLE users(id INTEGER PRIMARY KEY,active INTEGER);
        INSERT INTO users VALUES(1,1);
        CREATE TABLE ai_service_config(id INTEGER PRIMARY KEY,config TEXT);
        CREATE TABLE ai_balances(user_id INTEGER PRIMARY KEY,balance NUMERIC);
        CREATE TABLE ai_requests(id INTEGER PRIMARY KEY AUTOINCREMENT,owner INTEGER,request_key TEXT,fingerprint TEXT,domain TEXT,model TEXT,rate_snapshot TEXT,state TEXT,reserved NUMERIC,buy_cost NUMERIC,user_charge NUMERIC,input_tokens INTEGER,cached_tokens INTEGER,output_tokens INTEGER,provider_id TEXT DEFAULT '',encrypted_response TEXT,created INTEGER,updated INTEGER,UNIQUE(owner,request_key));
        CREATE TABLE ai_balance_ledger(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,request_key TEXT,amount NUMERIC,reason TEXT,actor TEXT,created INTEGER,UNIQUE(user_id,request_key));
        CREATE TABLE audit(actor TEXT,action TEXT,created INTEGER);
        ''')
        self.cfg=dict(ai.DEFAULT,enabled=True,key_id=1,model='test-snapshot',input_rate='1',cached_rate='0.25',output_rate='2',domains=['example.com'],pricing_reviewed=True,price_reference='verified-account-rates')
        self.raw.execute('INSERT INTO ai_service_config VALUES(1,?)',(json.dumps(self.cfg),));self.raw.execute('INSERT INTO ai_balances VALUES(1,10)');self.raw.commit()
        self.user=dict(id=1,role='user',username='buyer')
        self.body=dict(action='chat',prompt='Hello',domain='example.com',request_key='request_123456789012',confirmed=True,pricing_version=ai.pricing_version(self.cfg))
        raw=self.raw
        class Cursor:
            def __init__(self,c):self.c=c;self.lastrowid=c.lastrowid
            def fetchone(self):
                r=self.c.fetchone();return dict(r) if r else None
            def fetchall(self):return [dict(r) for r in self.c.fetchall()]
        class Con:
            def execute(self,sql,args=()):
                sql=sql.replace('INSERT IGNORE','INSERT OR IGNORE').replace(' FOR UPDATE','')
                args=tuple(str(a) if isinstance(a,Decimal) else a for a in args)
                return Cursor(raw.execute(sql,args))
        @contextmanager
        def db():
            try:yield Con();raw.commit()
            except Exception:raw.rollback();raise
        self.db=db
    def tearDown(self):self.raw.close();self.env.stop();self.tmp.cleanup()
    def response(self):return dict(model='test-snapshot',id='provider-id',usage=dict(prompt_tokens=1000,completion_tokens=500,prompt_tokens_details=dict(cached_tokens=200)),choices=[dict(message=dict(content='Answer'))])
    def test_exact_markup_and_cached_discount(self):
        cost,*tokens=ai.cost_for(self.response()['usage'],self.cfg)
        self.assertEqual(cost,Decimal('0.0018500000'));self.assertEqual(ai.billed(cost),Decimal('0.0024050000'))
        self.assertEqual(ai.billed(Decimal('10')),Decimal('13.0000000000'))
    def test_success_retries_return_saved_result_and_debit_once(self):
        with patch.object(ai.api_keys,'resolve_openai',return_value='private'),patch.object(ai,'provider_call',return_value=self.response()) as provider:
            first=ai.chat(self.user,self.body,self.db);second=ai.chat(self.user,self.body,self.db)
            self.assertEqual(first['answer'],'Answer');self.assertEqual(second['answer'],'Answer');provider.assert_called_once()
        balance=self.raw.execute('SELECT balance FROM ai_balances').fetchone()[0]
        self.assertAlmostEqual(balance,9.997595,places=9)
        encrypted=self.raw.execute('SELECT encrypted_response FROM ai_requests').fetchone()[0]
        self.assertNotIn('Answer',encrypted)
    def test_timeout_holds_for_review_and_does_not_retry(self):
        with patch.object(ai.api_keys,'resolve_openai',return_value='private'),patch.object(ai,'provider_call',side_effect=TimeoutError('private')) as provider:
            result=ai.chat(self.user,self.body,self.db);self.assertEqual(result['state'],'needs_review')
            self.assertNotIn('private',str(result));ai.chat(self.user,self.body,self.db);provider.assert_called_once()
    def test_rejected_provider_request_releases_entire_reserve(self):
        error=HTTPError('https://api.openai.com',401,'private',{},None)
        with patch.object(ai.api_keys,'resolve_openai',return_value='private'),patch.object(ai,'provider_call',side_effect=error):
            result=ai.chat(self.user,self.body,self.db)
        self.assertEqual(result['state'],'failed');self.assertAlmostEqual(self.raw.execute('SELECT balance FROM ai_balances').fetchone()[0],10,places=9)
    def test_insufficient_credit_no_api_call(self):
        self.raw.execute('UPDATE ai_balances SET balance=0');self.raw.commit()
        with patch.object(ai.api_keys,'resolve_openai',return_value='private'),patch.object(ai,'provider_call') as provider:
            with self.assertRaises(ValueError):ai.chat(self.user,self.body,self.db)
            provider.assert_not_called()
    def test_changed_rates_and_readonly_rejected(self):
        with self.assertRaises(ValueError):ai.chat(self.user,dict(self.body,pricing_version='stale'),self.db)
        with self.assertRaises(PermissionError):ai.chat(dict(self.user,role='readonly'),self.body,self.db)
    def test_no_usage_or_wrong_model_never_creates_unverified_charge(self):
        for response in [dict(self.response(),usage=None),dict(self.response(),model='different')]:
            self.raw.execute('DELETE FROM ai_requests');self.raw.execute('DELETE FROM ai_balance_ledger');self.raw.commit()
            with patch.object(ai.api_keys,'resolve_openai',return_value='private'),patch.object(ai,'provider_call',return_value=response):
                result=ai.chat(self.user,self.body,self.db)
            self.assertEqual(result['state'],'needs_review');self.assertIsNone(result['user_charge'])
    def test_manual_credit_idempotent_and_restricted(self):
        body=dict(action='credit',user_id=1,amount='2',note='Received payment',request_key='credit_123456789012')
        with self.assertRaises(PermissionError):ai.handle('POST',self.user,body,self.db)
        admin=dict(self.user,role='super_admin')
        ai.handle('POST',admin,body,self.db);ai.handle('POST',admin,body,self.db)
        self.assertEqual(self.raw.execute('SELECT balance FROM ai_balances').fetchone()[0],12)
    def test_resolver_enforces_domains_enabled_expiry(self):
        admin=dict(role='super_admin');api_keys.handle('POST',admin,dict(action='save',provider='openai',label='x',secret='private',enabled=True,domains=['example.com']))
        self.assertEqual(api_keys.resolve_openai(1,'example.com'),'private')
        with self.assertRaises(ValueError):api_keys.resolve_openai(1,'other.com')
        api_keys.handle('POST',admin,dict(action='save',id=1,provider='openai',label='x',secret='',enabled=False,domains=['example.com']))
        with self.assertRaises(ValueError):api_keys.resolve_openai(1,'example.com')

if __name__=='__main__':unittest.main()
