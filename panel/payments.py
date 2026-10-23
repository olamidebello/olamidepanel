"""Tenant-scoped hosted checkout adapters. Never collect card numbers."""
import hashlib,hmac,json,os,re,secrets,time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode,quote,urlsplit
from urllib.error import HTTPError,URLError
from cryptography.fernet import Fernet
from database import connect
import domain_marketplace
from fulfillment import enqueue

ADAPTERS={'stripe','paystack'}
PROVIDERS=['stripe','paystack','paypal','flutterwave','square','adyen','authorize_net','braintree','mollie','razorpay','checkout_com','worldpay','opay','monnify','bank_transfer']
class PaymentError(Exception):pass

def cipher():return Fernet(Path(os.environ.get('PANEL_PAYMENT_KEY','/etc/olamidepanel/payment.key')).read_bytes().strip())
def public_url():
    url=os.environ.get('PANEL_PUBLIC_URL','').rstrip('/')
    if urlsplit(url).scheme!='https' or not urlsplit(url).hostname or urlsplit(url).path:raise ValueError('Operator must configure PANEL_PUBLIC_URL as the HTTPS origin')
    return url

def request_api(provider,secret,path,payload=None,idempotency=None):
    bases={'stripe':'https://api.stripe.com/v1/','paystack':'https://api.paystack.co/'}
    headers={'Authorization':'Bearer '+secret,'Accept':'application/json'}
    data=None
    if payload is not None:
        if provider=='stripe':data=urlencode(payload).encode();headers['Content-Type']='application/x-www-form-urlencoded'
        else:data=json.dumps(payload).encode();headers['Content-Type']='application/json'
    if idempotency:headers['Idempotency-Key']=idempotency
    try:
        with urlopen(Request(bases[provider]+path,data=data,headers=headers),timeout=25) as response:return json.load(response)
    except (HTTPError,URLError,TimeoutError,ValueError):raise PaymentError('Provider request failed or timed out. Reconcile the existing payment; do not create another charge.') from None

def admin(user):return user['role'] in ['root','super_admin']
def seller_allowed(con,uid):
    return bool(con.execute("SELECT u.id FROM users u JOIN marketplace_vendors v ON v.user_id=u.id WHERE u.id=? AND u.active=1 AND u.role='reseller' AND v.enabled=1",(uid,)).fetchone())
def can_manage(con,user,owner):return admin(user) or (user['id']==owner and seller_allowed(con,owner))
def audit(con,user,action):con.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)',(user['username'],'payments:'+action,int(time.time())))
def decrypt(gateway):return json.loads(cipher().decrypt(gateway['credentials'].encode()))
def payment_visible(user,row):return admin(user) or row['buyer_id']==user['id'] or (user['role']=='reseller' and row['seller_id']==user['id'])

def signature(provider,raw,headers,secret,now=None):
    if provider=='paystack':return hmac.compare_digest(hmac.new(secret.encode(),raw,hashlib.sha512).hexdigest(),headers.get('x-paystack-signature',''))
    values={}
    for item in headers.get('Stripe-Signature','').split(','):
        if '=' in item:
            key,value=item.split('=',1);values.setdefault(key,[]).append(value)
    try:
        timestamp=int(values['t'][0])
        if abs((now if now is not None else time.time())-timestamp)>300:return False
        expected=hmac.new(secret.encode(),str(timestamp).encode()+b'.'+raw,hashlib.sha256).hexdigest()
        return any(hmac.compare_digest(expected,v) for v in values.get('v1',[]))
    except (ValueError,KeyError):return False

