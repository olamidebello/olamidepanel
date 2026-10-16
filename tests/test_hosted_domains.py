import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('hosted_domains', Path(__file__).resolve().parents[1] / 'panel/hosted_domains.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class Connection:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, query): return self
    def fetchall(self): return [{'name': 'dobhrap.com', 'owner': 'owner'}, {'name': 'customer.example', 'owner': 'customer'}]

class HostingDomainTests(unittest.TestCase):
    def test_regular_accounts_cannot_read_other_owners(self):
        def forbidden_db(): self.fail('Unauthorized request reached database')
        for role in ('user', 'reseller', 'admin', 'readonly'):
            with self.assertRaises(PermissionError):
                module.report({'role': role}, forbidden_db)

    def test_merge_keeps_owner_and_real_provisioning_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'status.json'
            path.write_text(json.dumps({'updated_at': 123, 'domains': [
                {'domain': 'dobhrap.com', 'status': 'waiting_dns'},
                {'domain': 'africanbrowser.com', 'status': 'https_ready'},
                {'domain': '<script>', 'status': 'https_ready'}]}))
            result = module.report({'role': 'super_admin'}, Connection, path)
        rows = {x['name']: x for x in result['domains']}
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows['dobhrap.com']['owner'], 'owner')
        self.assertEqual(rows['dobhrap.com']['status'], 'waiting_dns')
        self.assertEqual(rows['customer.example']['status'], 'inventory_only')
        self.assertEqual(rows['africanbrowser.com']['owner'], 'Server operator')

    def test_missing_snapshot_does_not_claim_sites_are_published(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.report({'role': 'root'}, Connection, Path(directory) / 'missing')
        self.assertTrue(result['notice'])
        self.assertTrue(all(x['status'] == 'inventory_only' for x in result['domains']))

if __name__ == '__main__': unittest.main()
