import sys
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'deploy'))
sys.path.insert(0,str(ROOT/'panel'))
import mail_namecheap as dns


def rec(name,kind,value,**kw):return dict(Name=name,Type=kind,Address=value,TTL='300',**kw)

class MailNamecheapTests(unittest.TestCase):
    def test_preserves_web_and_unrelated_txt(self):
        original=[rec('@','A','192.0.2.1'),rec('@','TXT','google-site-verification=abc'),rec('www','CNAME','example.com')]
        desired=[rec('@','MX','mail.example.com',MXPref='10'),rec('@','TXT','v=spf1 mx ~all')]
        merged=dns.merge(original,desired)
        self.assertEqual(merged[:3],original);self.assertEqual(len(merged),5)
        self.assertEqual(len(original),3)
        self.assertEqual(dns.merge(merged,desired),merged)

    def test_conflicting_mx_or_spf_is_not_overwritten(self):
        for kind,value,want in [('MX','old.provider.com','mail.example.com'),('TXT','v=spf1 include:old.example -all','v=spf1 mx ~all')]:
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                dns.merge([rec('@',kind,value)],[rec('@',kind,want)])

    def test_duplicate_spf_is_rejected(self):
        with self.assertRaises(ValueError):dns.merge([rec('@','TXT','v=spf1 mx ~all')]*2,[rec('@','TXT','v=spf1 mx ~all')])

    def test_quoted_dkim_chunks_are_equivalent(self):
        old=[rec('panel._domainkey','TXT','"v=DKIM1; " "p=abcdef"')]
        self.assertEqual(dns.merge(old,[rec('panel._domainkey','TXT','v=DKIM1; p=abcdef')]),old)

    def test_existing_strict_dmarc_is_preserved(self):
        old=[rec('_dmarc','TXT','v=DMARC1; p=reject; rua=mailto:reports@example.com')]
        self.assertEqual(dns.merge(old,[rec('_dmarc','TXT','v=DMARC1; p=none')]),old)

    def test_conflicting_dkim_key_requires_migration(self):
        with self.assertRaises(ValueError):dns.merge([rec('panel._domainkey','TXT','v=DKIM1; p=old')],[rec('panel._domainkey','TXT','v=DKIM1; p=new')])

    def test_ipv6_and_alias_mail_hosts_require_review(self):
        for kind,value in [('AAAA','2001:db8::1'),('ALIAS','example.com'),('CNAME','other.example.com')]:
            with self.subTest(kind=kind),self.assertRaises(ValueError):dns.merge([rec('mail',kind,value)],[rec('mail','A','192.0.2.1')])

    def test_unknown_record_and_dynamic_dns_are_preserved_by_refusal(self):
        for old in [rec('@','CAA','0 issue letsencrypt.org'),rec('mail','A','192.0.2.1',IsDDNSEnabled='true')]:
            with self.assertRaises(ValueError):dns.merge([old],[rec('mail','A','192.0.2.1')])

    def test_explicit_multilabel_zone_mapping(self):
        domain,z,name=dns.zone_for('mail.example.co.uk',[{'sld':'example','tld':'co.uk'}])
        self.assertEqual((domain,name),('example.co.uk','mail'))
        with self.assertRaises(ValueError):dns.zone_for('evil-example.co.uk',[z])

    def test_provider_write_preserves_zone_and_verifies_readback(self):
        import xml.etree.ElementTree as ET
        observed=[rec('@','A','192.0.2.10'),rec('@','TXT','verification=keep')]
        calls=[]
        def provider(account,command,**params):
            calls.append(command)
            root=ET.Element('{'+dns.NS['n']+'}ApiResponse')
            if command.endswith('getHosts'):
                result=ET.SubElement(root,'{'+dns.NS['n']+'}DomainDNSGetHostsResult',IsUsingOurDNS='true',EmailType='MX')
                for row in observed:ET.SubElement(result,'{'+dns.NS['n']+'}host',row)
            else:
                observed.clear()
                for i in range(1,20):
                    if 'HostName'+str(i) not in params:break
                    row=rec(params['HostName'+str(i)],params['RecordType'+str(i)],params['Address'+str(i)])
                    row['TTL']=params['TTL'+str(i)]
                    if 'MXPref'+str(i) in params:row['MXPref']=params['MXPref'+str(i)]
                    observed.append(row)
                ET.SubElement(root,'{'+dns.NS['n']+'}DomainDNSSetHostsResult',IsSuccess='true')
            return root
        connection=MagicMock();connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value={'mode':'production','credentials':'encrypted'}
        with patch.object(dns,'connect',connection),patch.object(dns,'cipher') as cipher,patch.object(dns,'call',side_effect=provider):
            cipher.return_value.decrypt.return_value=b'{}'
            config={'mode':'namecheap','account_id':1,'zones':[{'sld':'example','tld':'com'}]}
            result=dns.provision([('example.com','MX','10 mail.example.com.')],config)
            self.assertTrue(result['changed'])
            self.assertIn('domains.dns.setHosts',calls)
            self.assertIn(rec('@','TXT','verification=keep'),observed)
            self.assertFalse(dns.provision([('example.com','MX','10 mail.example.com.')],config)['changed'])
            self.assertEqual(calls.count('domains.dns.setHosts'),1)

    def test_missing_zone_fails_before_loading_credentials(self):
        with patch.object(dns,'connect') as connect:
            with self.assertRaises(ValueError):dns.provision([('mail.other.com','A','192.0.2.1')],{'mode':'namecheap','account_id':1,'zones':[{'sld':'example','tld':'com'}]})
            connect.assert_not_called()

if __name__=='__main__':unittest.main()