def verify(payment,gateway,keys):
    provider=gateway['provider'];reference=payment['provider_reference']
    if provider=='stripe':
        data=request_api(provider,keys['secret'],'checkout/sessions/'+quote(reference,safe=''))
        paid=data.get('payment_status')=='paid'
        amount=data.get('amount_total');currency=str(data.get('currency','')).upper()
        identity=data.get('id')==reference and data.get('metadata',{}).get('panel_payment')==payment['token']
        mode=bool(data.get('livemode'));mode_valid=type(data.get('livemode')) is bool
    else:
        response=request_api(provider,keys['secret'],'transaction/verify/'+quote(reference,safe=''));data=response.get('data',{})
        paid=response.get('status') is True and data.get('status')=='success'
        amount=data.get('amount');currency=str(data.get('currency','')).upper()
        identity=data.get('reference')==reference
        mode=data.get('domain')=='live';mode_valid=data.get('domain') in ['live','test']
    if not mode_valid or not identity or type(amount) is not int or amount!=payment['amount_cents'] or currency!=payment['currency'] or mode!=(gateway['mode']=='live'):
        raise ValueError('Provider identity, amount, currency or test/live mode mismatch')
    with connect() as con:
        current=con.execute('SELECT * FROM payment_transactions WHERE id=? FOR UPDATE',(payment['id'],)).fetchone()
        if paid and current['state']!='paid':
            con.execute("UPDATE payment_transactions SET state='paid',verified_at=? WHERE id=?",(int(time.time()),payment['id']))
            audit(con,{'username':'provider-verification'},'verified payment '+str(payment['id']))
        if paid and gateway['mode']=='live':enqueue(con,{**current,'state':'paid'})
    return {'ok':True,'paid':paid,'state':'paid' if paid else payment['state'],'provisioning':'queued' if paid and gateway['mode']=='live' else 'not_eligible'}

