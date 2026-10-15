import importlib.util, os, tempfile, unittest, threading, urllib.request, urllib.error, json
from pathlib import Path

class PanelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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
        r=self.request('login',{'username':name,'password':password}); cookie=r.headers['Set-Cookie'].split(';')[0]
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
