"""Durable paid-service activation. Runs as the panel user, never as root."""
import json,time,logging
from database import connect
import storage

KINDS={'hosting','reseller'}
MONTH=30*24*60*60

def enqueue(con,payment):
    """Called in the same transaction that records provider verification."""
    if payment['mode']!='live' or payment['state']!='paid':return
    if con.execute('SELECT order_id FROM provisioning_jobs WHERE order_id=?',(payment['order_id'],)).fetchone():return
    now=int(time.time())
    con.execute("INSERT IGNORE INTO provisioning_jobs(order_id,payment_id,state,attempts,next_attempt,message,updated) VALUES(?,?,'queued',0,?,'Payment verified; awaiting account activation',?)",(payment['order_id'],payment['id'],now,now))

def allocation(snapshot):
    if snapshot.get('plan_kind') not in KINDS:raise ValueError('No provisioning adapter for this service type')
    for key,upper in [('disk_gb',1000000),('websites',100000),('bandwidth_gb',10000000)]:
        if type(snapshot.get(key)) is not int or not 1<=snapshot[key]<=upper:raise ValueError('Invalid purchased service allocation')
    return snapshot

def activate(con,job,now):
    order=con.execute('SELECT * FROM hosting_orders WHERE id=? FOR UPDATE',(job['order_id'],)).fetchone()
    payment=con.execute('SELECT * FROM payment_transactions WHERE id=? FOR UPDATE',(job['payment_id'],)).fetchone()
    if not order or not payment:raise ValueError('Order or payment missing; operator review required')
    if payment['state']!='paid' or payment['mode']!='live' or not payment['verified_at']:raise ValueError('Verified live payment required')
    if (payment['order_id'],payment['buyer_id'],payment['seller_id'],payment['amount_cents'],payment['currency'])!=(order['id'],order['owner'],order['seller_id'],order['price_cents'],order['currency']):raise ValueError('Order and payment do not match')
    if order['status']!='approved':raise ValueError('Order is not approved')
    buyer=con.execute('SELECT * FROM users WHERE id=? FOR UPDATE',(order['owner'],)).fetchone()
    if not buyer or not buyer['active'] or buyer['role']=='readonly':raise ValueError('Buyer account requires operator review')
    if order['seller_id']:
        seller=con.execute("SELECT u.id FROM users u JOIN marketplace_vendors v ON v.user_id=u.id WHERE u.id=? AND u.active=1 AND u.role='reseller' AND v.enabled=1",(order['seller_id'],)).fetchone()
        if not seller:raise ValueError('Seller storefront is unavailable')
    existing=con.execute('SELECT order_id FROM hosting_services WHERE order_id=?',(order['id'],)).fetchone()
    if existing:return
    plan=allocation(json.loads(order['plan_snapshot']))
    # Login already exists because checkout is authenticated. Reuse it; never reset passwords.
    home=storage.home(buyer['id'])
    if home.is_symlink() or not home.is_dir():raise ValueError('Unsafe account storage directory')
    if plan['plan_kind']=='reseller' and buyer['role']=='reseller':
        vendor=con.execute('SELECT enabled FROM marketplace_vendors WHERE user_id=?',(buyer['id'],)).fetchone()
        if not vendor or not vendor['enabled']:raise ValueError('Existing reseller storefront requires operator approval')
    role_granted=0
    if plan['plan_kind']=='reseller' and buyer['role']=='user':
        con.execute("UPDATE users SET role='reseller' WHERE id=?",(buyer['id'],))
        con.execute('INSERT INTO marketplace_vendors(user_id,enabled) VALUES(?,1) ON DUPLICATE KEY UPDATE enabled=1',(buyer['id'],))
        con.execute("INSERT IGNORE INTO marketplace_stores(owner_id,name,description,contact_email,updated) VALUES(?,?,'',?,?)",(buyer['id'],buyer['username']+' store',buyer['email'],now))
        role_granted=1
    con.execute("INSERT INTO hosting_services(order_id,payment_id,owner,seller_id,kind,disk_bytes,websites,bandwidth_gb,state,activated_at,expires_at,role_granted) VALUES(?,?,?,?,?,?,?,?,'active',?,?,?)",(order['id'],payment['id'],buyer['id'],order['seller_id'],plan['plan_kind'],plan['disk_gb']*1024**3,plan['websites'],plan['bandwidth_gb'],now,now+MONTH,role_granted))
    con.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)',('service-worker','activated paid service order '+str(order['id']),now))

