import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('mail_bootstrap', Path(__file__).resolve().parents[1] / 'deploy/mail_bootstrap.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class BootstrapTests(unittest.TestCase):
    def test_existing_credentials_are_not_rotated(self):
        saved = [{'address': 'admin@example.com', 'password_hash': 'old', 'password': 'saved'}]
        with patch.object(bootstrap.subprocess, 'run') as run:
            result = bootstrap.accounts(['example.com'], ['admin'], [], saved)
        run.assert_not_called()
        self.assertEqual(saved, result)

    def test_new_accounts_use_random_passwords_and_stdin_hashing(self):
        with patch.object(bootstrap.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '$6$hashed\n')) as run:
            result = bootstrap.accounts(['example.com'], ['admin'], [], [])
        self.assertGreaterEqual(len(result[0]['password']), 24)
        self.assertEqual('{SHA512-CRYPT}$6$hashed', result[0]['password_hash'])
        self.assertEqual(['openssl', 'passwd', '-6', '-stdin'], run.call_args.args[0])
        self.assertNotIn(result[0]['password'], run.call_args.args[0])

    def test_conflicting_mx_and_spf_are_not_replaced(self):
        for kind, desired, current in [('MX', '10 mail.example.com.', ['10 old.example.com.']), ('TXT', '"v=spf1 mx ~all"', ['"v=spf1 include:provider.example -all"'])]:
            with self.assertRaises(ValueError):
                bootstrap.dns_lines('example.com', kind, desired, current)

    def test_matching_records_are_idempotent(self):
        self.assertEqual([], bootstrap.dns_lines('example.com', 'MX', '10 mail.example.com.', ['10 MAIL.EXAMPLE.COM.']))
        self.assertEqual([], bootstrap.dns_lines('panel._domainkey.example.com', 'TXT', '"v=DKIM1; p=abcdef"', ['"v=DKIM1; " "p=abcdef"']))

    def test_new_spf_preserves_unrelated_txt_and_guards_snapshot(self):
        lines = bootstrap.dns_lines('example.com', 'TXT', '"v=spf1 mx ~all"', ['"site-verification=123"'])
        self.assertTrue(lines[0].startswith('prereq yxrrset'))
        self.assertTrue(lines[-1].startswith('update add'))
        self.assertFalse(any('delete' in line for line in lines))

    def test_servfail_never_looks_like_empty_zone(self):
        with patch.object(bootstrap.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, ';; ->>HEADER<<- opcode: QUERY, status: SERVFAIL, id: 1')):
            with self.assertRaises(RuntimeError):
                bootstrap.query('example.com', 'MX')

    def test_domain_and_multiline_dns_injection_rejected(self):
        with self.assertRaises(ValueError):
            bootstrap.dns_lines('example.com\nupdate delete other.com', 'MX', '10 mail.example.com.', [])
        with self.assertRaises(ValueError):
            bootstrap.dns_lines('example.com', 'TXT', '"v=spf1"\nsend', [])

if __name__ == '__main__':
    unittest.main()
