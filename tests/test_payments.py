import sys,json,hmac,hashlib,tempfile,os,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).parents[1]/'panel'))
import payments
class PaymentTest(unittest.TestCase):
    def test_stripe_signature_and_tolerance(self):
        raw=b'{"type":"example"}';secret='whsec_example';stamp=1000
        sig=hmac.new(secret.encode(),b'1000.'+raw,hashlib.sha256).hexdigest()
        self.assertTrue(payments.signature('stripe',raw,{'Stripe-Signature':'t=1000,v1='+sig},secret,1000))
        self.assertFalse(payments.signature('stripe',raw+b'x',{'Stripe-Signature':'t=1000,v1='+sig},secret,1000))
        self.assertFalse(payments.signature('stripe',raw,{'Stripe-Signature':'t=1000,v1='+sig},secret,1400))
    def test_paystack_signature(self):
        raw=b'payload';sig=hmac.new(b'secret',raw,hashlib.sha512).hexdigest()
        self.assertTrue(payments.signature('paystack',raw,{'x-paystack-signature':sig},'secret'))
        self.assertFalse(payments.signature('paystack',raw,{'x-paystack-signature':'invalid'},'secret'))
    def test_encryption_roundtrip(self):
        from cryptography.fernet import Fernet
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'key';path.write_bytes(Fernet.generate_key())
            with patch.dict(os.environ,{'PANEL_PAYMENT_KEY':str(path)}):
                token=payments.cipher().encrypt(b'{"secret":"test-private"}').decode()
                self.assertNotIn('test-private',token)
                self.assertEqual(payments.decrypt({'credentials':token})['secret'],'test-private')
    def test_verify_rejects_amount_currency_and_mode(self):
        row={'id':1,'provider_reference':'cs_test_abcdef123','amount_cents':1500,'currency':'USD','token':'token','state':'checkout'}
        response={'id':row['provider_reference'],'payment_status':'paid','amount_total':1500,'currency':'usd','metadata':{'panel_payment':'token'},'livemode':False}
        for key,value in [('amount_total',1501),('currency','eur'),('livemode',True),('id','other')]:
            with patch.object(payments,'request_api',return_value={**response,key:value}):
                with self.assertRaises(ValueError):payments.verify(row,{'provider':'stripe','mode':'test'},{'secret':'hidden'})
    def test_verify_rejects_wrong_metadata(self):
        with patch.object(payments,'request_api',return_value={'id':'cs_test_ref','payment_status':'paid','amount_total':1500,'currency':'usd','metadata':{'panel_payment':'other'},'livemode':False}):
            with self.assertRaises(ValueError):payments.verify({'id':1,'provider_reference':'cs_test_ref','amount_cents':1500,'currency':'USD','token':'token','state':'checkout'},{'provider':'stripe','mode':'test'},{'secret':'hidden'})
    def test_readonly_cannot_mutate(self):
        status,_=payments.handle('POST','/api/payments/checkout',{'role':'readonly'},{})
        self.assertEqual(status,403)
    def test_remote_origin_requires_https(self):
        with patch.dict(os.environ,{'PANEL_PUBLIC_URL':'http://example.com'}):
            with self.assertRaises(ValueError):payments.public_url()
    def test_customer_cannot_list_merchant_credentials(self):
        con=MagicMock();con.__enter__.return_value=con
        with patch.object(payments,'connect',return_value=con):
            status,_=payments.handle('GET','/api/payments/gateways',{'role':'user'})
        self.assertEqual(status,403)
    def test_paid_verification_idempotent(self):
        row={'id':1,'provider_reference':'cs_test_example','amount_cents':1500,'currency':'USD','token':'token','state':'checkout'}
        response={'id':row['provider_reference'],'payment_status':'paid','amount_total':1500,'currency':'usd','metadata':{'panel_payment':'token'},'livemode':False}
        con=MagicMock();con.__enter__.return_value=con
        con.execute.return_value.fetchone.return_value={'state':'paid'}
        with patch.object(payments,'request_api',return_value=response),patch.object(payments,'connect',return_value=con):
            result=payments.verify(row,{'provider':'stripe','mode':'test'},{'secret':'hidden'})
        self.assertTrue(result['paid'])
        self.assertEqual(con.execute.call_count,1)
    def test_cannot_manage_another_reseller_gateway(self):
        con=MagicMock()
        self.assertFalse(payments.can_manage(con,{'role':'reseller','id':12},13))
        con.execute.assert_not_called()
