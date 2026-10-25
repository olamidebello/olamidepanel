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
