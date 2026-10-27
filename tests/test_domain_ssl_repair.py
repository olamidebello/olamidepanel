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
