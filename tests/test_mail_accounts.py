import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, MagicMock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'panel'))
sys.path.insert(0,str(ROOT/'deploy'))
import mail_accounts as mail
from mail_account_worker import apply_requests

class MailAccountTests(unittest.TestCase):
    def test_address_rejects_traversal_and_bad_domains(self):
        for value in ['../x@example.com','a@-example.com','a@example..com','A@example.com','a@ex_ample.com','a@example.com\n']:
            with self.subTest(value=value),self.assertRaises(ValueError):mail.validate_address(value)
        self.assertEqual(mail.validate_address('support@afribulkhub.com'),'afribulkhub.com')

    def test_password_is_hashed_not_passed_as_argument(self):
        with patch.object(mail.subprocess,'run') as run:
            run.return_value.stdout='$6$salt$abc\n'
            value=mail.hash_password('long-secret-password')
            self.assertEqual(value,'{SHA512-CRYPT}$6$salt$abc')
            self.assertNotIn('long-secret-password',run.call_args.args[0])
            self.assertEqual(run.call_args.kwargs['input'],'long-secret-password\n')

    def test_invalid_passwords(self):
        for password in ['short','x'*257,'x'*14+'\n',None]:
            with self.assertRaises(ValueError):mail.hash_password(password)

    def test_policy_preserves_other_accounts_and_hashes(self):
        policy={'mail_hostname':'mail.example.com','mail_accounts':[{'address':'a@other.com','password_hash':'existing'}]}
        job={'id':1,'address':'support@afribulkhub.com','operation':'upsert','password_hash':'{SHA512-CRYPT}$6$salt$hash'}
        new,accepted,denied=apply_requests(policy,[job],lambda j,d:True)
        self.assertEqual(accepted,[1]);self.assertEqual(denied,[])
        self.assertEqual(new['mail_accounts'][0],policy['mail_accounts'][0])
        self.assertEqual(len(policy['mail_accounts']),1)

    def test_revoked_ownership_denies_change(self):
        job={'id':1,'address':'support@example.com','operation':'disable'}
        policy={'mail_accounts':[{'address':'support@example.com','password_hash':'existing'}]}
        new,accepted,denied=apply_requests(policy,[job],lambda j,d:False)
        self.assertEqual(new,policy);self.assertEqual(denied,[1]);self.assertFalse(accepted)

    def test_disable_preserves_other_mailboxes(self):
        policy={'mail_accounts':[{'address':'a@example.com'},{'address':'b@example.com'}]}
        new,accepted,_=apply_requests(policy,[{'id':2,'address':'a@example.com','operation':'disable'}],lambda j,d:True)
        self.assertEqual(new['mail_accounts'],[{'address':'b@example.com'}]);self.assertEqual(accepted,[2])

    def test_corrupt_hash_cannot_enter_policy(self):
        policy={'mail_accounts':[]}
        new,accepted,denied=apply_requests(policy,[{'id':3,'address':'a@example.com','operation':'upsert','password_hash':'raw-password'}],lambda j,d:True)
        self.assertEqual(new,policy);self.assertFalse(accepted);self.assertEqual(denied,[3])

    def test_api_rejects_unapproved_domain_before_hashing(self):
        con=MagicMock();factory=MagicMock();factory.return_value.__enter__.return_value=con
        with patch.object(mail,'permitted_domains',return_value=['own.example']),patch.object(mail,'hash_password') as hash_fn:
            status,_=mail.handle('POST',{'id':7,'role':'user'},factory,{'address':'a@other.example','operation':'upsert','password':'long-secret-password'})
        self.assertEqual(status,403);hash_fn.assert_not_called()

    def test_api_hides_other_domains_and_password_hashes(self):
        con=MagicMock();factory=MagicMock();factory.return_value.__enter__.return_value=con
        con.execute.return_value.fetchall.side_effect=[
            [{'address':'a@own.example','updated':1},{'address':'b@other.example','updated':1}],
            [{'address':'a@own.example','creator':7,'state':'queued'}, {'address':'b@other.example','creator':8,'state':'queued'}]]
        with patch.object(mail,'permitted_domains',return_value=['own.example']):
            status,data=mail.handle('GET',{'id':7,'role':'user'},factory)
        self.assertEqual(status,200);self.assertEqual(len(data['accounts']),1);self.assertEqual(len(data['requests']),1)
        for call in con.execute.call_args_list:self.assertNotIn('password_hash',call.args[0])

    def test_regular_user_requires_approved_matching_inventory(self):
        class Rows:
            def fetchall(self):return []
        class Con:
            def execute(self,sql,args):
                self.sql=sql;self.args=args;return Rows()
        con=Con()
        self.assertEqual(mail.permitted_domains(con,{'id':7,'role':'user'}),[])
        self.assertIn('d.owner=m.owner',con.sql);self.assertEqual(con.args,(7,))

if __name__=='__main__':unittest.main()
