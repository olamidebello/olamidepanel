import hashlib,os,pwd,shutil,subprocess,tempfile,unittest
from pathlib import Path
from jinja2 import Environment,StrictUndefined
ROOT=Path(__file__).parents[1]

class DomainSSHTests(unittest.TestCase):
    def render(self,access='sftp'):
        env=Environment(undefined=StrictUndefined)
        env.filters['hash']=lambda value,kind:hashlib.new(kind,value.encode()).hexdigest()
        group=__import__('grp').getgrgid(pwd.getpwuid(os.getuid()).pw_gid).gr_name
        return env.from_string((ROOT/'ansible/templates/domain-ssh.conf.j2').read_text()).render(managed_domain_accounts=[{'domain':'example.com','access':access}],domain_account_group=group,domain_key_base='/etc/ssh/olamidepanel-domain-keys',domain_home_base='/srv/olamidepanel-domains')
    def test_specific_modes_precede_confined_defaults(self):
        for access in ['sftp','shell','disabled']:
            text=self.render(access)
            self.assertLess(text.index('Match User'),text.index('Match Group'))
            self.assertIn('AuthenticationMethods publickey',text)
            self.assertIn('DisableForwarding yes',text)
            self.assertIn('ChrootDirectory /srv/olamidepanel-domains/%u',text)
            if access=='shell':self.assertIn('ForceCommand none',text)
    @unittest.skipUnless(shutil.which('sshd') and shutil.which('ssh-keygen') and Path('/run/sshd').exists(),'requires OpenSSH and privilege-separation directory')
    def test_openssh_effective_configuration_for_each_mode(self):
        user=pwd.getpwuid(os.getuid()).pw_name
        login='dom_'+hashlib.sha256(b'example.com').hexdigest()[:16]
        with tempfile.TemporaryDirectory() as tmp:
            key=Path(tmp)/'hostkey';config=Path(tmp)/'sshd_config'
            subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)],check=True)
            for access in ['sftp','shell','disabled']:
                config.write_text(self.render(access).replace('Match User '+login,'Match User '+user))
                result=subprocess.run([shutil.which('sshd'),'-T','-f',str(config),'-h',str(key),'-C','user='+user+',host=localhost,addr=127.0.0.1'],capture_output=True,text=True,check=True)
                lines=result.stdout.splitlines()
                self.assertIn('passwordauthentication no',lines)
                self.assertIn('authenticationmethods publickey',lines)
                self.assertIn('disableforwarding yes',lines)
                if access=='shell':
                    self.assertIn('forcecommand none',lines);self.assertIn('chrootdirectory none',lines)
                elif access=='sftp':self.assertIn('forcecommand internal-sftp -d /home/'+login,lines)
                else:self.assertIn('forcecommand internal-sftp -d /',lines)
