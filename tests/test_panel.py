import importlib.util, os, tempfile, unittest, threading, urllib.request, urllib.error, json
from pathlib import Path

class PanelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('PANEL_TEST_MYSQL'): raise unittest.SkipTest('Set PANEL_TEST_MYSQL=1 and PANEL_DB_CONFIG to a disposable MySQL database')
        cls.tmp=tempfile.TemporaryDirectory(); os.environ['PANEL_DATA']=cls.tmp.name
        spec=importlib.util.spec_from_file_location('panel',Path(__file__).parents[1]/'panel/server.py'); cls.p=importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.p)
        cls.p.initialize(); cls.p.create_user('admin','a-long-test-password','admin'); cls.p.create_user('other','another-long-password','user')
        cls.server=cls.p.ThreadingHTTPServer(('127.0.0.1',0),cls.p.Handler);cls.server.attempts={};threading.Thread(target=cls.server.serve_forever,daemon=True).start()
        cls.url='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls): cls.server.shutdown();cls.server.server_close();cls.tmp.cleanup()
    def request(self,path,data=None,cookie='',csrf=''):
        r=urllib.request.Request(self.url+'/api/'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Cookie':cookie,'X-CSRF-Token':csrf,'Content-Type':'application/json'})
        return urllib.request.urlopen(r)
    def login(self,name='admin',password='a-long-test-password'):
        r=self.request('login',{'username':name,'password':password,'accept_terms':True}); cookie=r.headers['Set-Cookie'].split(';')[0]
        return cookie,json.load(self.request('me',cookie=cookie))['csrf']
    def test_auth_required(self):
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('metrics')
        self.assertEqual(e.exception.code,401)
    def test_csrf_required(self):
        cookie,_=self.login()
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('domains',{'name':'example.com'},cookie)
        self.assertEqual(e.exception.code,403)
    def test_files_and_isolation(self):
        cookie,csrf=self.login(); self.request('files',{'action':'write','path':'hello.txt','content':'hello'},cookie,csrf)
        self.assertEqual(json.load(self.request('files?path=hello.txt',cookie=cookie))['content'],'hello')
        other,_=self.login('other','another-long-password');self.assertEqual(json.load(self.request('files?path=',cookie=other)),[])
        with self.assertRaises(ValueError):self.p.safe_path(1,'../../panel.db')
        (self.p.home(1)/'link').symlink_to('/etc')
        with self.assertRaises(ValueError):self.p.safe_path(1,'link/passwd')
    def test_user_cannot_admin(self):
        cookie,csrf=self.login('other','another-long-password')
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('users',{'username':'intruder','password':'very-long-password'},cookie,csrf)
        self.assertEqual(e.exception.code,404)
    def test_domain_inventory(self):
        cookie,csrf=self.login();self.request('domains',{'name':'example.com'},cookie,csrf)
        self.assertEqual(json.load(self.request('domains',cookie=cookie))[0]['name'],'example.com')
        other,_=self.login('other','another-long-password');self.assertEqual(json.load(self.request('domains',cookie=other)),[])
    def test_access_levels_and_suspension(self):
        self.p.create_user('owner','owner-long-password','root')
        self.p.create_user('manager','manager-long-password','super_admin')
        cookie,csrf=self.login('manager','manager-long-password')
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.request('users',{'username':'elevated','password':'elevated-long-password','role':'root'},cookie,csrf)
        self.assertEqual(e.exception.code,403)
        self.request('users',{'username':'reader','password':'reader-long-password','role':'readonly'},cookie,csrf)
        reader,reader_csrf=self.login('reader','reader-long-password')
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.request('files',{'action':'write','path':'bad','content':'bad'},reader,reader_csrf)
        self.assertEqual(e.exception.code,403)
        users=json.load(self.request('users',cookie=cookie)); uid=next(u['id'] for u in users if u['username']=='reader')
        self.request('users/update',{'id':uid,'role':'readonly','active':False},cookie,csrf)
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('me',cookie=reader)
        self.assertEqual(e.exception.code,401)
        owner_id=next(u['id'] for u in users if u['username']=='owner')
        with self.assertRaises(urllib.error.HTTPError):self.request('users/update',{'id':owner_id,'role':'user','active':False},cookie,csrf)
    def test_provision_idempotent(self):
        body={'username':'automatic','password':'automatic-long-password','role':'user','active':True}
        self.assertTrue(self.p.provision_user(body)['changed'])
        self.assertFalse(self.p.provision_user(body)['changed'])
    def test_user_lifecycle(self):
        self.p.create_user('lifecycle','lifecycle-password','user')
        with self.p.db() as con: uid=con.execute("SELECT id FROM users WHERE username='lifecycle'").fetchone()['id']
        actor={'id':99999,'role':'root'}
        self.p.manage_user(actor,{'id':uid,'action':'profile','email':'person@example.com','display_name':'Person'})
        with self.p.db() as con:self.assertEqual(con.execute('SELECT email FROM users WHERE id=?',(uid,)).fetchone()['email'],'person@example.com')
        self.p.manage_user(actor,{'id':uid,'action':'password','password':'replacement-password'})
        with self.p.db() as con:
            row=con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
            self.assertEqual(row['password'],self.p.password_hash('replacement-password',row['salt']))
        with self.assertRaises(ValueError):self.p.manage_user(actor,{'id':uid,'action':'delete','confirmation':'lifecycle'})
        self.p.update_user(actor,{'id':uid,'role':'user','active':False})
        with self.assertRaises(ValueError):self.p.manage_user(actor,{'id':uid,'action':'delete','confirmation':'wrong'})
        self.p.manage_user(actor,{'id':uid,'action':'delete','confirmation':'lifecycle'})
        with self.p.db() as con:self.assertIsNone(con.execute('SELECT id FROM users WHERE id=?',(uid,)).fetchone())
    def test_account_action_cannot_target_superior(self):
        with self.p.db() as con: uid=con.execute("SELECT id FROM users WHERE username='admin'").fetchone()['id']
        with self.assertRaises(ValueError):self.p.manage_user({'id':9999,'role':'user'},{'id':uid,'action':'password','password':'replacement-password'})

    def test_deleted_storage_never_reassigned(self):
        self.p.create_user('retained','retained-password','user')
        with self.p.db() as con: uid=con.execute("SELECT id FROM users WHERE username='retained'").fetchone()['id']
        (self.p.home(uid)/'private.txt').write_text('private')
        actor={'id':9999,'role':'root'}
        self.p.update_user(actor,{'id':uid,'role':'user','active':False})
        self.p.manage_user(actor,{'id':uid,'action':'delete','confirmation':'retained'})
        self.p.create_user('newowner','newowner-password','user')
        with self.p.db() as con: new_id=con.execute("SELECT id FROM users WHERE username='newowner'").fetchone()['id']
        self.assertNotEqual(uid,new_id)
        self.assertFalse((self.p.home(new_id)/'private.txt').exists())
    def test_login_requires_terms_confirmation(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.request('login',{'username':'admin','password':'a-long-test-password'})
        self.assertEqual(e.exception.code,400)
    def test_legal_pages_public(self):
        for path in ['/terms','/privacy','/copyright']:
            with urllib.request.urlopen(self.url+path) as response:
                self.assertEqual(response.status,200)
                self.assertIn(b'OlamidePanel',response.read())
    def test_marketplace_order_lifecycle(self):
        import marketplace
        with self.p.db() as con:
            uid=con.execute("SELECT id FROM users WHERE username='other'").fetchone()['id']
        admin={'id':999,'role':'root','username':'test-owner'}
        user={'id':uid,'role':'user','username':'other'}
        body={'name':'Test plan','description':'Integration test','price_cents':1500,'disk_gb':30,'bandwidth_gb':500,'websites':5,'enabled':True,'featured':False}
        status,result=marketplace.handle('POST','/api/marketplace/plans/save',admin,body)
        self.assertEqual(status,200);pid=result['id']
        request={'plan_id':pid,'expected_price_cents':1500,'request_key':'integration-request-0001','confirmed':True,'note':'Example'}
        _,order=marketplace.handle('POST','/api/marketplace/orders/create',user,request)
        _,again=marketplace.handle('POST','/api/marketplace/orders/create',user,request)
        self.assertEqual(order['id'],again['id']);self.assertTrue(again['duplicate'])
        with self.assertRaises(ValueError):marketplace.handle('POST','/api/marketplace/orders/create',user,{**request,'request_key':'integration-request-0002','expected_price_cents':100})
        _,approved=marketplace.handle('POST','/api/marketplace/orders/action',admin,{'id':order['id'],'action':'approve','operator_note':'Manual follow-up'})
        self.assertEqual(approved['status'],'approved')
        with self.assertRaises(ValueError):marketplace.handle('POST','/api/marketplace/orders/action',user,{'id':order['id'],'action':'cancel'})
        with self.p.db() as con:
            saved=con.execute('SELECT * FROM hosting_orders WHERE id=?',(order['id'],)).fetchone()
            self.assertIn('Test plan',saved['plan_snapshot'])
    def test_reseller_catalog_isolation(self):
        import marketplace
        for name in ['sellerone','sellertwo','shopbuyer']:
            self.p.create_user(name,'a-reseller-test-password','reseller' if name!='shopbuyer' else 'user')
        with self.p.db() as con:
            rows=con.execute("SELECT id,username,role FROM users WHERE username IN ('sellerone','sellertwo','shopbuyer')").fetchall()
        users={row['username']:dict(row) for row in rows}
        admin={'id':999,'role':'root','username':'test-operator'}
        plan={'name':'Reseller test','description':'Test allocation','price_cents':2500,'disk_gb':50,'bandwidth_gb':500,'websites':20,'enabled':True,'featured':False,'plan_kind':'reseller'}
        self.assertEqual(marketplace.handle('POST','/api/marketplace/plans/save',users['sellerone'],plan)[0],403)
        for name in ['sellerone','sellertwo']:
            marketplace.handle('POST','/api/marketplace/vendors/save',admin,{'id':users[name]['id'],'enabled':True})
        _,created=marketplace.handle('POST','/api/marketplace/plans/save',users['sellerone'],plan)
        pid=created['id']
        self.assertEqual(marketplace.handle('POST','/api/marketplace/plans/save',users['sellertwo'],{**plan,'id':pid})[0],403)
        _,order=marketplace.handle('POST','/api/marketplace/orders/create',users['shopbuyer'],{'plan_id':pid,'expected_price_cents':2500,'request_key':'reseller-order-0001','confirmed':True})
        self.assertEqual(marketplace.handle('POST','/api/marketplace/orders/action',users['sellertwo'],{'id':order['id'],'action':'approve'})[0],404)
        marketplace.handle('POST','/api/marketplace/vendors/save',admin,{'id':users['sellerone']['id'],'enabled':False})
        _,visible=marketplace.handle('GET','/api/marketplace/plans',users['shopbuyer'])
        self.assertNotIn(pid,[p['id'] for p in visible])
        self.assertEqual(marketplace.handle('POST','/api/marketplace/orders/action',users['sellerone'],{'id':order['id'],'action':'approve'})[0],404)
        marketplace.handle('POST','/api/marketplace/vendors/save',admin,{'id':users['sellerone']['id'],'enabled':True})
        _,approved=marketplace.handle('POST','/api/marketplace/orders/action',users['sellerone'],{'id':order['id'],'action':'approve'})
        self.assertEqual(approved['status'],'approved')
    def test_gateway_credentials_encrypted_and_scoped(self):
        import payments
        from cryptography.fernet import Fernet
        from unittest.mock import patch
        with self.p.db() as con:uid=con.execute("SELECT id FROM users WHERE username='other'").fetchone()['id']
        secret='sk_test_disposable_private_key'
        path=Path(self.tmp.name)/'payment.key';path.write_bytes(Fernet.generate_key())
        with patch.dict(os.environ,{'PANEL_PAYMENT_KEY':str(path)}):
            status,result=payments.handle('POST','/api/payments/gateways/save',{'id':999,'role':'root','username':'operator'},{'owner_id':0,'provider':'stripe','label':'Test merchant','mode':'test','enabled':True,'secret':secret,'webhook_secret':'whsec_example'})
            self.assertEqual(status,200)
            with self.p.db() as con:
                row=con.execute('SELECT * FROM payment_gateways WHERE id=?',(result['id'],)).fetchone()
                self.assertNotIn(secret,row['credentials'])
            self.assertEqual(payments.decrypt(row)['secret'],secret)
            _,listed=payments.handle('GET','/api/payments/gateways',{'role':'root'})
            self.assertNotIn(secret,json.dumps(listed))
            self.assertEqual(payments.handle('GET','/api/payments/gateways',{'id':uid,'role':'user'})[0],403)
    def test_mfa_enrollment_login_and_recovery(self):
        from cryptography.fernet import Fernet
        from unittest.mock import patch
        import mfa
        keyfile=Path(self.tmp.name)/'mfa.key';keyfile.write_bytes(Fernet.generate_key())
        self.p.create_user('mfauser','mfa-test-long-password','user')
        with patch.dict(os.environ,{'PANEL_PAYMENT_KEY':str(keyfile)}):
            cookie,csrf=self.login('mfauser','mfa-test-long-password')
            setup=json.load(self.request('mfa',{'action':'setup','current_password':'mfa-test-long-password'},cookie,csrf))
            code=mfa.code(setup['secret'],int(mfa.time.time())//30)
            enabled=json.load(self.request('mfa',{'action':'enable','current_password':'mfa-test-long-password','code':code},cookie,csrf))
            with self.assertRaises(urllib.error.HTTPError):self.request('me',cookie=cookie)
            with self.assertRaises(urllib.error.HTTPError):self.login('mfauser','mfa-test-long-password')
            body={'username':'mfauser','password':'mfa-test-long-password','accept_terms':True,'mfa_code':enabled['recovery_codes'][0]}
            response=self.request('login',body);cookie=response.headers['Set-Cookie'].split(';')[0]
            csrf=json.load(self.request('me',cookie=cookie))['csrf']
            with self.assertRaises(urllib.error.HTTPError):self.request('login',body)
            self.request('mfa',{'action':'disable','current_password':'mfa-test-long-password','code':enabled['recovery_codes'][1]},cookie,csrf)
            self.login('mfauser','mfa-test-long-password')
    def test_marketplace_store_settings_persistence_and_navigation(self):
        import marketplace
        self.p.create_user('storemerchant','store-merchant-password','reseller')
        self.p.create_user('storebuyer','store-buyer-long-password','user')
        with self.p.db() as con:
            seller=dict(con.execute("SELECT id,username,role FROM users WHERE username='storemerchant'").fetchone())
            buyer=dict(con.execute("SELECT id,username,role FROM users WHERE username='storebuyer'").fetchone())
        admin={'id':0,'username':'operator','role':'root'}
        marketplace.handle('POST','/api/marketplace/vendors/save',admin,{'id':seller['id'],'enabled':True})
        settings={'owner_id':seller['id'],'name':'Merchant Store','description':'Hosting shop','contact_email':'support@example.com'}
        self.assertEqual(marketplace.handle('POST','/api/marketplace/store/save',seller,settings)[0],200)
        _,stored=marketplace.handle('GET','/api/marketplace/store',seller);self.assertEqual(stored['name'],'Merchant Store')
        _,stores=marketplace.handle('GET','/api/marketplace/stores',buyer);self.assertTrue(any(row['name']=='Merchant Store' for row in stores))
        self.assertEqual(marketplace.handle('GET','/api/marketplace/store',buyer)[0],403)
        self.assertEqual(marketplace.handle('GET','/api/marketplace/orders?scope=store',buyer)[0],403)
        self.assertEqual(marketplace.handle('POST','/api/marketplace/store/save',seller,{**settings,'owner_id':0})[0],403)
        marketplace.handle('POST','/api/marketplace/vendors/save',admin,{'id':seller['id'],'enabled':False})
        self.assertEqual(marketplace.handle('POST','/api/marketplace/store/save',seller,settings)[0],403)
        _,stores=marketplace.handle('GET','/api/marketplace/stores',buyer);self.assertFalse(any(row['owner_id']==seller['id'] for row in stores))

    def test_site_controls_persist_revisions_and_enforce_ownership(self):
        cookie,csrf=self.login()
        self.request('domains',{'name':'controls.example.com'},cookie,csrf)
        domain=next(d for d in json.load(self.request('domains',cookie=cookie)) if d['name']=='controls.example.com')
        self.request('websites',{'domain_id':domain['id'],'title':'Control test','tagline':'Static test'},cookie,csrf)
        settings={'redirects':[{'path':'/old','target':'https://example.net/new','status':302}],'indexes':False,'errors':{'404':'Not found'},'hotlink':False,'referers':[],'blocked_ips':['192.0.2.1']}
        saved=self.request('site-controls',{'domain_id':domain['id'],'revision':0,'settings':settings},cookie,csrf)
        self.assertEqual(saved.status,202)
        row=next(d for d in json.load(self.request('site-controls',cookie=cookie)) if d['id']==domain['id'])
        self.assertEqual(row['revision'],1);self.assertEqual(row['applied_revision'],0);self.assertEqual(row['state'],'queued');self.assertEqual(row['settings']['blocked_ips'],['192.0.2.1/32'])
        with self.assertRaises(urllib.error.HTTPError) as stale:self.request('site-controls',{'domain_id':domain['id'],'revision':0,'settings':settings},cookie,csrf)
        self.assertEqual(stale.exception.code,409)
        other,other_csrf=self.login('other','another-long-password')
        with self.assertRaises(urllib.error.HTTPError) as denied:self.request('site-controls',{'domain_id':domain['id'],'revision':1,'settings':settings},other,other_csrf)
        self.assertEqual(denied.exception.code,404)
        self.assertFalse(any(d['id']==domain['id'] for d in json.load(self.request('site-controls',cookie=other))))
