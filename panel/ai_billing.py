"""Metered text chat: immutable buying rates, 30% markup, reservations and idempotent debits."""
import hashlib
import json
import re
import time
from decimal import Decimal, ROUND_HALF_UP
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import api_keys
from database import connect
from payments import cipher

MARKUP = Decimal('1.30')
UNIT = Decimal('0.0000000001')
SCHEMA = '''
CREATE TABLE IF NOT EXISTS ai_service_config (
 id INT PRIMARY KEY,
 config TEXT NOT NULL
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS ai_balances (
 user_id BIGINT PRIMARY KEY,
 balance DECIMAL(24,10) NOT NULL DEFAULT 0
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS ai_requests (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 owner BIGINT NOT NULL,
 request_key VARCHAR(64) CHARACTER SET ascii NOT NULL,
 fingerprint CHAR(64) CHARACTER SET ascii NOT NULL,
 domain VARCHAR(253) CHARACTER SET ascii NOT NULL,
 model VARCHAR(100) CHARACTER SET ascii NOT NULL,
 rate_snapshot TEXT NOT NULL,
 state VARCHAR(24) NOT NULL,
 reserved DECIMAL(24,10) NOT NULL,
 buy_cost DECIMAL(24,10),
 user_charge DECIMAL(24,10),
 input_tokens BIGINT,
 cached_tokens BIGINT,
 output_tokens BIGINT,
 provider_id VARCHAR(150) NOT NULL DEFAULT '',
 encrypted_response MEDIUMTEXT,
 created BIGINT NOT NULL,
 updated BIGINT NOT NULL,
 UNIQUE KEY ai_user_request(owner,request_key)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS ai_balance_ledger (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 user_id BIGINT NOT NULL,
 request_key VARCHAR(64) CHARACTER SET ascii NOT NULL,
 amount DECIMAL(24,10) NOT NULL,
 reason VARCHAR(250) NOT NULL,
 actor VARCHAR(64) NOT NULL,
 created BIGINT NOT NULL,
 UNIQUE KEY ai_credit_request(user_id,request_key)
) ENGINE=InnoDB;
'''
DEFAULT = dict(enabled=False, key_id=0, model='', input_rate='0', cached_rate='0', output_rate='0',
               domains=[], max_output_tokens=1024, price_reference='', pricing_reviewed=False)


def initialize(db=connect):
    with db() as con:
        for sql in SCHEMA.split(';'):
            if sql.strip(): con.execute(sql)
        con.execute('INSERT IGNORE INTO ai_service_config(id,config) VALUES(1,?)',(json.dumps(DEFAULT),))


def amount(value):
    try: result = Decimal(str(value))
    except Exception: raise ValueError('Invalid monetary amount') from None
    if not result.is_finite() or result < 0 or result > Decimal('1000000'):
        raise ValueError('Amount must be between 0 and 1000000 USD')
    return result.quantize(UNIT, rounding=ROUND_HALF_UP)


def pricing_version(cfg):return hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()


def billed(cost): return (Decimal(cost) * MARKUP).quantize(UNIT, rounding=ROUND_HALF_UP)


def cost_for(usage, rates):
    if not isinstance(usage,dict): raise ValueError('Missing provider usage; review required')
    inputs = usage.get('prompt_tokens'); outputs = usage.get('completion_tokens')
    details = usage.get('prompt_tokens_details') or {}
    cached = details.get('cached_tokens',0)
    if any(type(n) is not int or n < 0 for n in (inputs, outputs, cached)) or cached > inputs:
        raise ValueError('Invalid provider usage; review required')
    if details.get('audio_tokens',0) or details.get('image_tokens',0) or details.get('cache_write_tokens',0):
        raise ValueError('Unexpected non-text usage; review required')
    cost = ((inputs-cached)*amount(rates['input_rate']) + cached*amount(rates['cached_rate']) + outputs*amount(rates['output_rate']))/Decimal(1000000)
    return cost.quantize(UNIT, rounding=ROUND_HALF_UP), inputs, cached, outputs


def configuration(con):
    row=con.execute('SELECT config FROM ai_service_config WHERE id=1').fetchone()
    return json.loads(row['config']) if row else dict(DEFAULT)


