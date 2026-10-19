"""Preserve the whole Namecheap zone; credentials arrive only on stdin."""
import sys, json, ipaddress, urllib.request, urllib.parse, xml.etree.ElementTree as ET
NS={'n':'https://api.namecheap.com/xml.response'}
def parse_response(payload):
    root=ET.fromstring(payload)
    for node in root.iter():
        for namespace in ('http://api.namecheap.com/xml.response', NS['n']):
            prefix='{'+namespace+'}'
            if node.tag.startswith(prefix):
                local=node.tag[len(prefix):]
                node.tag='{'+NS['n']+'}'+('host' if local=='Host' else local)
                break
    if root.tag!='{'+NS['n']+'}ApiResponse': raise ValueError('Unrecognized Namecheap XML response')
    return root

def merge(records, names, address):
    ipaddress.IPv4Address(address)
    out=[dict(r) for r in records]
    for name in names:
        same=[r for r in out if r['Name']==name]
        if any(r['Type'] in ('CNAME','AAAA','NS','ALIAS','URL','URL301','FRAME') for r in same):
            raise ValueError('Conflicting record for '+name)
        aa=[r for r in same if r['Type']=='A']
        if len(aa)>1: raise ValueError('Multiple A records for '+name)
        if aa: aa[0]['Address']=address
        else: out.append(dict(Name=name,Type='A',Address=address,TTL='300',MXPref='10'))
    return out

def main():
    cfg=json.load(sys.stdin)
    base={k:cfg[k] for k in ('ApiUser','ApiKey','UserName','ClientIp')}
    base.update(SLD='africandroid',TLD='world')
    def call(cmd,extra=None):
        body=urllib.parse.urlencode(dict(base,Command='namecheap.domains.dns.'+cmd,**(extra or {}))).encode()
        with urllib.request.urlopen(urllib.request.Request('https://api.namecheap.com/xml.response',data=body),timeout=45) as res: root=parse_response(res.read())
        if root.get('Status')!='OK': raise RuntimeError('Namecheap API rejected request; check API access, IP allowlist and DNS provider.')
        return root
    root=call('getHosts'); result=root.find('.//n:DomainDNSGetHostsResult',NS)
    if result is None or result.get('IsUsingOurDNS','').lower()!='true': raise ValueError('Domain must use Namecheap DNS')
    records=[dict(h.attrib) for h in result.findall('n:host',NS)]
    # CAA/DynamicDNS metadata cannot be safely round-tripped by this adapter.
    if any(r['Type']=='CAA' or r.get('IsDDNSEnabled','false').lower()=='true' for r in records): raise ValueError('CAA or DynamicDNS metadata requires manual DNS provisioning')
    names=cfg['names']; new=merge(records,names,cfg['address'])
    if new==records: print('unchanged'); return
    args={}
    email=result.get('EmailType')
    if any(r['Type'] in ('MX','MXE') for r in records):
        if not email: raise ValueError('EmailType unavailable; use manual DNS to preserve email configuration')
        args['EmailType']=email
    for i,r in enumerate(new,1):
        for source,target in [('Name','HostName'),('Type','RecordType'),('Address','Address'),('TTL','TTL'),('MXPref','MXPref')]:
            if source in r: args[target+str(i)]=r[source]
    # Detect edits made between our read and write.
    fresh=call('getHosts').find('.//n:DomainDNSGetHostsResult',NS)
    if [dict(h.attrib) for h in fresh.findall('n:host',NS)]!=records: raise RuntimeError('DNS changed concurrently; rerun')
    reply=call('setHosts',args).find('.//n:DomainDNSSetHostsResult',NS)
    if reply is None or reply.get('IsSuccess','').lower()!='true': raise RuntimeError('DNS update failed')
    verified=call('getHosts').find('.//n:DomainDNSGetHostsResult',NS)
    hosts=[dict(h.attrib) for h in verified.findall('n:host',NS)]
    for name in names:
        if not any(h['Name']==name and h['Type']=='A' and h['Address']==cfg['address'] for h in hosts): raise RuntimeError('DNS verification failed')
    print('changed')
if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(str(exc) if isinstance(exc,(ValueError,RuntimeError)) else 'Namecheap request failed; credentials suppressed',file=sys.stderr);sys.exit(1)
