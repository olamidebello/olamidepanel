import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('hosted_services',Path(__file__).resolve().parents[1]/'integrations/hosted_services.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class HostedServicesTests(unittest.TestCase):
 def test_verified_identity_only_and_retries_deduplicate(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'jobs.sqlite';data=dict(subject='1',email='a@example.com',name='Alice',account_type='individual',email_verified=False)
   with self.assertRaises(ValueError):m.enqueue(path,**data)
   self.assertFalse(path.exists());data['email_verified']=True
   m.enqueue(path,**data);m.enqueue(path,**data)
   with m.connect(path) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM registrations').fetchone()[0],1)
   with self.assertRaises(ValueError):m.enqueue(path,**{**data,'email':'b@example.com'})
 def test_network_failure_is_durable_and_not_reported_provisioned(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'jobs.sqlite';m.enqueue(path,subject='1',email='a@example.com',name='Alice',account_type='court',email_verified=True,organization_id='court1')
   with patch.object(m.urllib.request,'build_opener',side_effect=OSError('offline')):m.run({'database':str(path),'token':'a'*40,'app_id':'test'})
   self.assertEqual(m.status(path,'1')['state'],'retry')
 def test_success_stores_safe_phone_result(self):
  import io
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'jobs.sqlite';m.enqueue(path,subject='1',email='a@example.com',name='Alice',account_type='individual',email_verified=True)
   class Opener:
    def open(self,*a,**k):return io.BytesIO(json.dumps({'sipStatus':'awaiting_switch','pbxWorkspace':False}).encode())
   with patch.object(m.urllib.request,'build_opener',return_value=Opener()):m.run({'database':str(path),'token':'a'*40,'app_id':'test'})
   result=m.status(path,'1');self.assertEqual(result['state'],'provisioned');self.assertEqual(result['phone']['sipStatus'],'awaiting_switch')
if __name__=='__main__':unittest.main()
