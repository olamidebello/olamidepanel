import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('weather_discover', Path(__file__).resolve().parents[1] / 'deploy/weather/discover.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class WeatherDiscovery(unittest.TestCase):
    def test_no_email_fails_instead_of_guessing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                module.discover(Path(tmp), {})

    def test_panel_email_and_existing_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'etc/letsencrypt').mkdir(parents=True)
            (root / 'etc/olamide-github-deploy.json').write_text(json.dumps({'admin_email':'operator@example.org'}))
            (root / 'etc/letsencrypt/cloudflare.ini').write_text('dns_cloudflare_api_token = test-token\n')
            settings = module.discover(root, {})
            self.assertEqual(settings['tls_email'], 'operator@example.org')
            self.assertEqual(settings['dns_api_token'], 'test-token')
            self.assertEqual(settings['dns_provider'], 'cloudflare')
            self.assertEqual(settings['dns_zone_id'], '')

    def test_production_account_contact_and_manual_dns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            account = root / 'etc/letsencrypt/accounts/acme-v02.api.letsencrypt.org/directory/account'
            account.mkdir(parents=True)
            (account / 'regr.json').write_text(json.dumps({'body':{'contact':['mailto:cert@example.org']}}))
            settings = module.discover(root, {})
            self.assertEqual(settings['tls_email'], 'cert@example.org')
            self.assertEqual(settings['dns_provider'], 'manual')

    def test_explicit_settings_take_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'etc/olamide-weather').mkdir(parents=True)
            (root / 'etc/olamide-weather/provision.json').write_text(json.dumps({'tls_email':'saved@example.org','dns_api_token':'saved-token','dns_zone_id':'saved-zone'}))
            settings = module.discover(root, {'WEATHER_TLS_EMAIL':'override@example.org'})
            self.assertEqual(settings['tls_email'], 'override@example.org')
            self.assertEqual(settings['dns_zone_id'], 'saved-zone')
            self.assertEqual(settings['dns_api_token'], 'saved-token')
