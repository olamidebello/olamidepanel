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
            result = module.report({'role': 'super_admin'}, Connection, path, operator_domains=())
        rows = {x['name']: x for x in result['domains']}
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows['dobhrap.com']['owner'], 'owner')
        self.assertEqual(rows['dobhrap.com']['status'], 'waiting_dns')
        self.assertEqual(rows['customer.example']['status'], 'inventory_only')
        self.assertEqual(rows['africanbrowser.com']['owner'], 'Server operator')

    def test_missing_snapshot_does_not_claim_sites_are_published(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.report({'role': 'root'}, Connection, Path(directory) / 'missing', operator_domains=())
        self.assertTrue(result['notice'])
        self.assertTrue(all(x['status'] == 'inventory_only' for x in result['domains']))

    def test_operator_domains_visible_without_claiming_deployment(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.report({'role': 'root'}, Connection, Path(directory) / 'missing')
        rows = {x['name']: x for x in result['domains']}
        self.assertIn('aicourtsystem.com', rows)
        self.assertEqual(rows['aicourtsystem.com']['status'], 'verification_pending')
        self.assertEqual(rows['dobhrap.com']['owner'], 'owner')
        self.assertEqual(rows['dobhrap.com']['status'], 'inventory_only')

    def test_snapshot_overrides_pending_status(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'status.json'
            path.write_text(json.dumps({'updated_at': 123, 'domains': [
                {'domain': 'aicourtsystem.com', 'status': 'waiting_dns'}]}))
            result = module.report({'role': 'root'}, Connection, path)
        row = next(x for x in result['domains'] if x['name'] == 'aicourtsystem.com')
        self.assertEqual(row['status'], 'waiting_dns')
        self.assertEqual(row['source'], 'Server hosting automation')

class CountryWeatherInventoryTests(unittest.TestCase):
    def test_all_country_domains_visible_before_deployment(self):
        catalog = json.loads((Path(__file__).resolve().parents[1] / 'ansible/weather/countries.json').read_text())
        self.assertEqual(module.WEATHER_DOMAINS, {x['domain']: x['name'] for x in catalog})
        with tempfile.TemporaryDirectory() as directory:
            data = module.report({'role':'super_admin'}, Connection, Path(directory) / 'missing')
        rows = {r['name']:r for r in data['domains']}
        for country in catalog:
            self.assertEqual(rows[country['domain']]['country'], country['name'])
            self.assertEqual(rows[country['domain']]['category'], 'country_weather')
            self.assertEqual(rows[country['domain']]['status'], 'verification_pending')
        self.assertEqual(rows['weathernigeria.africandroid.world']['country'], 'Nigeria')

    def test_country_snapshot_keeps_failure_and_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snapshot.json'
            path.write_text(json.dumps({'updated_at':123,'domains':[
                {'domain':'weathertunisia.africandroid.world','status':'needs_attention','error':'Obtain HTTPS certificate failed'},
                {'domain':'weatherghana.africandroid.world','status':'https_ready','checked_at':'2026-10-19T17:00:00Z'}]}))
            data = module.report({'role':'super_admin'}, Connection, path)
        rows = {r['name']:r for r in data['domains']}
        self.assertEqual(rows['weathertunisia.africandroid.world']['status'], 'needs_attention')
        self.assertEqual(rows['weatherghana.africandroid.world']['status'], 'https_ready')
        self.assertEqual(rows['weatherghana.africandroid.world']['country'], 'Ghana')

if __name__ == '__main__': unittest.main()
