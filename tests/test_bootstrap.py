import importlib.util, tempfile, unittest, json, stat
from pathlib import Path
spec=importlib.util.spec_from_file_location('bootstrap',Path(__file__).parents[1]/'deploy/bootstrap_passwords.py')
bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(bootstrap)
class BootstrapTest(unittest.TestCase):
    def test_generate_preserve_and_protect(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'credentials.json'
            a=bootstrap.prepare(path,{'panel_mysql_password':'REPLACE_WITH_PLACEHOLDER'})
            b=bootstrap.prepare(path,{})
            self.assertEqual(a,b)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            self.assertEqual(len(set(a.values())),3)
            for value in a.values():self.assertGreaterEqual(len(value),40)
    def test_explicit_valid_password_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            r=bootstrap.prepare(Path(folder)/'credentials.json',{'panel_admin_password':'secure-explicit-password'})
            self.assertEqual(r['panel_effective_admin_password'],'secure-explicit-password')