def run_batch(limit=20):
    """Row locks cover activation and completion. Crashes roll back; retries reuse one job."""
    now=int(time.time())
    # Read candidates before inserting, avoiding INSERT...SELECT source locks against
    # concurrent activation transactions. Unique keys still arbitrate duplicate recovery.
    with connect() as con:
        recovered=con.execute("SELECT p.* FROM payment_transactions p LEFT JOIN provisioning_jobs j ON j.order_id=p.order_id WHERE p.state='paid' AND p.mode='live' AND p.verified_at IS NOT NULL AND j.order_id IS NULL LIMIT 100").fetchall()
    for payment in recovered:
        with connect() as con:enqueue(con,payment)
    with connect() as con:
        con.execute("UPDATE hosting_services SET state='expired' WHERE state='active' AND expires_at<=?",(now,))
        # Only revoke reseller roles originally granted by this worker, never administrator roles.
        expired=con.execute("SELECT DISTINCT owner FROM hosting_services WHERE role_granted=1 AND state='expired'").fetchall()
        for row in expired:
            buyer=con.execute('SELECT role FROM users WHERE id=? FOR UPDATE',(row['owner'],)).fetchone()
            active=con.execute("SELECT order_id FROM hosting_services WHERE owner=? AND kind='reseller' AND state='active' AND expires_at>?",(row['owner'],now)).fetchone()
            if buyer and buyer['role']=='reseller' and not active:
                con.execute("UPDATE users SET role='user' WHERE id=?",(row['owner'],))
                con.execute('UPDATE marketplace_vendors SET enabled=0 WHERE user_id=?',(row['owner'],))
    for _ in range(limit):
        job=None
        try:
            with connect() as con:
                job=con.execute("SELECT * FROM provisioning_jobs WHERE state IN ('queued','retrying') AND next_attempt<=? ORDER BY updated,order_id LIMIT 1 FOR UPDATE SKIP LOCKED",(now,)).fetchone()
                if not job:break
                activate(con,job,now)
                con.execute("UPDATE provisioning_jobs SET state='active',message='Account resources activated; use your existing panel login',updated=? WHERE order_id=?",(now,job['order_id']))
        except Exception as error:
            if job is None:raise
            logging.exception('Account activation failed for order %s',job['order_id'])
            # This update follows rollback, so a partial DB activation is never recorded as active.
            with connect() as con:
                current=con.execute('SELECT * FROM provisioning_jobs WHERE order_id=? FOR UPDATE',(job['order_id'],)).fetchone()
                if current['state']=='active':continue
                attempts=current['attempts']+1
                message=str(error)[:400] if isinstance(error,ValueError) else 'Activation failed; operator should inspect worker logs'
                con.execute('UPDATE provisioning_jobs SET state=?,attempts=?,next_attempt=?,message=?,updated=? WHERE order_id=?',('needs_attention' if attempts>=5 else 'retrying',attempts,now+min(3600,60*2**attempts),message,now,job['order_id']))

def limits(uid):
    with connect() as con:
        row=con.execute("SELECT COALESCE(SUM(disk_bytes),0) AS disk_bytes,COALESCE(SUM(websites),0) AS websites FROM hosting_services WHERE owner=? AND state='active' AND expires_at>?",(uid,int(time.time()))).fetchone()
    return {'disk_bytes':max(250*1024**2,int(row['disk_bytes'])),'websites':int(row['websites'])}

if __name__=='__main__':run_batch()
