import sys, unittest
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).parents[1]/'panel'))
import namecheap as nc

def zone(extra=''):
    return ET.fromstring('<ApiResponse xmlns="https://api.namecheap.com/xml.response" Status="OK"><DomainDNSGetHostsResult IsUsingOurDNS="true"><host Name="@" Type="A" Address="192.0.2.1" TTL="300"/><host Name="@" Type="TXT" Address="verify-token" TTL="300"/>'+extra+'</DomainDNSGetHostsResult></ApiResponse>')

class NamecheapTests(unittest.TestCase):
    def test_documented_http_namespace_and_capital_host(self):
        root = nc.parse_response('<ApiResponse xmlns="http://api.namecheap.com/xml.response" Status="OK"><CommandResponse><DomainDNSGetHostsResult IsUsingOurDNS="true"><Host Name="@" Type="A" Address="192.0.2.1" TTL="300"/></DomainDNSGetHostsResult></CommandResponse></ApiResponse>')
        result = root.find('.//n:DomainDNSGetHostsResult', nc.NS)
        self.assertIsNotNone(result)
        self.assertEqual(result.find('n:host', nc.NS).get('Name'), '@')
    def test_https_namespace_and_lowercase_host(self):
        root = nc.parse_response('<ApiResponse xmlns="https://api.namecheap.com/xml.response" Status="OK"><DomainDNSGetHostsResult><host Name="www"/></DomainDNSGetHostsResult></ApiResponse>')
        self.assertEqual(root.find('.//n:host', nc.NS).get('Name'), 'www')
    def test_unknown_namespace_rejected(self):
        with self.assertRaises(ValueError):nc.parse_response('<ApiResponse xmlns="https://example.com" Status="OK"/>')
    def test_permissions_before_database(self):
        for role in ['admin','reseller','user','readonly']:
            with patch.object(nc,'connect') as db:
                self.assertEqual(nc.handle('POST',{'role':role},{'action':'delete'})[0],403)
                db.assert_not_called()
    def test_public_never_returns_key(self):
        self.assertNotIn('credentials',nc.public(dict(id=1,label='a',mode='sandbox',updated=1,credentials='secret')))
    def test_preserves_existing_records(self):
        final=zone('<host Name="www" Type="A" Address="192.0.2.2" TTL="300"/>')
        success=ET.fromstring('<ApiResponse xmlns="https://api.namecheap.com/xml.response"><DomainDNSSetHostsResult IsSuccess="true"/></ApiResponse>')
        with patch.object(nc,'call',side_effect=[zone(),zone(),success,final]) as api:
            nc.provision({},dict(sld='example',tld='co.uk',hosts='www',address='192.0.2.2'))
            args=api.call_args_list[2].kwargs
            self.assertEqual(args['Address2'],'verify-token')
            self.assertEqual(args['HostName3'],'www')
            self.assertEqual(args['TLD'],'co.uk')
    def test_conflicts_stop_before_write(self):
        with patch.object(nc,'call',return_value=zone('<host Name="www" Type="CNAME" Address="example.com"/>')) as api:
            with self.assertRaises(ValueError):nc.provision({},dict(sld='example',tld='com',hosts='www',address='192.0.2.2'))
            self.assertEqual(api.call_count,1)
    def test_concurrent_change_stops_write(self):
        with patch.object(nc,'call',side_effect=[zone(),zone('<host Name="mail" Type="A" Address="192.0.2.3"/>')]) as api:
            with self.assertRaises(ValueError):nc.provision({},dict(sld='example',tld='com',hosts='www',address='192.0.2.2'))
            self.assertEqual(api.call_count,2)
    def test_network_error_does_not_expose_key(self):
        account=dict(mode='sandbox',ApiUser='user',ApiKey='secret',UserName='user',ClientIp='192.0.2.1')
        with patch.object(nc.urllib.request,'urlopen',side_effect=RuntimeError('secret')):
            with self.assertRaises(ValueError) as error:nc.call(account,'domains.getList')
            self.assertNotIn('secret',str(error.exception))

if __name__=='__main__':unittest.main()
