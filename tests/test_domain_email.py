"""Security regressions for rendered multi-domain mail configuration."""
import unittest
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES = Path(__file__).resolve().parents[1] / 'ansible/templates/mail'

class MailConfigTests(unittest.TestCase):
    def setUp(self):
        self.env = Environment(loader=FileSystemLoader(TEMPLATES), undefined=StrictUndefined)
        self.values = dict(mail_hostname='mail.host.example', mail_selector='panel',
            mail_effective_domains=['one.example', 'two.example'],
            mail_accounts=[dict(address='admin@one.example', password_hash='{SHA512-CRYPT}$6$one'),
                           dict(address='admin@two.example', password_hash='{SHA512-CRYPT}$6$two')],
            ansible_facts={'getent_passwd': {'olamide-vmail': ['x', '997', '996']}})

    def render(self, name):
        return self.env.get_template(name + '.j2').render(**self.values)

    def test_same_localpart_has_separate_storage_and_full_address_auth(self):
        users = self.render('users')
        self.assertIn('/one.example/admin', users)
        self.assertIn('/two.example/admin', users)
        conf = self.render('dovecot.conf')
        self.assertNotIn('driver = static', conf)
        self.assertIn('auth_username_format = %Lu', conf)
        self.assertNotIn('auth-system', conf)
        self.assertIn('ssl = required', conf)

    def test_no_open_relay_and_authenticated_submission_requires_tls(self):
        main = self.render('main.cf')
        self.assertIn('permit_mynetworks, permit_sasl_authenticated, reject_unauth_destination', main)
        self.assertIn('smtpd_reject_unlisted_recipient = yes', main)
        master = self.render('master.cf')
        self.assertIn('smtpd_tls_security_level=encrypt', master)
        self.assertIn('smtpd_relay_restrictions=permit_sasl_authenticated,reject', master)
        self.assertIn('reject_authenticated_sender_login_mismatch', master)
        self.assertIn('admin@one.example admin@one.example', self.render('senders'))

    def test_empty_mailbox_inventory_never_enables_catchall(self):
        self.values['mail_accounts'] = []
        self.assertEqual('', self.render('users').strip())
        self.assertEqual('', self.render('recipients').strip())

    def test_generated_accounts_override_empty_operator_list_in_all_maps(self):
        self.values['mail_accounts'] = []
        self.values['mail_effective_accounts'] = [dict(address='admin@one.example', password_hash='{SHA512-CRYPT}$6$one')]
        for template in ('users', 'senders', 'recipients'):
            self.assertIn('admin@one.example', self.render(template))

    def test_opendkim_is_supervised_in_foreground_and_listener_is_checked(self):
        import yaml
        play = yaml.safe_load((TEMPLATES.parents[1] / 'deploy-domain-email.yml').read_text())[0]
        task = next(t for t in play['tasks'] if t['name'] == 'Run OpenDKIM in foreground under direct systemd supervision')
        unit = task['ansible.builtin.copy']['content']
        self.assertIn('Type=simple', unit)
        self.assertIn('PIDFile=\n', unit)
        self.assertIn('ExecStart=/usr/sbin/opendkim -f -x /etc/opendkim.conf', unit)
        self.assertIn('User=opendkim', unit)
        check = next(t for t in play['tasks'] if t['name'] == 'Verify local mail listeners')
        self.assertIn(8891, check['loop'])

    def test_dkim_key_paths_are_separate(self):
        keys = self.render('KeyTable')
        self.assertIn('/one.example/panel.private', keys)
        self.assertIn('/two.example/panel.private', keys)

if __name__ == '__main__':
    unittest.main()

