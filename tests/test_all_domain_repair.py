import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
spec=importlib.util.spec_from_file_location('all_repair',Path(__file__).resolve().parents[1]/'deploy/repair_all_hosting.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class AllDomainRepairTests(unittest.TestCase):
 def test_insecure_mapping_and_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'mapping';path.write_text('{"targets":{}}');path.chmod(0o644)
   with self.assertRaises(ValueError):m.load_approved(path)
   path.chmod(0o600);self.assertEqual(m.load_approved(path),{})
   link=Path(temp)/'alias';link.symlink_to(path)
   with self.assertRaises(ValueError):m.load_approved(link)
 def test_panel_failure_does_not_prevent_domain_repair(self):
  with tempfile.TemporaryDirectory() as temp:
   def call(argv,timeout=30):
    out=''
    if '--discover' in argv:out='["site.example"]'
    elif argv[:2]==['runuser','-u']:out='[]'
    elif argv[:2]==['systemctl','is-active']:out='active'
    elif argv[0]=='curl':out='<title>OlamidePanel</title><form id="loginForm">'
    return SimpleNamespace(returncode=0,stdout=out,stderr='')
   stages=[]
   def stage(argv,log,timeout):
    stages.append(argv[1]);log.write_text(json.dumps({'domains':[{'domain':'site.example','status':'https_verified'}]}))
    return {'state':'failed' if 'restore_panel_domain.py' in argv[1] else 'passed'}
   base=Path(temp)/'repair'
   with patch.object(m,'BASE',base),patch.object(m,'load_approved',return_value={}),patch.object(m,'call',side_effect=call),patch.object(m,'run_stage',side_effect=stage),patch('builtins.print'):
    self.assertEqual(m.main({},Path('/trusted')),1)
   self.assertEqual(len(stages),2)
   report=json.loads((base/'report.json').read_text())
   self.assertEqual(report['status'],'incomplete')
   self.assertEqual(report['requires_mapping'],['site.example'])
   self.assertFalse(report['domains'][0]['application_identity_verified'])
if __name__=='__main__':unittest.main()
