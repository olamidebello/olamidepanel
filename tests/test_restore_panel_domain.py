import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('restore',Path(__file__).resolve().parents[1]/'deploy/restore_panel_domain.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class PanelRepairTests(unittest.TestCase):
 def test_shared_media_block_retains_media_name_and_routes(self):
  text='server { listen 443 ssl; server_name media.example olamidepanel.com; location / { proxy_pass http://127.0.0.1:9876; } }'
  new,count=m.strip_domain(text)
  self.assertEqual(count,1);self.assertIn('server_name media.example;',new);self.assertIn('127.0.0.1:9876',new);self.assertNotIn('olamidepanel.com',new)
 def test_apex_only_block_removed_other_server_preserved(self):
  other='server { server_name media.example; location / { return 200; } }'
  new,count=m.strip_domain('server { server_name olamidepanel.com; } '+other)
  self.assertEqual(new.strip(),other);self.assertEqual(count,1)
 def test_comments_and_quotes_do_not_break_parser(self):
  new,count=m.strip_domain('server { # }\n server_name "olamidepanel.com" media.example; set $x "}"; }')
  self.assertEqual(count,1);self.assertIn('media.example',new);self.assertIn('set $x "}";',new)
 def test_unrelated_suffix_not_removed(self):
  text='server { server_name sub.olamidepanel.com; }'
  self.assertEqual(m.strip_domain(text),(text,0))
 def test_identity_requires_panel_login(self):
  self.assertFalse(m.panel_body('<title>Africa Media Hub</title>'))
  self.assertTrue(m.panel_body('<title>OlamidePanel</title><form id="loginForm">'))
if __name__=='__main__':unittest.main()

class RollbackTests(unittest.TestCase):
 def test_wrong_response_rolls_back_routing_and_keeps_other_application(self):
  import tempfile
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);old=root/'media.conf';text='server { server_name media.example olamidepanel.com; location / { proxy_pass http://127.0.0.1:9876; } }';old.write_text(text)
   new=root/'restored.conf';base=root/'report'
   panel='<title>OlamidePanel</title><form id="loginForm">'
   def cmd(args,timeout=30):
    if args[0]=='curl':return panel if 'http://127.0.0.1:8090/' in args else '<title>Africa Media Hub</title>'
    return ''
   with patch.object(m,'BASE',base),patch.object(m,'CONF',new),patch.object(m,'command',side_effect=cmd),patch.object(m,'files',return_value={old:text}),patch.object(m,'valid_existing_cert',return_value=False):
    self.assertEqual(m.main(),1)
   self.assertEqual(old.read_text(),text);self.assertFalse(new.exists())
   import json
   result=json.loads((base/'report.json').read_text());self.assertTrue(result['rolled_back'])
