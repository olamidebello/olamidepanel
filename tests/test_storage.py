import base64,io,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'panel'))
import storage

class StorageTest(unittest.TestCase):
 def setUp(self):
  self.quota_patch=patch.object(storage,'quota',side_effect=lambda uid:storage.QUOTA);self.quota_patch.start();self.addCleanup(self.quota_patch.stop)
  self.tmp=tempfile.TemporaryDirectory();self.patch=patch.object(storage,'DATA',Path(self.tmp.name));self.patch.start();self.user={'id':11,'role':'user'}
 def tearDown(self):self.patch.stop();self.tmp.cleanup()
 def action(self,**body):return storage.handle('POST','/api/storage/files',self.user,body)
 def test_upload_download_isolation_and_overwrite(self):
  self.action(action='upload',path='a.txt',content_base64=base64.b64encode(b'first').decode())
  with self.assertRaises(ValueError):self.action(action='upload',path='a.txt',content_base64='Yg==')
  self.action(action='upload',path='a.txt',content_base64='Yg==',overwrite=True)
  self.assertEqual(storage.download(self.user,'/api/storage/download?path=a.txt'),('a.txt',b'b'))
  self.assertEqual(storage.handle('GET','/api/storage/files',{'id':12,'role':'user'}),[])
  with self.assertRaises(ValueError):storage.path(11,'../../escape')
  (storage.home(11)/'link').symlink_to('/etc')
  with self.assertRaises(ValueError):storage.path(11,'link/passwd')
 def test_large_editor_refuses_without_truncation(self):
  content=b'a'*(1024**2+1);storage.write(11,storage.path(11,'large'),content)
  with self.assertRaises(ValueError):storage.handle('GET','/api/storage/files?path=large',self.user)
  self.assertEqual(storage.path(11,'large').read_bytes(),content)
 def test_archive_and_restore_keep_original(self):
  self.action(action='write',path='a.txt',content='original')
  backup=storage.handle('POST','/api/storage/backups',self.user,{'action':'create'})
  self.action(action='write',path='a.txt',content='changed')
  result=storage.handle('POST','/api/storage/backups',self.user,{'action':'restore','id':backup['id'],'confirmed':True})
  self.assertEqual((storage.home(11)/result['folder']/'a.txt').read_text(),'original')
  self.assertEqual(storage.path(11,'a.txt').read_text(),'changed')
  with self.assertRaises(ValueError):storage.download({'id':12},'/api/storage/download?backup='+backup['id'])
 def test_archive_traversal_links_and_rollback(self):
  for name,mode in [('../escape',0),('/escape',0),('symlink',0o120777<<16)]:
   out=io.BytesIO()
   with zipfile.ZipFile(out,'w') as z:
    entry=zipfile.ZipInfo(name);entry.external_attr=mode;z.writestr(entry,'data')
   with self.assertRaises(ValueError):storage.extract(11,out.getvalue(),storage.path(11,'out'))
   self.assertFalse(storage.path(11,'out').exists())
  out=io.BytesIO()
  with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('file','x'*200)
  with patch.object(storage,'ARCHIVE_MAX',100):
   with self.assertRaises(ValueError):storage.extract(11,out.getvalue(),storage.path(11,'out'))
  self.assertFalse(list(storage.home(11).glob('.panel-extract-*')))
 def test_quota_readonly_and_images(self):
  with patch.object(storage,'QUOTA',2):
   with self.assertRaises(ValueError):self.action(action='write',path='a',content='long')
  with self.assertRaises(PermissionError):storage.handle('POST','/api/storage/files',{'id':11,'role':'readonly'},{'action':'mkdir','path':'a'})
  from PIL import Image
  Image.new('RGB',(100,60)).save(storage.path(11,'source.png'))
  self.action(action='image',path='source.png',destination='small.webp',width=40,height=40,format='WEBP')
  with Image.open(storage.path(11,'small.webp')) as image:self.assertEqual(image.size,(40,24))
  with self.assertRaises(ValueError):self.action(action='image',path='source.png',destination='invalid.png',width=0,height=40)