def handle(method,path,user,body=None):
    suffix=path.removeprefix('/api/payments/')
    if method=='GET':
        with connect() as con:
            if suffix=='providers':return 200,[{'provider':p,'adapter':p in ADAPTERS,'status':'adapter implemented; merchant testing required' if p in ADAPTERS else 'not implemented'} for p in PROVIDERS]
            if suffix=='gateways':
                if not admin(user) and user['role']!='reseller':return 403,{'error':'Seller access required'}
                query='SELECT id,owner_id,provider,label,mode,enabled,updated FROM payment_gateways'
                args=()
                if not admin(user):query+=' WHERE owner_id=?';args=(user['id'],)
                rows=con.execute(query+' ORDER BY id',args).fetchall()
                for row in rows:row['credentials_stored']=True;row['webhook_path']='/api/payments/webhook/'+str(row['id'])
                return 200,rows
            if suffix=='transactions':
                query='SELECT id,order_id,buyer_id,seller_id,gateway_id,provider,mode,amount_cents,currency,state,created,verified_at,token,provider_reference FROM payment_transactions'
                args=()
                if not admin(user):query+=' WHERE buyer_id=? OR seller_id=?';args=(user['id'],user['id'] if user['role']=='reseller' else -1)
                return 200,con.execute(query+' ORDER BY id DESC LIMIT 200',args).fetchall()
            if suffix.startswith('options/'):
                uid=int(suffix.split('/')[-1]);order=con.execute('SELECT * FROM hosting_orders WHERE id=? AND owner=?',(uid,user['id'])).fetchone()
                if not order:return 404,{'error':'Unknown order'}
                if order['status']!='approved':return 400,{'error':'Order must be approved first'}
                if order['seller_id'] and not seller_allowed(con,order['seller_id']):return 403,{'error':'Seller storefront disabled'}
                assigned=domain_marketplace.order_gateways(con,uid)
                choices=con.execute('SELECT id,provider,label,mode FROM payment_gateways WHERE owner_id=? AND enabled=1',(order['seller_id'],)).fetchall()
                return 200,[g for g in choices if assigned is None or g['id'] in assigned]
        return 404,{'error':'Unknown payment operation'}
    if user['role']=='readonly':return 403,{'error':'Read-only access'}
    if suffix=='gateways/save':
        provider=body.get('provider');mode=body.get('mode');label=str(body.get('label','')).strip()
        if provider not in ADAPTERS:raise ValueError('This provider has no working adapter')
        if mode not in ['test','live'] or not 1<=len(label)<=80 or type(body.get('enabled')) is not bool:raise ValueError('Invalid gateway settings')
        owner=body.get('owner_id',0 if admin(user) else user['id'])
        if type(owner) is not int or owner<0:raise ValueError('Invalid store ID')
        with connect() as con:
            if not can_manage(con,user,owner):return 403,{'error':'Cannot manage this store'}
            if owner and not seller_allowed(con,owner) and (not admin(user) or not body.get('id') or body['enabled']):raise ValueError('Enable this reseller storefront first')
            old=None
            if body.get('id'):
                old=con.execute('SELECT * FROM payment_gateways WHERE id=? FOR UPDATE',(int(body['id']),)).fetchone()
                if not old or old['owner_id']!=owner:return 403,{'error':'Gateway ownership cannot be reassigned'}
                if old['provider']!=provider or old['mode']!=mode:raise ValueError('Create a separate gateway for another provider or mode')
            keys=decrypt(old) if old else {}
            for name in ['secret','webhook_secret']:
                if body.get(name):keys[name]=str(body[name]).strip()
            secret=keys.get('secret','')
            prefix='sk_live_' if mode=='live' else 'sk_test_'
            if not secret.startswith(prefix) or len(secret)>512:raise ValueError('Secret key prefix must match selected test/live mode')
            if provider=='stripe' and not keys.get('webhook_secret','').startswith('whsec_'):raise ValueError('Stripe webhook signing secret required')
            if body['enabled'] and mode=='live' and os.environ.get('PANEL_ENABLE_LIVE_PAYMENTS','0')!='1':raise ValueError('Operator must explicitly enable live payments in deployment settings after testing')
            if body['enabled'] and body.get('confirmed_live') is not True and mode=='live':raise ValueError('Confirm live payments before enabling')
            encrypted=cipher().encrypt(json.dumps(keys).encode()).decode()
            if old:
                con.execute('UPDATE payment_gateways SET label=?,enabled=?,credentials=?,updated=? WHERE id=?',(label,int(body['enabled']),encrypted,int(time.time()),old['id']));gid=old['id']
            else:
                gid=con.execute('INSERT INTO payment_gateways(owner_id,provider,label,mode,enabled,credentials,updated) VALUES(?,?,?,?,?,?,?)',(owner,provider,label,mode,int(body['enabled']),encrypted,int(time.time()))).lastrowid
            audit(con,user,'gateway saved '+str(gid))
        return 200,{'ok':True,'id':gid}
    if suffix=='checkout':
        if body.get('confirmed') is not True:raise ValueError('Confirm one-time payment and automatic account activation')
        origin=public_url()
        with connect() as con:
            order=con.execute('SELECT * FROM hosting_orders WHERE id=? AND owner=? FOR UPDATE',(int(body['order_id']),user['id'])).fetchone()
            if not order or order['status']!='approved':raise ValueError('Only your approved orders can be paid')
            if order['seller_id'] and not seller_allowed(con,order['seller_id']):raise ValueError('Seller storefront disabled')
            if order['price_cents']<=0:raise ValueError('Free orders require manual setup, not checkout')
            assigned=domain_marketplace.order_gateways(con,order['id'])
            if assigned is not None and int(body['gateway_id']) not in assigned:raise ValueError('Gateway is not assigned to this domain')
            existing=con.execute('SELECT * FROM payment_transactions WHERE order_id=?',(order['id'],)).fetchone()
            if existing:
                if existing['state']=='checkout' and existing['checkout_url']:return 200,{'url':existing['checkout_url'],'state':'checkout'}
                return 409,{'error':'Existing payment state: '+existing['state']+'. Verify it in Payments before another attempt.'}
            gateway=con.execute('SELECT * FROM payment_gateways WHERE id=? AND owner_id=? AND enabled=1',(int(body['gateway_id']),order['seller_id'])).fetchone()
            if not gateway:raise ValueError('Choose an enabled gateway for this seller')
            if gateway['mode']=='live' and os.environ.get('PANEL_ENABLE_LIVE_PAYMENTS','0')!='1':raise ValueError('Live payments are disabled by the operator')
            buyer=con.execute('SELECT email FROM users WHERE id=?',(user['id'],)).fetchone()
            if gateway['provider']=='paystack' and not buyer['email']:raise ValueError('Set your contact email before using Paystack')
            token=secrets.token_hex(20)
            pid=con.execute('INSERT INTO payment_transactions(order_id,buyer_id,seller_id,gateway_id,provider,mode,amount_cents,currency,state,token,created) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(order['id'],user['id'],order['seller_id'],gateway['id'],gateway['provider'],gateway['mode'],order['price_cents'],order['currency'],'creating',token,int(time.time()))).lastrowid
            audit(con,user,'checkout requested '+str(pid))
        keys=decrypt(gateway);provider=gateway['provider']
        if gateway['mode']=='live' and os.environ.get('PANEL_ENABLE_LIVE_PAYMENTS','0')!='1':
            with connect() as con:con.execute("UPDATE payment_transactions SET state='needs_review' WHERE id=?",(pid,))
            raise ValueError('Live payments are disabled by the operator')
        try:
            if provider=='stripe':
                result=request_api(provider,keys['secret'],'checkout/sessions',{'mode':'payment','success_url':origin+'/#payment-return','cancel_url':origin+'/#payment-cancel','line_items[0][price_data][currency]':order['currency'].lower(),'line_items[0][price_data][unit_amount]':order['price_cents'],'line_items[0][price_data][product_data][name]':'OlamidePanel order #'+str(order['id'])+' (one month; no automatic renewal)','line_items[0][quantity]':1,'metadata[panel_payment]':token},token)
                reference=result['id'];url=result['url']
            else:
                reference='panel-'+token
                with connect() as con:con.execute('UPDATE payment_transactions SET provider_reference=? WHERE id=?',(reference,pid))
                result=request_api(provider,keys['secret'],'transaction/initialize',{'email':buyer['email'],'amount':order['price_cents'],'currency':order['currency'],'reference':reference,'callback_url':origin+'/#payment-return'})
                if result.get('status') is not True:raise PaymentError('Provider declined initialization')
                url=result['data']['authorization_url']
            parsed=urlsplit(url)
            allowed={'stripe':{'checkout.stripe.com'},'paystack':{'checkout.paystack.com'}}
            if parsed.scheme!='https' or parsed.hostname not in allowed[provider]:raise PaymentError('Unexpected hosted checkout URL')
            with connect() as con:con.execute("UPDATE payment_transactions SET state='checkout',provider_reference=?,checkout_url=? WHERE id=?",(reference,url,pid))
            return 200,{'url':url,'state':'checkout'}
        except Exception:
            with connect() as con:con.execute("UPDATE payment_transactions SET state='needs_review' WHERE id=?",(pid,))
            raise PaymentError('Checkout needs operator reconciliation; no second checkout will be created automatically') from None
    if suffix=='reconcile':
        with connect() as con:
            row=con.execute('SELECT * FROM payment_transactions WHERE id=?',(int(body['id']),)).fetchone()
            if not row or not can_manage(con,user,row['seller_id']):return 403,{'error':'Store administrator access required'}
            if row['state']=='paid':raise ValueError('Verified payment reference cannot be changed')
            gateway=con.execute('SELECT * FROM payment_gateways WHERE id=?',(row['gateway_id'],)).fetchone()
        reference=str(body.get('reference','')).strip()
        if gateway['provider']=='stripe':
            if not re.fullmatch(r'cs_(?:test_|live_)?[a-zA-Z0-9]{8,190}',reference):raise ValueError('Enter the Checkout Session ID from the merchant dashboard')
        elif reference!='panel-'+row['token']:raise ValueError('Paystack reference must match the original attempt token')
        candidate={**row,'provider_reference':reference}
        verified=verify(candidate,gateway,decrypt(gateway))
        with connect() as con:
            con.execute('UPDATE payment_transactions SET provider_reference=? WHERE id=?',(reference,row['id']))
            audit(con,user,'reconciled payment '+str(row['id']))
        return 200,verified
    if suffix=='verify':
        with connect() as con:
            row=con.execute('SELECT * FROM payment_transactions WHERE id=?',(int(body['id']),)).fetchone()
            if not row or not payment_visible(user,row):return 404,{'error':'Unknown payment'}
            if not row['provider_reference']:raise ValueError('No provider reference. Operator reconciliation required.')
            gateway=con.execute('SELECT * FROM payment_gateways WHERE id=?',(row['gateway_id'],)).fetchone()
        return 200,verify(row,gateway,decrypt(gateway))
    return 404,{'error':'Unknown payment operation'}

def webhook(path,raw,headers):
    gid=int(path.rsplit('/',1)[-1])
    with connect() as con:gateway=con.execute('SELECT * FROM payment_gateways WHERE id=?',(gid,)).fetchone()
    if not gateway:return 404,{'error':'Unknown webhook'}
    keys=decrypt(gateway)
    if not signature(gateway['provider'],raw,headers,keys.get('webhook_secret','') if gateway['provider']=='stripe' else keys['secret']):return 400,{'error':'Invalid signature'}
    event=json.loads(raw)
    if gateway['provider']=='stripe':
        if event.get('type') not in ['checkout.session.completed','checkout.session.async_payment_succeeded']:return 200,{'ignored':True}
        reference=event.get('data',{}).get('object',{}).get('id')
    else:
        if event.get('event')!='charge.success':return 200,{'ignored':True}
        reference=event.get('data',{}).get('reference')
    with connect() as con:row=con.execute('SELECT * FROM payment_transactions WHERE gateway_id=? AND provider_reference=?',(gid,reference)).fetchone()
    if not row:return 200,{'ignored':True}
    return 200,verify(row,gateway,keys)
