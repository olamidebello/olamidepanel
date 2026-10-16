"""Plan catalog and manual-review orders. No payment or hosting provisioning."""
import json, re, time
from database import connect, IntegrityError

ADMIN_ROLES={'root','super_admin'}

def integer(body,key,minimum,maximum):
    value=body.get(key)
    if type(value) is not int or not minimum<=value<=maximum: raise ValueError('Invalid '+key)
    return value

def validate_plan(body):
    name=str(body.get('name','')).strip(); description=str(body.get('description','')).strip()
    if not 2<=len(name)<=80 or len(description)>1000: raise ValueError('Plan name must have 2–80 characters; description limit is 1000')
    if type(body.get('enabled')) is not bool or type(body.get('featured')) is not bool: raise ValueError('Enabled and featured must be booleans')
    kind=body.get('plan_kind','hosting')
    if kind not in ['hosting','reseller']:raise ValueError('Invalid plan type')
    return dict(plan_kind=kind,name=name,description=description,price_cents=integer(body,'price_cents',0,100000000),disk_gb=integer(body,'disk_gb',1,1000000),bandwidth_gb=integer(body,'bandwidth_gb',1,10000000),websites=integer(body,'websites',1,100000),enabled=int(body['enabled']),featured=int(body['featured']))

def audit(con,user,action):
    con.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)',(user['username'],'marketplace:'+action,int(time.time())))

def transition(current,action,admin):
    if current!='pending': raise ValueError('Only pending orders can be changed')
    if action=='cancel': return 'cancelled'
    if admin and action in ['approve','reject']: return 'approved' if action=='approve' else 'rejected'
    raise ValueError('Operation not permitted')

