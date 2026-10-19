"""Exercise Ansible precedence across bootstrap and mail plays."""
import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec('ansible'), 'ansible-core unavailable')
class MailHandoffTests(unittest.TestCase):
    def test_generated_accounts_survive_empty_extra_vars_across_plays(self):
        import yaml
        prep = yaml.safe_load((ROOT / 'ansible/prepare-domain-mail.yml').read_text())[0]['tasks']
        bootstrap = next(t for t in prep if t['name'] == 'Load generated and existing mailbox hashes into deployment')
        email = yaml.safe_load((ROOT / 'ansible/deploy-domain-email.yml').read_text())[0]
        resolve = next(t for t in email['pre_tasks'] if t['name'] == 'Resolve generated mailboxes independently of operator extra vars')
        address = 'admin@one.example'
        payload = {'mail_accounts': [{'address': address, 'password_hash': '{SHA512-CRYPT}$6$fake'}]}
        plays = [
            {'hosts': 'localhost', 'gather_facts': False,
             'vars': {'bootstrap_account_data': {'content': base64.b64encode(json.dumps(payload).encode()).decode()}},
             'tasks': [bootstrap]},
            {'hosts': 'localhost', 'gather_facts': False,
             'vars': email['vars'],
             'tasks': [resolve, {'ansible.builtin.assert': {'that': [
                 'mail_accounts | length == 0',
                 'mail_effective_accounts | length == 1',
                 "mail_effective_accounts[0].address == 'admin@one.example'"
             ]}}]}
        ]
        with tempfile.TemporaryDirectory() as temp:
            playbook = Path(temp) / 'test.json'
            policy = Path(temp) / 'policy.json'
            playbook.write_text(json.dumps(plays))
            policy.write_text(json.dumps({'mail_accounts': []}))
            result = subprocess.run([sys.executable, '-m', 'ansible.cli.playbook', '-i', 'localhost,', '-c', 'local', str(playbook), '-e', '@' + str(policy)], text=True, capture_output=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
