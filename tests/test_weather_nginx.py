import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('weather_nginx', Path(__file__).resolve().parents[1] / 'deploy/weather/nginx_repair.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class NginxRepair(unittest.TestCase):
    def test_existing_small_directive_comments_and_idempotency(self):
        source = '# http { ignored\nhttp {\nserver_names_hash_bucket_size 64;\nserver { server_name "a{b}"; }\n}\n'
        result = module.tune(source)
        self.assertIn('server_names_hash_bucket_size 256;', result)
        self.assertIn('server_names_hash_max_size 8192;', result)
        self.assertNotIn('bucket_size 64;', result)
        self.assertEqual(module.tune(result), result)

    def test_larger_values_are_preserved(self):
        source = 'http { server_names_hash_bucket_size 512; server_names_hash_max_size 16384; }'
        self.assertEqual(module.tune(source), source)

    def test_identical_aliases_only_and_rollback(self):
        for binary,success in [('/bin/true',True),('/bin/false',False)]:
            with self.subTest(binary=binary), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                config = root / 'nginx.conf'
                source = 'http { server_names_hash_bucket_size 64; }'
                config.write_text(source)
                enabled = root / 'sites-enabled'
                enabled.mkdir()
                (enabled / 'a').write_text('server { listen 80; server_name example.org; }')
                (enabled / 'b').symlink_to('a')
                (enabled / 'c').write_text('server { listen 80; server_name example.org; location / { return 200; } }')
                if success:
                    result = module.repair(config, enabled, root / 'backups', binary)
                    self.assertTrue(result['changed'])
                    self.assertFalse((enabled / 'b').is_symlink())
                    self.assertTrue((enabled / 'c').exists())
                else:
                    with self.assertRaises(RuntimeError):
                        module.repair(config, enabled, root / 'backups', binary)
                    self.assertEqual(config.read_text(), source)
                    self.assertTrue((enabled / 'b').is_symlink())
                    self.assertTrue((enabled / 'b').exists())
