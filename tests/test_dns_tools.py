import sys,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).parents[1]/'panel'))
import dns_tools
class DnsToolsTest(unittest.TestCase):
 def test_reject_shell_input_and_unsupported_types(self):
  for name in ['example.com;id','$(id)','localhost','../etc/passwd','https://example.com']:
   with self.assertRaises(ValueError):dns_tools.lookup({'name':name})
  with self.assertRaises(ValueError):dns_tools.lookup({'name':'example.com','type':'AXFR'})
 def test_answers_and_timeout(self):
  resolver=MagicMock();record=MagicMock();record.to_text.return_value='192.0.2.1';answer=MagicMock();answer.__iter__.return_value=iter([record]);answer.rrset.ttl=300;resolver.resolve.return_value=answer
  with patch.object(dns_tools.dns.resolver,'Resolver',return_value=resolver):
   result=dns_tools.lookup({'name':'EXAMPLE.COM.','type':'A'});self.assertEqual(result['records'],['192.0.2.1']);self.assertEqual(result['ttl'],300)
   resolver.resolve.assert_called_with('example.com','A',search=False)
   resolver.resolve.side_effect=dns_tools.dns.exception.Timeout
   with self.assertRaisesRegex(ValueError,'timed out'):dns_tools.lookup({'name':'example.com'})
