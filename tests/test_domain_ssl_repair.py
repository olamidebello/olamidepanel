import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('repair',Path(__file__).resolve().parents[1]/'deploy/repair_domain_ssl.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RoutingTests(unittest.TestCase):
 def test_exact_domain_and_comment_quoting(self):
  text='server { # } ignored\n server_name one.example; location / { proxy_pass http://127.0.0.1:9999; } } server { server_name two.example; }'
  self.assertEqual(len(m.blocks(text,'one.example')),1);self.assertEqual(m.blocks(text,'example'),[])
 def test_only_root_proxy_changes(self):
  body='location /api/ { proxy_pass http://127.0.0.1:4000; } location / { proxy_pass http://127.0.0.1:3000; }'
  result,hit=m.root_proxy_patch(body,18840)
  self.assertTrue(hit);self.assertIn('http://127.0.0.1:4000;',result);self.assertIn('http://127.0.0.1:18840;',result)
 def test_unusual_backend_is_not_rewritten(self):
  with self.assertRaises(ValueError):m.root_proxy_patch('location / { proxy_pass https://upstream.example/api; }',18840)
 def test_duplicate_roots_are_rejected(self):
  with self.assertRaises(ValueError):m.root_proxy_patch('location / { proxy_pass http://127.0.0.1:3000; } location / { proxy_pass http://127.0.0.1:4000; }',18840)
if __name__=='__main__':unittest.main()

class DiagnosticsTests(unittest.TestCase):
 def test_reserved_retired_names_excluded_but_live_subdomains_retained(self):
  self.assertTrue(m.excluded_name('retired-oob.invalid'))
  self.assertTrue(m.excluded_name('mail.your-domain.com'))
  self.assertFalse(m.excluded_name('mail.olamidepanel.com'))
 def test_error_has_phase_exit_code_and_real_curl_detail(self):
  import subprocess
  error=subprocess.CalledProcessError(22,['curl','https://justisolve.com/'],stderr='curl: (22) The requested URL returned error: 502')
  result=m.failure_details(error,'https_response')
  self.assertEqual(result['exit_code'],22)
  self.assertEqual(result['phase'],'https_response')
  self.assertIn('502',result['detail'])

class CurrentDnsTests(unittest.TestCase):
 def test_remote_dns_is_checked_without_local_route_or_certificate_changes(self):
  import tempfile
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as temp:
   original_path=Path
   def path(value):return original_path(temp)/'report' if value=='/var/lib/olamide-domain-ssl-repair' else original_path(value)
   config={'ipv4':'154.16.170.86','email':'operator@example.com','domains':['weatherangola.africandroid.world'],'follow_current_dns':True}
   with patch.object(m,'Path',side_effect=path),patch.object(m,'dns',side_effect=lambda d,k:{'181.214.149.146'} if k=='A' else set()),patch.object(m,'run',return_value='') as commands,patch.object(m,'repair',side_effect=AssertionError('must not edit remote domain locally')),patch.object(m.subprocess,'run',side_effect=AssertionError('must not invoke Certbot')),patch('builtins.print'):
    self.assertEqual(m.main(config),0)
   import json
   row=json.loads((original_path(temp)/'report/report.json').read_text())['domains'][0]
   self.assertEqual(row['status'],'https_verified_on_current_dns_server')
   self.assertFalse(row['routing_changed']);self.assertNotIn('--resolve',commands.call_args.args[0])
