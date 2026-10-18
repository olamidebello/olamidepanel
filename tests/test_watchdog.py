import importlib.util
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'panel'))
import watchdog
spec=importlib.util.spec_from_file_location('watchdog_runner',Path(__file__).resolve().parents[1]/'deploy/watchdog.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

class WatchdogTests(unittest.TestCase):
 def test_report_authorization_before_database_access(self):
  def forbidden():self.fail('Unauthorized database access')
  for role in ('user','reseller','admin','readonly'):
   with self.assertRaises(PermissionError):watchdog.report({'role':role},forbidden)
 def test_restart_threshold_and_cooldown(self):
  target={'service':'example.service'};bad={'https':True,'backend_1':False}
  self.assertEqual(runner.decide(bad,{},2000,target),(1,'observing'))
  self.assertEqual(runner.decide(bad,{'failures':1},2000,target),(2,'restart_pending'))
  self.assertEqual(runner.decide(bad,{'failures':1,'last_restart':1900},2000,target),(2,'cooldown'))
 def test_https_failure_does_not_restart_healthy_backend(self):
  self.assertEqual(runner.decide({'https':False,'backend_1':True},{'failures':1},2000,{'service':'example.service'})[1],'routing_or_tls_attention')
 def test_unmapped_domain_never_restarts(self):
  self.assertEqual(runner.decide({'https':False},{'failures':1},2000,{})[1],'operator_required')
 def test_recovery_resets_failures(self):
  self.assertEqual(runner.decide({'https':True},{'failures':20},2000,{}),(0,'healthy'))
 def test_probes_use_loopback_and_no_shell(self):
  from unittest.mock import patch
  class Result:returncode=0;stdout='200'
  with patch.object(runner,'command',return_value=Result()) as cmd:
   self.assertTrue(runner.probe('example.com',{})['https'])
   args=cmd.call_args.args[0]
   self.assertIn('example.com:443:127.0.0.1',args)
   self.assertNotIn('--location',args)
 def test_database_backed_expected_json_is_required(self):
  from unittest.mock import patch
  class Result:returncode=0;stdout='200'
  with patch.object(runner,'command',return_value=Result()):
   checks=runner.probe('example.com',{'checks':[{'port':8090,'path':'/api/setup/status','field':'required','value':False}]})
   self.assertFalse(checks['backend_1'])
