"""Typed static-site controls; only the DNS-verified root worker writes Nginx files."""
import copy,ipaddress,json,re,time
from urllib.parse import urlsplit
from database import connect
DEFAULTS={'redirects':[],'indexes':False,'errors':{},'hotlink':False,'referers':[],'blocked_ips':[]}
DOMAIN=re.compile(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}')

def defaults():return copy.deepcopy(DEFAULTS)

def validate(settings,domain):
 if not isinstance(settings,dict) or set(settings)!=set(DEFAULTS):raise ValueError('All supported site-control fields are required')
 out=defaults()
 for field in ['indexes','hotlink']:
  if type(settings[field]) is not bool:raise ValueError(field+' must be boolean')
  out[field]=settings[field]
 for field in ['blocked_ips','referers','redirects']:
  if not isinstance(settings[field],list) or len(settings[field])>20:raise ValueError(field+' accepts at most 20 entries')
 for raw in settings['blocked_ips']:
  if not isinstance(raw,str):raise ValueError('IP address or CIDR required')
  try:out['blocked_ips'].append(str(ipaddress.ip_network(raw,strict=False)))
  except ValueError:raise ValueError('Valid IPv4/IPv6 address or CIDR required') from None
 for raw in settings['referers']:
  if not isinstance(raw,str) or len(raw)>253 or not DOMAIN.fullmatch(raw.lower()):raise ValueError('Allowed referers must be plain domain names')
  out['referers'].append(raw.lower())
 if not isinstance(settings['errors'],dict) or len(settings['errors'])>7:raise ValueError('Supported error-code map required')
 for code,message in settings['errors'].items():
  if code not in ['400','401','403','404','500','502','503'] or not isinstance(message,str) or not 1<=len(message)<=1000:raise ValueError('Supported HTTP error and message (1–1000 characters) required')
  out['errors'][code]=message
 seen=set();edges={}
 for rule in settings['redirects']:
  if not isinstance(rule,dict) or set(rule)!={'path','target','status'}:raise ValueError('Redirect path, target and status required')
  path,target,status=rule['path'],rule['target'],rule['status']
  if not isinstance(path,str) or len(path)>200 or not re.fullmatch(r'/[A-Za-z0-9/_~.\-]*',path) or any(p.startswith('.') for p in path.split('/') if p) or '//' in path or path.startswith('/_panel-errors') or path in seen:raise ValueError('Unique safe absolute redirect path required')
  if type(status) is not int or status not in [301,302,307,308]:raise ValueError('Valid redirect HTTP status required')
  if not isinstance(target,str) or len(target)>1000 or re.search(r'[\s\\"\x27;$\{\}]',target):raise ValueError('Safe HTTPS redirect URL required')
  try:u=urlsplit(target);host=u.hostname;port=u.port
  except ValueError:raise ValueError('Valid HTTPS redirect URL required') from None
  if u.scheme!='https' or not host or not DOMAIN.fullmatch(host.lower()) or u.username or u.password or port not in [None,443]:raise ValueError('HTTPS target with a valid hostname and standard port required')
  seen.add(path)
  if host.lower()==domain:edges[path]=u.path or '/'
  out['redirects'].append({'path':path,'target':target,'status':status})
 for start in edges:
  visited=set();node=start
  while node in edges:
   if node in visited:raise ValueError('Redirect cycle detected')
   visited.add(node);node=edges[node]
 return out

def nginx(settings,domain):
 s=validate(settings,domain)
 lines=['# Generated OlamidePanel static-site controls','autoindex '+('on' if s['indexes'] else 'off')+';']
 for ip in s['blocked_ips']:lines.append('deny '+ip+';')
 for r in s['redirects']:lines.append('location = '+r['path']+' { return '+str(r['status'])+' "'+r['target']+'"; }')
 for code in s['errors']:lines.append('error_page '+code+' /_panel-errors/'+code+'.html;')
 if s['errors']:lines.append('location ^~ /_panel-errors/ { internal; }')
 if s['hotlink']:
  lines+=['location ~* \\.(?:gif|jpe?g|png|webp|svg|ico)$ {',' valid_referers none blocked server_names '+ ' '.join(s['referers'])+';', ' if ($invalid_referer) { return 403; }',' try_files $uri =404;','}']
 return '\n'.join(lines)+'\n'

def handle(method,user,body=None):
 if method=='GET':
  with connect() as con:rows=con.execute('SELECT d.id,d.name,w.state,w.message,c.settings,c.revision,c.applied_revision FROM domains d LEFT JOIN website_requests w ON w.domain_id=d.id LEFT JOIN website_controls c ON c.domain_id=d.id WHERE d.owner=? ORDER BY d.name',(user['id'],)).fetchall()
  return 200,[{**r,'settings':json.loads(r['settings']) if r['settings'] else defaults(),'revision':r['revision'] or 0,'applied_revision':r['applied_revision'] or 0} for r in rows]
 if user['role']=='readonly':return 403,{'error':'Read-only access'}
 if not isinstance(body,dict) or type(body.get('domain_id')) is not int or type(body.get('revision')) is not int or body['revision']<0:raise ValueError('Domain ID and current revision required')
 with connect() as con:
  domain=con.execute('SELECT id,name FROM domains WHERE id=? AND owner=? FOR UPDATE',(body['domain_id'],user['id'])).fetchone()
  if not domain:return 404,{'error':'Domain unavailable'}
  settings=validate(body.get('settings'),domain['name'])
  old=con.execute('SELECT revision FROM website_controls WHERE domain_id=? FOR UPDATE',(domain['id'],)).fetchone()
  if body['revision']!=(old['revision'] if old else 0):return 409,{'error':'Settings changed. Reload before saving'}
  if not con.execute('SELECT domain_id FROM website_requests WHERE domain_id=? FOR UPDATE',(domain['id'],)).fetchone():return 409,{'error':'Request Site Publisher for this domain first'}
  con.execute('INSERT INTO website_controls(domain_id,settings,revision,updated) VALUES(?,?,1,?) ON DUPLICATE KEY UPDATE settings=VALUES(settings),revision=revision+1,updated=VALUES(updated)',(domain['id'],json.dumps(settings),int(time.time())))
  con.execute("UPDATE website_requests SET state='queued',message='Site control update queued for DNS verification',updated=? WHERE domain_id=?",(int(time.time()),domain['id']))
  con.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)',(user['username'],'static site controls queued '+domain['name'],int(time.time())))
 return 202,{'queued':True,'message':'Saved and queued. DNS proof and provisioning must succeed before these controls are active.'}
