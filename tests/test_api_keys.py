import json, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'panel'))
import api_keys
from cryptography.fernet import Fernet

class VaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.key=Fernet.generate_key();(self.root/'key').write_bytes(self.key)
        self.env=patch.dict(os.environ,PANEL_DATA=str(self.root),PANEL_PAYMENT_KEY=str(self.root/'key'));self.env.start()
        self.admin={'role':'super_admin'}
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def save(self,**extra):
        return api_keys.handle('POST',self.admin,dict(action='save',provider='openai',label='Shared AI',domains=['example.com'],secret='test-private-value',**extra))
    def test_permissions_no_storage(self):
        for role in ['admin','user','readonly','reseller']:
            self.assertEqual(api_keys.handle('GET',{'role':role})[0],403)
        self.assertFalse((self.root/'api-provider-keys.lock').exists())
    def test_encryption_redaction_rotation_and_deletion(self):
        self.save()
        path=self.root/'api-provider-keys.json';raw=path.read_text()
        self.assertNotIn('test-private-value',raw)
        row=json.loads(raw)['keys'][0]
        self.assertEqual(Fernet(self.key).decrypt(row['encrypted_secret'].encode()),b'test-private-value')
        result=api_keys.handle('GET',self.admin)[1]
        self.assertNotIn('encrypted_secret',result['keys'][0]);self.assertNotIn('test-private-value',str(result))
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.save(id=1);self.assertEqual(api_keys.handle('GET',self.admin)[1]['keys'][0]['version'],2)
        api_keys.handle('POST',self.admin,dict(action='delete',id=1))
        self.assertEqual(api_keys.handle('GET',self.admin)[1]['keys'],[])
    def test_blank_preserves_key_and_expiry_policy(self):
        self.save()
        api_keys.handle('POST',self.admin,dict(action='save',id=1,provider='openai',label='Updated',secret='',domains=[],expires=1,enabled=False))
        row=api_keys.handle('GET',self.admin)[1]['keys'][0]
        self.assertEqual(row['version'],1);self.assertTrue(row['expired']);self.assertFalse(row['enabled'])
    def test_invalid_domains_secret_and_identifiers(self):
        for body in [dict(action='delete',id=-1),dict(action='save',provider='openai',label='x',domains=['https://example.com']),dict(action='save',provider='openai',label='x',secret='bad\nkey')]:
            with self.assertRaises(ValueError):api_keys.handle('POST',self.admin,body)
    def test_symlink_refused(self):
        (self.root/'api-provider-keys.json').symlink_to(self.root/'key')
        with self.assertRaises(ValueError):api_keys.handle('GET',self.admin)

if __name__=='__main__':unittest.main()