def validate_config(body):
    cfg={k:body.get(k,DEFAULT[k]) for k in DEFAULT}
    if type(cfg['enabled']) is not bool or type(cfg['pricing_reviewed']) is not bool:
        raise ValueError('Enable and pricing confirmation must be booleans')
    if not isinstance(cfg['model'],str) or len(cfg['model'])>100 or not re.fullmatch(r'gpt-[a-z0-9.-]+-[0-9]{4}-[0-9]{2}-[0-9]{2}',cfg['model']) or any(kind in cfg['model'] for kind in ('search','audio','image','realtime','transcrib','tts','embedding','deep-research')):
        raise ValueError('Enter the exact text-chat model snapshot from your OpenAI account')
    if type(cfg['key_id']) is not int or cfg['key_id']<=0:
        raise ValueError('Choose a saved OpenAI credential')
    if type(cfg['max_output_tokens']) is not int or not 1<=cfg['max_output_tokens']<=4096:
        raise ValueError('Output limit must be 1–4096 tokens')
    if not isinstance(cfg['domains'],list) or not cfg['domains'] or len(cfg['domains'])>200:
        raise ValueError('Select 1–200 domains')
    for domain in cfg['domains']:
        if not isinstance(domain,str) or len(domain)>253 or not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}',domain):
            raise ValueError('Invalid AI service domain')
    for key in ('input_rate','cached_rate','output_rate'):cfg[key]=str(amount(cfg[key]))
    if amount(cfg['cached_rate'])>amount(cfg['input_rate']):raise ValueError('Cached rate cannot exceed the normal input rate')
    if len(str(cfg['price_reference']))>250:raise ValueError('Pricing reference is too long')
    if cfg['enabled'] and (not cfg['pricing_reviewed'] or not cfg['price_reference'] or amount(cfg['input_rate'])<=0 or amount(cfg['output_rate'])<=0):
        raise ValueError('Confirm current buying rates and reference before enabling')
    return cfg


def public_request(row,include_answer=False):
    keys=('id','owner','request_key','domain','model','state','reserved','buy_cost','user_charge','input_tokens','cached_tokens','output_tokens','provider_id','created','updated')
    result={k:str(row[k]) if isinstance(row.get(k),Decimal) else row.get(k) for k in keys}
    if include_answer and row.get('encrypted_response'):
        try:result['answer']=cipher().decrypt(row['encrypted_response'].encode()).decode()
        except Exception:raise ValueError('Saved response cannot be decrypted') from None
    return result


def settle(con,row,cost,usage=None,answer=None,provider_id='',state='completed'):
    # Caller locks the user's balance before the request row; terminal states are immutable.
    if row['state'] not in ('pending','needs_review'):return
    cost=amount(cost);charge=billed(cost)
    if charge>Decimal(str(row['reserved'])):raise ValueError('Provider cost exceeds reservation; manual review required')
    refund=Decimal(str(row['reserved']))-charge
    con.execute('UPDATE ai_balances SET balance=balance+? WHERE user_id=?',(refund,row['owner']))
    tokens=usage or (None,None,None)
    encrypted=cipher().encrypt(answer.encode()).decode() if answer is not None else None
    con.execute('UPDATE ai_requests SET state=?,buy_cost=?,user_charge=?,input_tokens=?,cached_tokens=?,output_tokens=?,provider_id=?,encrypted_response=?,updated=? WHERE id=?',
                (state,cost,charge,*tokens,provider_id,encrypted,int(time.time()),row['id']))
    con.execute('INSERT INTO ai_balance_ledger(user_id,request_key,amount,reason,actor,created) VALUES(?,?,?,?,?,?)',
                (row['owner'],'settle-'+str(row['id']),refund,'Reserve adjustment; total user charge '+str(charge),'ai-meter',int(time.time())))


