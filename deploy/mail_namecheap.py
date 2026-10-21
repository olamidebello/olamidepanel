"""Conservative Namecheap mail DNS merge using the panel's encrypted account."""
import ipaddress
import json
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'panel'))
from database import connect
from payments import cipher
from namecheap import call, NS

SUPPORTED={'A','AAAA','ALIAS','CNAME','MX','MXE','NS','TXT','URL','URL301','FRAME'}
LABEL=r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'


def zone_for(name, zones):
    matches=[]
    for z in zones:
        sld,tld=z.get('sld',''),z.get('tld','')
        if not re.fullmatch(LABEL,sld) or not re.fullmatch(LABEL+r'(?:\.'+LABEL+r')*',tld):
            raise ValueError('Invalid explicit Namecheap SLD/TLD mapping')
        domain=sld+'.'+tld
        if name==domain or name.endswith('.'+domain):matches.append((domain,z))
    if not matches:raise ValueError('No configured authoritative zone for '+name)
    domain,z=max(matches,key=lambda v:len(v[0]))
    return domain,z,('@' if name==domain else name[:-(len(domain)+1)])


def txt_value(value):
    if value.startswith('"'):
        import shlex
        return ''.join(shlex.split(value))
    return value


def identity(r):
    kind=r['Type'].upper();value=r['Address']
    if kind in ('MX','CNAME','NS'):value=value.lower().rstrip('.')
    if kind=='TXT':value=txt_value(value)
    return r['Name'].lower(),kind,value,str(int(r.get('MXPref','10'))) if kind in ('MX','MXE') else ''


def merge(records, desired):
    if any(r.get('Type') not in SUPPORTED or r.get('IsDDNSEnabled','false').lower()=='true' for r in records):
        raise ValueError('Unsupported records or Dynamic DNS require manual DNS review')
    result=[dict(r) for r in records]
    for record in desired:
        name,kind,value,_=identity(record)
        same=[r for r in result if r['Name'].lower()==name]
        # A mail host must have one unambiguous IPv4 destination.
        if any(r['Type']=='CNAME' for r in same):raise ValueError('CNAME conflicts with mail DNS: '+name)
        if kind=='A' and any(r['Type'] in ('AAAA','ALIAS') for r in same):
            raise ValueError('Mail hostname AAAA/ALIAS requires explicit migration')
        current=[r for r in same if r['Type']==kind]
        if kind=='MX' and any(r['Type']=='MXE' for r in same):raise ValueError('Existing MXE requires explicit migration')
        if kind=='TXT' and value.startswith('v=spf1'):
            current=[r for r in current if txt_value(r['Address']).lower().startswith('v=spf1')]
        elif kind=='TXT' and value.startswith('v=DMARC1'):
            # Preserve an existing single valid DMARC policy, including stricter enforcement.
            if len(current)==1 and txt_value(current[0]['Address']).startswith('v=DMARC1;'):continue
        elif kind=='TXT' and '._domainkey' not in name:
            current=[r for r in current if identity(r)==identity(record)]
        if current:
            if len(current)!=1 or identity(current[0])!=identity(record):
                raise ValueError('Existing mail record differs; review migration for '+name+' '+kind)
        else:result.append(dict(record))
    if len(result)>150:raise ValueError('Zone exceeds safe Namecheap record limit')
    return result


def provision(desired, config):
    if config.get('mode')!='namecheap':raise ValueError('Namecheap mode required')
    zones=config.get('zones',[])
    if not isinstance(zones,list) or not 1<=len(zones)<=100:raise ValueError('Explicit Namecheap zones required')
    grouped={}
    # Validate and group everything before contacting the provider.
    for name,kind,value in desired:
        if not re.fullmatch(LABEL+r'(?:\.'+LABEL+r')*',name.replace('_domainkey','domainkey').replace('_dmarc','dmarc')):
            raise ValueError('Invalid DNS name')
        domain,z,host=zone_for(name,zones)
        if kind not in ('A','TXT','MX') or '\n' in value or '\r' in value:raise ValueError('Unsupported mail DNS value')
        record={'Name':host,'Type':kind,'TTL':'300','Address':value}
        if kind=='MX':
            pref,target=value.split();record.update(Address=target.rstrip('.'),MXPref=str(int(pref)))
        elif kind=='TXT':record['Address']=txt_value(value)
        elif kind=='A':record['Address']=str(ipaddress.IPv4Address(value))
        grouped.setdefault(domain,{'zone':z,'desired':[]})['desired'].append(record)
    with connect() as con:row=con.execute('SELECT * FROM namecheap_accounts WHERE id=?',(int(config['account_id']),)).fetchone()
    if not row or row['mode']!=config.get('environment','production'):
        raise ValueError('Saved Namecheap account missing or environment differs')
    account=json.loads(cipher().decrypt(row['credentials'].encode()))|{'mode':row['mode']}
    def read(z):
        root=call(account,'domains.dns.getHosts',SLD=z['sld'],TLD=z['tld'])
        result=root.find('.//n:DomainDNSGetHostsResult',NS)
        if result is None or result.get('IsUsingOurDNS','').lower()!='true':raise ValueError('Namecheap is not authoritative for this zone')
        return result,[dict(h.attrib) for h in result.findall('n:host',NS)]
    plans=[]
    for domain,group in grouped.items():
        result,records=read(group['zone'])
        updated=merge(records,group['desired'])
        # Redirect/forwarding mail modes cannot safely be converted implicitly.
        has_mx=any(r['Type']=='MX' for r in group['desired'])
        if has_mx and result.get('EmailType') not in ('MX','MXE') and not config.get('allow_custom_mx',False):
            raise ValueError('Switch zone to Custom MX or explicitly enable allow_custom_mx after reviewing mail routing')
        plans.append((domain,group,result.get('EmailType'),records,updated))
    changed=[]
    for domain,group,email_type,records,updated in plans:
        if updated==records:continue
        fresh,hosts=read(group['zone'])
        if hosts!=records or fresh.get('EmailType')!=email_type:raise ValueError('DNS changed during provisioning; inspect and retry')
        params={'SLD':group['zone']['sld'],'TLD':group['zone']['tld']}
        if any(r['Type']=='MX' for r in group['desired']):params['EmailType']='MX'
        elif email_type:params['EmailType']=email_type
        for i,record in enumerate(updated,1):
            for source,target in [('Name','HostName'),('Type','RecordType'),('Address','Address'),('TTL','TTL'),('MXPref','MXPref')]:
                if source in record:params[target+str(i)]=record[source]
        result=call(account,'domains.dns.setHosts',**params).find('.//n:DomainDNSSetHostsResult',NS)
        if result is None or result.get('IsSuccess','').lower()!='true':raise ValueError('Namecheap did not confirm DNS update')
        _,observed=read(group['zone'])
        signature=lambda r: identity(r)+(str(int(r.get('TTL','1800'))),)
        if sorted(map(signature,observed))!=sorted(map(signature,updated)):
            raise ValueError('DNS was submitted but read-back differs; inspect zone before retrying')
        changed.append(domain)
    return {'mode':'namecheap','changed':bool(changed),'changed_zones':changed,'pending':0,'verification':'provider read-back; public DNS propagation not verified'}