def handle(method,path,user,body=None):
    admin=user['role'] in ADMIN_ROLES
    suffix=path.removeprefix('/api/marketplace/')
    if method=='GET':
        with connect() as con:
            if suffix=='vendors':
                if not admin:return 403,{'error':'Super-admin access required'}
                return 200,con.execute("SELECT u.id,u.username,u.active,COALESCE(v.enabled,0) AS enabled FROM users u LEFT JOIN marketplace_vendors v ON v.user_id=u.id WHERE u.role='reseller' ORDER BY u.username").fetchall()
            if suffix=='capabilities':
                vendor=con.execute('SELECT enabled FROM marketplace_vendors WHERE user_id=?',(user['id'],)).fetchone()
                return 200,{'manage_all':admin,'manage_own':user['role']=='reseller' and bool(vendor and vendor['enabled'])}
            if suffix=='plans':
                public="p.enabled=1 AND (p.seller_id=0 OR EXISTS (SELECT 1 FROM marketplace_vendors v JOIN users u ON u.id=v.user_id WHERE v.user_id=p.seller_id AND v.enabled=1 AND u.active=1 AND u.role='reseller'))"
                query='SELECT p.*,COALESCE(u.display_name,u.username) AS seller_name,u.username AS seller_username FROM hosting_plans p LEFT JOIN users u ON u.id=p.seller_id'
                args=()
                if not admin:
                    query+=' WHERE ('+public+')'
                    if user['role']=='reseller':query+=' OR p.seller_id=?';args=(user['id'],)
                return 200,con.execute(query+' ORDER BY p.price_cents,p.id',args).fetchall()
            if suffix=='orders':
                query='SELECT o.*,u.username FROM hosting_orders o JOIN users u ON u.id=o.owner'
                args=()
                if not admin:
                    query+=' WHERE o.owner=?';args=(user['id'],)
                    if user['role']=='reseller':query+=' OR o.seller_id=?';args=(user['id'],user['id'])
                return 200,con.execute(query+' ORDER BY o.id DESC LIMIT 200',args).fetchall()
            if suffix=='summary':
                where='' if admin else ' WHERE owner=?';args=() if admin else (user['id'],)
                if user['role']=='reseller':where=' WHERE owner=? OR seller_id=?';args=(user['id'],user['id'])
                counts=con.execute('SELECT status,COUNT(*) AS total FROM hosting_orders'+where+' GROUP BY status',args).fetchall()
                return 200,{'scope':'all_accounts' if admin else ('reseller_store' if user['role']=='reseller' else 'your_account'),'counts':{r['status']:r['total'] for r in counts},'enabled_plans':con.execute("SELECT COUNT(*) AS total FROM hosting_plans p WHERE p.enabled=1 AND (p.seller_id=0 OR EXISTS (SELECT 1 FROM marketplace_vendors v JOIN users u ON u.id=v.user_id WHERE v.user_id=p.seller_id AND v.enabled=1 AND u.active=1 AND u.role='reseller'))").fetchone()['total'],'payment_processing':False,'automatic_provisioning':False}
        return 404,{'error':'Unknown marketplace operation'}
    if method!='POST':return 405,{'error':'Unsupported method'}
    if user['role']=='readonly':return 403,{'error':'Read-only access'}
    if suffix=='vendors/save':
        if not admin:return 403,{'error':'Super-admin access required'}
        uid=integer(body,'id',1,2**63-1)
        if type(body.get('enabled')) is not bool:raise ValueError('Enabled must be boolean')
        with connect() as con:
            target=con.execute("SELECT id FROM users WHERE id=? AND role='reseller' FOR UPDATE",(uid,)).fetchone()
            if not target:raise ValueError('Choose a reseller account')
            con.execute('INSERT INTO marketplace_vendors(user_id,enabled) VALUES(?,?) ON DUPLICATE KEY UPDATE enabled=VALUES(enabled)',(uid,int(body['enabled'])))
            audit(con,user,'vendor '+str(uid)+' publishing '+str(body['enabled']))
        return 200,{'ok':True}
    if suffix=='plans/save':
        if not admin and user['role']!='reseller':return 403,{'error':'Catalog access required'}
        if not admin:
            with connect() as con:
                vendor=con.execute('SELECT enabled FROM marketplace_vendors WHERE user_id=?',(user['id'],)).fetchone()
                if not vendor or not vendor['enabled']:return 403,{'error':'Super admin must enable your reseller publishing access'}
        fields=validate_plan(body)
        with connect() as con:
            if body.get('id'):
                uid=integer(body,'id',1,2**63-1)
                row=con.execute('SELECT id,seller_id FROM hosting_plans WHERE id=? FOR UPDATE',(uid,)).fetchone()
                if not row:raise ValueError('Unknown plan')
                if not admin and row['seller_id']!=user['id']:return 403,{'error':'You can only edit your own plans'}
                con.execute('UPDATE hosting_plans SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',(*fields.values(),uid))
            else:
                fields['seller_id']=0 if admin else user['id']
                uid=con.execute('INSERT INTO hosting_plans ('+','.join(fields)+') VALUES ('+','.join('?' for _ in fields)+')',tuple(fields.values())).lastrowid
            audit(con,user,'plan saved '+str(uid))
        return 200,{'ok':True,'id':uid}
    if suffix=='orders/create':
        pid=integer(body,'plan_id',1,2**63-1)
        key=body.get('request_key',''); note=str(body.get('note','')).strip()
        if not re.fullmatch(r'[a-zA-Z0-9_-]{16,64}',str(key)) or len(note)>1000:raise ValueError('Invalid request key or order note')
        if body.get('confirmed') is not True:raise ValueError('Confirm the order request and manual provisioning notice')
        with connect() as con:
            existing=con.execute('SELECT id FROM hosting_orders WHERE owner=? AND request_key=?',(user['id'],key)).fetchone()
            if existing:return 200,{'ok':True,'id':existing['id'],'duplicate':True}
            plan=con.execute('SELECT * FROM hosting_plans WHERE id=? AND enabled=1 FOR UPDATE',(pid,)).fetchone()
            if not plan:raise ValueError('This plan is unavailable')
            if plan['seller_id']:
                vendor=con.execute("SELECT v.user_id FROM marketplace_vendors v JOIN users u ON u.id=v.user_id WHERE v.user_id=? AND v.enabled=1 AND u.active=1 AND u.role='reseller'",(plan['seller_id'],)).fetchone()
                if not vendor:raise ValueError('This reseller storefront is unavailable')
            if plan['seller_id']==user['id']:raise ValueError('You cannot order your own plan')
            if type(body.get('expected_price_cents')) is not int or body['expected_price_cents']!=plan['price_cents']:raise ValueError('Plan price changed. Reload the catalog and confirm the current price.')
            snapshot=json.dumps({k:plan[k] for k in ['name','description','price_cents','disk_gb','bandwidth_gb','websites','seller_id','plan_kind']})
            try:
                uid=con.execute('INSERT INTO hosting_orders(owner,seller_id,plan_id,request_key,plan_snapshot,price_cents,currency,status,note,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(user['id'],plan['seller_id'],pid,key,snapshot,plan['price_cents'],'USD','pending',note,int(time.time()),int(time.time()))).lastrowid
            except IntegrityError:
                existing=con.execute('SELECT id FROM hosting_orders WHERE owner=? AND request_key=? FOR UPDATE',(user['id'],key)).fetchone()
                if not existing:raise
                return 200,{'ok':True,'id':existing['id'],'duplicate':True}
            audit(con,user,'order requested '+str(uid))
        return 200,{'ok':True,'id':uid,'status':'pending','message':'Request recorded. No payment collected or hosting provisioned.'}
    if suffix=='orders/action':
        uid=integer(body,'id',1,2**63-1);action=body.get('action')
        with connect() as con:
            order=con.execute('SELECT * FROM hosting_orders WHERE id=? FOR UPDATE',(uid,)).fetchone()
            seller=bool(order and user['role']=='reseller' and order['seller_id']==user['id'])
            if seller:
                vendor=con.execute('SELECT enabled FROM marketplace_vendors WHERE user_id=?',(user['id'],)).fetchone()
                seller=bool(vendor and vendor['enabled'])
            if not order or (not admin and not seller and order['owner']!=user['id']):return 404,{'error':'Unknown order'}
            if action=='cancel' and not admin and order['owner']!=user['id']:return 403,{'error':'Only buyer or super admin may cancel'}
            status=transition(order['status'],action,admin or seller)
            note=str(body.get('operator_note','')).strip()
            if len(note)>1000:raise ValueError('Note is too long')
            con.execute('UPDATE hosting_orders SET status=?,operator_note=?,updated=? WHERE id=?',(status,note if admin or seller else order['operator_note'],int(time.time()),uid))
            audit(con,user,'order '+str(uid)+' '+status)
        return 200,{'ok':True,'status':status,'message':'Status updated; approval does not provision hosting.'}
    return 404,{'error':'Unknown marketplace operation'}
