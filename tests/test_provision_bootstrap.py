import importlib.util,unittest,json
from pathlib import Path
from types import SimpleNamespace
spec=importlib.util.spec_from_file_location('wrapper',Path(__file__).parents[1]/'deploy/provision_bootstrap.py')
wrapper=importlib.util.module_from_spec(spec);spec.loader.exec_module(wrapper)
class ProvisionWrapperTest(unittest.TestCase):
    def test_success_and_stdin(self):
        def run(argv,**kw):
            self.assertEqual(argv[:3],['runuser','-u','olamidepanel'])
            self.assertEqual(json.loads(kw['input'])['password'],'secret-admin')
            self.assertNotIn('secret-admin',argv)
            self.assertEqual(kw['cwd'],'/tmp')
            return SimpleNamespace(returncode=0,stdout='{"changed":false}',stderr='')
        self.assertEqual(wrapper.provision({'panel_admin_username':'owner','panel_admin_password':'secret-admin'},{},run),{'changed':False,'ok':True})
    def test_error_redacted(self):
        def run(*args,**kw):return SimpleNamespace(returncode=1,stdout='',stderr='failed secret-admin database-secret')
        result=wrapper.provision({'panel_admin_username':'owner','panel_admin_password':'secret-admin'},{'password':'database-secret'},run)
        self.assertFalse(result['ok']);self.assertNotIn('secret',result['error'])
