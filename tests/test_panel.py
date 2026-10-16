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
