import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'panel'))
import mfa
class TotpTest(unittest.TestCase):
 def test_rfc6238_sha1_six_digits(self):
  secret='GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'
  for timestamp,expected in [(59,'287082'),(1111111109,'081804'),(1111111111,'050471'),(1234567890,'005924'),(2000000000,'279037'),(20000000000,'353130')]:
   self.assertEqual(mfa.code(secret,timestamp//30),expected)
   self.assertEqual(mfa.match(secret,expected,now=timestamp),timestamp//30)
   self.assertIsNone(mfa.match(secret,expected,last_step=timestamp//30,now=timestamp))
 def test_reject_malformed_or_expired(self):
  secret='GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'
  for value in ['',None,'1234567','１２３４５６','abcdef']:
   self.assertIsNone(mfa.match(secret,value,now=59))
  self.assertIsNone(mfa.match(secret,'287082',now=3600))
