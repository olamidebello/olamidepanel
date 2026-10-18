import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'panel'))
import module_manager as manager

class ModuleManagerTests(unittest.TestCase):
 def test_authorization_before_database(self):
  def forbidden():self.fail('Unauthorized access reached database')
  for role in ('admin','reseller','user','readonly'):
   with self.assertRaises(PermissionError):manager.report({'role':role},forbidden)
   with self.assertRaises(PermissionError):manager.queue({'role':role},{'adapter':'all','operation':'repair'},forbidden)
 def test_arbitrary_commands_and_paths_are_rejected(self):
  def forbidden():self.fail('Invalid request reached database')
  user={'role':'super_admin'}
  for body in ({'adapter':'../../tmp','operation':'repair'},{'adapter':'core','operation':'shell'},{'adapter':'nginx.service','operation':'repair'}):
   with self.assertRaises(ValueError):manager.queue(user,body,forbidden)
 def test_fixed_adapters_only_reference_existing_project_files(self):
  root=Path(__file__).resolve().parents[1]/'panel'
  for adapter,(files,deps) in manager.ADAPTERS.items():
   for name in files:
    self.assertTrue((root/name).is_file(),(adapter,name))
    self.assertNotIn('..',Path(name).parts)
 def test_bulk_jobs_and_audit_are_persisted(self):
  calls=[]
  class Connection:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def execute(self,sql,args=()):calls.append((sql,args));return self
   def fetchone(self):return None
  result=manager.queue({'id':1,'username':'operator','role':'root'},{'adapter':'all','operation':'repair'},Connection)
  jobs=[x for x in calls if x[0].startswith('INSERT INTO module_jobs')]
  self.assertEqual(result['queued'],len(manager.ADAPTERS))
  self.assertEqual(len(jobs),len(manager.ADAPTERS))
  self.assertTrue(any(x[0].startswith('INSERT INTO audit') for x in calls))
