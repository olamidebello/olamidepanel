import importlib.util,json,sys,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).parents[1]/'panel'))
import domain_marketplace as dm
import payments
spec=importlib.util.spec_from_file_location('domain_worker',Path(__file__).parents[1]/'deploy/domain_marketplace_worker.py')
worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)

class DomainMarketplaceTests(unittest.TestCase):
    def test_authorization_precedes_inventory_database(self):
        with patch.object(dm.hosted_domains,'report') as report:
            for role in ['admin','reseller','user','readonly']:
                with self.assertRaises(PermissionError):dm.handle('GET',{'role':role})
            report.assert_not_called()
    def test_bulk_validation(self):
        body=dict(domains=['example.com'],gateway_ids=[1],operation='deploy',confirmed=True)
        self.assertEqual(dm.validate_targets(body,['example.com']),(['example.com'],[1],'deploy'))
        for changes in [dict(domains=['bad.com']),dict(domains=['example.com']*2),dict(gateway_ids=[]),dict(gateway_ids=[True]),dict(confirmed=False),dict(operation='shell')]:
            with self.assertRaises(ValueError):dm.validate_targets(dict(body,**changes),['example.com'])
    def test_disabled_storefront_fails_closed(self):
        con=MagicMock();con.execute.return_value.fetchone.return_value=dict(enabled=False,state='deployed',gateway_ids='[1]')
        with self.assertRaises(ValueError):dm.assigned(con,'example.com')
    def test_gateway_filter_enforced_before_provider_calls(self):
        con=MagicMock();con.__enter__.return_value=con
        con.execute.return_value.fetchone.return_value=dict(id=8,status='approved',seller_id=0,price_cents=100)
        with patch.object(payments,'connect',return_value=con),patch.object(payments,'public_url',return_value='https://panel.example.com'),patch.object(dm,'order_gateways',return_value=[1]),patch.object(payments,'request_api') as request:
            with self.assertRaises(ValueError):payments.handle('POST','/api/payments/checkout',dict(id=2,role='user'),dict(confirmed=True,order_id=8,gateway_id=2))
            request.assert_not_called()
    def test_nginx_parser_exact_names_comments_quotes_multiple_blocks(self):
        text='''# server { server_name example.com; }
server { listen 80; server_name example.com www.example.com; location / { proxy_pass http://localhost:80; } }
server { listen 443 ssl; server_name "example.com"; }
server { server_name otherexample.com; }
'''
        self.assertEqual(len(worker.server_blocks(text,'example.com')),2)
        self.assertEqual(worker.server_blocks(text,'absent.example.com'),[])
    def test_public_store_escapes_content_and_has_no_gateway_secrets(self):
        con=MagicMock();con.__enter__.return_value=con
        con.execute.return_value.fetchall.side_effect=[[dict(id=1,name='<script>',description='<img>',price_cents=100,currency='USD')],[dict(id=1,label='Shared',provider='stripe',mode='test',credentials='PRIVATE')]]
        with patch.object(dm,'assigned',return_value=[1]):
            result=dm.storefront('example.com','https://panel.example.com',db=lambda:con).decode()
        self.assertNotIn('<script>',result);self.assertNotIn('PRIVATE',result);self.assertIn('marketplace_domain=example.com',result)

if __name__=='__main__':unittest.main()