def provider_call(key,model,prompt,max_output):
    # Fixed endpoint, no tools, text only, one result, no streaming or automatic retries.
    data=json.dumps(dict(model=model,messages=[dict(role='user',content=prompt)],max_completion_tokens=max_output,n=1,store=False,service_tier='default')).encode()
    request=Request('https://api.openai.com/v1/chat/completions',data=data,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    with urlopen(request,timeout=90) as response:
        payload=response.read(2_000_001)
        if len(payload)>2_000_000:raise ValueError('Provider response too large')
        return json.loads(payload)


def chat(user,body,db=connect):
    if user.get('role')=='readonly':raise PermissionError('Read-only accounts cannot use paid services')
    prompt=body.get('prompt','');request_key=body.get('request_key','');domain=body.get('domain','')
    if not isinstance(prompt,str) or not prompt.strip() or len(prompt.encode())>32000:
        raise ValueError('Enter a text prompt of at most 32000 UTF-8 bytes')
    if not isinstance(request_key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,64}',request_key):raise ValueError('Invalid request identifier')
    if body.get('confirmed') is not True:raise ValueError('Confirm usage-based pricing at provider cost plus 30%')
    fingerprint=hashlib.sha256(json.dumps([prompt,domain],ensure_ascii=True).encode()).hexdigest()
    with db() as con:
        con.execute('INSERT IGNORE INTO ai_balances(user_id,balance) VALUES(?,0)',(user['id'],))
        balance=con.execute('SELECT balance FROM ai_balances WHERE user_id=? FOR UPDATE',(user['id'],)).fetchone()
        previous=con.execute('SELECT * FROM ai_requests WHERE owner=? AND request_key=?',(user['id'],request_key)).fetchone()
        if previous:
            if previous['fingerprint']!=fingerprint:raise ValueError('Request identifier belongs to a different prompt')
            return public_request(previous,True)
        cfg=configuration(con)
        if body.get('pricing_version')!=pricing_version(cfg):raise ValueError('Pricing settings changed; reload and confirm the current rates')
        if not cfg['enabled'] or domain not in cfg['domains']:raise ValueError('AI service is disabled for this domain')
        if con.execute("SELECT id FROM ai_requests WHERE owner=? AND state IN ('pending','needs_review') LIMIT 1",(user['id'],)).fetchone():
            raise ValueError('An earlier request is pending or needs review')
        key=api_keys.resolve_openai(cfg['key_id'],domain)
        # For text byte-level tokenizers, UTF-8 byte count plus framing is conservative.
        estimate={'prompt_tokens':len(prompt.encode())+1024,'completion_tokens':cfg['max_output_tokens']}
        reserve=billed(cost_for(estimate,cfg)[0])
        if Decimal(str(balance['balance']))<reserve:raise ValueError('Insufficient AI balance for this request reservation')
        now=int(time.time())
        rid=con.execute("INSERT INTO ai_requests(owner,request_key,fingerprint,domain,model,rate_snapshot,state,reserved,created,updated) VALUES(?,?,?,?,?,?,'pending',?,?,?)",(user['id'],request_key,fingerprint,domain,cfg['model'],json.dumps(cfg),reserve,now,now)).lastrowid
        con.execute('UPDATE ai_balances SET balance=balance-? WHERE user_id=?',(reserve,user['id']))
        con.execute('INSERT INTO ai_balance_ledger(user_id,request_key,amount,reason,actor,created) VALUES(?,?,?,?,?,?)',(user['id'],'reserve-'+str(rid),-reserve,'Usage reservation','ai-meter',now))
    result=None
    try:
        result=provider_call(key,cfg['model'],prompt,cfg['max_output_tokens'])
        if result.get('model')!=cfg['model'] or result.get('service_tier','default')!='default':raise ValueError('Provider model or service tier differs from configured buying rates')
        cost,inputs,cached,outputs=cost_for(result.get('usage'),cfg)
        answer=result['choices'][0]['message'].get('content') or ''
        if not isinstance(answer,str):raise ValueError('Unexpected non-text output')
        with db() as con:
            con.execute('SELECT balance FROM ai_balances WHERE user_id=? FOR UPDATE',(user['id'],)).fetchone()
            row=con.execute('SELECT * FROM ai_requests WHERE id=? FOR UPDATE',(rid,)).fetchone()
            settle(con,row,cost,(inputs,cached,outputs),answer,str(result.get('id',''))[:150])
    except Exception as exc:
        with db() as con:
            con.execute('SELECT balance FROM ai_balances WHERE user_id=? FOR UPDATE',(user['id'],)).fetchone()
            row=con.execute('SELECT * FROM ai_requests WHERE id=? FOR UPDATE',(rid,)).fetchone()
            if isinstance(exc,HTTPError) and exc.code in (400,401,403,404,422,429):
                settle(con,row,Decimal(0),state='failed')
            elif row['state']=='pending':
                con.execute("UPDATE ai_requests SET state='needs_review',provider_id=?,updated=? WHERE id=?",(str(result.get('id',''))[:150] if isinstance(result,dict) else '',int(time.time()),rid))
        # No upstream body, prompt or credential appears in errors or audit records.
    with db() as con:return public_request(con.execute('SELECT * FROM ai_requests WHERE id=? AND owner=?',(rid,user['id'])).fetchone(),True)


def handle(method,user,body=None,db=connect):
    admin=user.get('role') in ('root','super_admin')
    if method=='GET':
        with db() as con:
            cfg=configuration(con)
            balance=con.execute('SELECT balance FROM ai_balances WHERE user_id=?',(user['id'],)).fetchone()
            rows=con.execute('SELECT * FROM ai_requests WHERE owner=? ORDER BY id DESC LIMIT 100',(user['id'],)).fetchall()
            result={'pricing_version':pricing_version(cfg),'config':cfg if admin else {k:cfg[k] for k in ('enabled','model','domains','max_output_tokens','input_rate','cached_rate','output_rate')},'markup_percent':30,'currency':'USD','balance':str(balance['balance']) if balance else '0','requests':[public_request(r) for r in rows]}
            if admin:
                result['balances']=[dict(user_id=r['id'],username=r['username'],balance=str(r['balance'] or 0)) for r in con.execute('SELECT u.id,u.username,b.balance FROM users u LEFT JOIN ai_balances b ON b.user_id=u.id ORDER BY u.id LIMIT 500').fetchall()]
                result['usage_report']=[public_request(r) for r in con.execute('SELECT * FROM ai_requests ORDER BY id DESC LIMIT 200').fetchall()]
                result['reviews']=[public_request(r) for r in con.execute("SELECT * FROM ai_requests WHERE state IN ('pending','needs_review') ORDER BY id LIMIT 200").fetchall()]
            return result
    body=body or {};action=body.get('action')
    if action=='chat':return chat(user,body,db)
    if not admin:raise PermissionError('Super-admin access required')
    if action=='config':
        cfg=validate_config(body)
        # Validate assignment/expiry without making a paid API request.
        if cfg['enabled']:
            for domain in cfg['domains']:api_keys.resolve_openai(cfg['key_id'],domain)
        with db() as con:
            con.execute('UPDATE ai_service_config SET config=? WHERE id=1',(json.dumps(cfg),))
            con.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)',(user['username'],'ai:configuration updated; markup=30%',int(time.time())))
        return {'ok':True}
    if action=='credit':
        uid=body.get('user_id');value=amount(body.get('amount'));note=str(body.get('note','')).strip();request_key=body.get('request_key','')
        if type(uid) is not int or uid<=0 or value<=0 or not 1<=len(note)<=200 or not re.fullmatch(r'[A-Za-z0-9_-]{16,64}',request_key):raise ValueError('Provide user, positive credit, reason and request ID')
        with db() as con:
            if not con.execute('SELECT id FROM users WHERE id=? AND active=1',(uid,)).fetchone():raise ValueError('Unknown active user')
            con.execute('INSERT IGNORE INTO ai_balances(user_id,balance) VALUES(?,0)',(uid,))
            con.execute('SELECT balance FROM ai_balances WHERE user_id=? FOR UPDATE',(uid,)).fetchone()
            duplicate=con.execute('SELECT amount,reason FROM ai_balance_ledger WHERE user_id=? AND request_key=?',(uid,request_key)).fetchone()
            if duplicate:
                if Decimal(str(duplicate['amount']))!=value or duplicate['reason']!=note:raise ValueError('Credit request ID belongs to another adjustment')
                return {'ok':True,'duplicate':True}
            con.execute('UPDATE ai_balances SET balance=balance+? WHERE user_id=?',(value,uid))
            con.execute('INSERT INTO ai_balance_ledger(user_id,request_key,amount,reason,actor,created) VALUES(?,?,?,?,?,?)',(uid,request_key,value,note,user['username'],int(time.time())))
            con.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)',(user['username'],'ai:credit user='+str(uid)+' USD='+str(value),int(time.time())))
        return {'ok':True}
    if action=='reconcile':
        rid=body.get('id');cost=amount(body.get('buy_cost'));note=str(body.get('note','')).strip()
        if type(rid) is not int or not 1<=len(note)<=200:raise ValueError('Select request and supply reconciliation evidence')
        with db() as con:
            target=con.execute('SELECT owner FROM ai_requests WHERE id=?',(rid,)).fetchone()
            if not target:raise ValueError('Unknown request')
            con.execute('SELECT balance FROM ai_balances WHERE user_id=? FOR UPDATE',(target['owner'],)).fetchone()
            row=con.execute('SELECT * FROM ai_requests WHERE id=? FOR UPDATE',(rid,)).fetchone()
            if row['state']=='pending' and int(time.time())-row['updated']<600:raise ValueError('Request may still be running; wait 10 minutes before reconciliation')
            if row['state'] not in ('needs_review','pending'):raise ValueError('Only uncertain requests can be reconciled')
            settle(con,row,cost,state='reconciled')
            con.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)',(user['username'],'ai:reconcile request='+str(rid)+' cost='+str(cost)+' evidence='+note,int(time.time())))
        return {'ok':True}
    raise ValueError('Unknown AI operation')
