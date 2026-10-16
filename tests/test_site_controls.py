import copy,importlib.util,json,os,pwd,shutil,socket,subprocess,sys,tempfile,time,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import MagicMock,patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'panel'));sys.path.insert(0,str(ROOT/'deploy'))
import site_controls
import apply_site_controls

class SiteControlTests(unittest.TestCase):
 def test_typed_values_and_redirect_cycles(self):
  s=site_controls.defaults();s['redirects']=[{'path':'/old','target':'https://example.net/new','status':302}];s['blocked_ips']=['192.0.2.7','2001:db8::/32'];s['errors']={'404':'Not here <script>'};s['hotlink']=True
  checked=site_controls.validate(s,'example.com');self.assertEqual(checked['blocked_ips'][0],'192.0.2.7/32');self.assertIn('return 302 "https://example.net/new";',site_controls.nginx(s,'example.com'))
  for patch_value in [{'indexes':'on'},{'blocked_ips':['127.0.0.1; allow all']},{'referers':['bad; return 200']},{'errors':{'200':'invalid'}}]:
   with self.assertRaises(ValueError):site_controls.validate({**s,**patch_value},'example.com')
  for rule in [{'path':'/.secret','target':'https://example.net','status':302},{'path':'/x','target':'https://example.net/$http_cookie','status':302},{'path':'/x','target':'https://user:pass@example.net','status':302},{'path':'/x','target':'https://example.com/x','status':302}]:
   with self.assertRaises(ValueError):site_controls.validate({**s,'redirects':[rule]},'example.com')
 def test_old_error_documents_remain_internal_after_disabling_custom_pages(self):
  self.assertIn('location ^~ /_panel-errors/ { internal; }',site_controls.nginx(site_controls.defaults(),'example.com'))
 def test_rejects_cross_owner_and_stale_writes(self):
  user={'id':7,'role':'user','username':'test'};body={'domain_id':1,'revision':0,'settings':site_controls.defaults()}
  with patch.object(site_controls,'connect') as db:
   con=db.return_value.__enter__.return_value;con.execute.return_value.fetchone.return_value=None
   self.assertEqual(site_controls.handle('POST',user,body)[0],404)
   self.assertEqual(con.execute.call_args.args[1],(1,7))
  self.assertEqual(site_controls.handle('POST',{**user,'role':'readonly'},body)[0],403)
  with patch.object(site_controls,'connect') as db:
   con=db.return_value.__enter__.return_value;con.execute.return_value.fetchone.side_effect=[{'id':1,'name':'example.com'},{'revision':2}]
   self.assertEqual(site_controls.handle('POST',user,body)[0],409)
   self.assertFalse(any('INSERT' in call.args[0] for call in con.execute.call_args_list))
 def test_failed_nginx_check_restores_prior_configuration_and_error_pages(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);site=root/'site';site.mkdir();target=root/'site.conf';original='server { '+apply_site_controls.MARKER+' }';target.write_text(original);include=root/'includes/1.conf';settings=site_controls.defaults();settings['errors']={'404':'Test'}
   def fail():raise RuntimeError('invalid')
   with self.assertRaises(RuntimeError):apply_site_controls.apply(site,target,include,settings,'example.com',fail,lambda:None)
   self.assertEqual(target.read_text(),original);self.assertFalse(include.exists());self.assertFalse((site/'_panel-errors/404.html').exists())
 def test_include_is_inserted_after_hidden_file_protection_and_is_idempotent(self):
  original='server { '+apply_site_controls.MARKER+' }';path=Path('/etc/nginx/olamidepanel-static/1.conf');result=apply_site_controls.prepare_config(original,path)
  self.assertGreater(result.index('include '),result.index('deny all'))
  self.assertEqual(result,apply_site_controls.prepare_config(result,path))

@unittest.skipUnless(shutil.which('nginx'),'Nginx executable required for configuration and HTTP acceptance')
class NginxAcceptance(unittest.TestCase):
 def test_redirects_indexes_errors_hidden_files_and_hotlink_behavior(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);site=root/'site';site.mkdir();(site/'folder').mkdir();(site/'folder/readme.txt').write_text('hello');(site/'photo.png').write_bytes(b'image');(site/'.private.png').write_bytes(b'secret')
   sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
   target=root/'site.conf';target.write_text('server { listen 127.0.0.1:'+str(port)+'; server_name example.com; root '+str(site)+'; index index.html; location / { try_files $uri $uri/ =404; } '+apply_site_controls.MARKER+' }')
   config=root/'nginx.conf';config.write_text('user '+pwd.getpwuid(os.getuid()).pw_name+'; pid '+str(root/'nginx.pid')+'; error_log stderr; events {} http { access_log off; include '+str(target)+'; }')
   settings=site_controls.defaults();settings.update(indexes=True,hotlink=True,errors={'404':'Custom missing page'});settings['redirects']=[{'path':'/old','target':'https://example.net/new','status':302}]
   def check():subprocess.run(['nginx','-t','-p',str(root),'-c',str(config)],check=True,capture_output=True)
   apply_site_controls.apply(site,target,root/'includes/1.conf',settings,'example.com',check,lambda:None)
   process=subprocess.Popen(['nginx','-p',str(root),'-c',str(config),'-g','daemon off;'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
   opener=urllib.request.build_opener(NoRedirect())
   def request(path,referer=None):
    req=urllib.request.Request('http://127.0.0.1:'+str(port)+path,headers={'Host':'example.com',**({'Referer':referer} if referer else {})})
    try:
     with opener.open(req,timeout=2) as response:return response.status,response.headers,response.read()
    except urllib.error.HTTPError as response:return response.code,response.headers,response.read()
   try:
    for _ in range(30):
     try:response=request('/folder/');break
     except OSError:time.sleep(.05)
    self.assertEqual(response[0],200);self.assertIn(b'readme.txt',response[2]);self.assertEqual(request('/old')[0],302)
    self.assertEqual(request('/old')[1]['Location'],'https://example.net/new');self.assertIn(b'Custom missing page',request('/absent')[2]);self.assertEqual(request('/.private.png')[0],403)
    self.assertEqual(request('/photo.png','https://evil.example/')[0],403);self.assertEqual(request('/photo.png','https://example.com/page')[0],200)
    self.assertEqual(request('/_panel-errors/404.html')[0],404)
    settings['blocked_ips']=['127.0.0.1']
    apply_site_controls.apply(site,target,root/'includes/1.conf',settings,'example.com',check,lambda:subprocess.run(['nginx','-p',str(root),'-c',str(config),'-s','reload'],check=True,capture_output=True))
    for _ in range(30):
     response=request('/folder/')
     if response[0]==403:break
     time.sleep(.05)
    self.assertEqual(response[0],403)
   finally:process.terminate();process.wait(timeout=5)
