import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'panel'))
sys.path.insert(0,str(ROOT/'deploy'))
import provision_websites as worker

class PublisherRetryTests(unittest.TestCase):
    def test_dns_waits_without_running_privileged_commands(self):
        for error in [worker.dns.resolver.NXDOMAIN(), ValueError('Ownership TXT value does not match')]:
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as tmp:
                with patch.object(worker,'STATE',Path(tmp)), patch.object(worker.Path,'read_text',return_value='{"public_ipv4":"192.0.2.1","panel_hostname":"panel.example.com","acme_email":"admin@example.com"}'), patch.object(worker,'connect') as db, patch.object(worker.dns.resolver,'Resolver') as resolver, patch.object(worker,'status') as status, patch.object(worker,'command') as command:
                    con=db.return_value.__enter__.return_value
                    con.execute.return_value.fetchall.side_effect=[[{'id':1}],[{'domain_id':1,'name':'example.com','token':'proof'}]]
                    resolver.return_value.resolve.side_effect=error
                    worker.run()
                    self.assertEqual(status.call_args.args[:2],(1,'waiting_dns'))
                    command.assert_not_called()
                    query=con.execute.call_args_list[1].args[0]
                    self.assertIn("s.state='waiting_dns'",query)
                    self.assertIn('s.updated<=UNIX_TIMESTAMP()-60',query)

if __name__=='__main__':unittest.main()
