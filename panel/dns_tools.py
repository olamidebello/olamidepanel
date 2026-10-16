"""Read-only DNS lookups; no shell execution or DNS configuration changes."""
import re
import dns.resolver
TYPES={'A','AAAA','CNAME','MX','NS','TXT','SOA','CAA'}
def lookup(body):
 name=str(body.get('name','')).strip().lower().rstrip('.')
 kind=body.get('type','A')
 if not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?\.)+[a-z0-9-]{2,63}',name):raise ValueError('Enter a valid DNS hostname')
 if kind not in TYPES:raise ValueError('Unsupported DNS record type')
 resolver=dns.resolver.Resolver();resolver.timeout=2;resolver.lifetime=4
 try:
  answer=resolver.resolve(name,kind,search=False)
  return {'name':name,'type':kind,'records':[r.to_text() for r in answer][:100],'ttl':answer.rrset.ttl,'status':'answered'}
 except dns.resolver.NXDOMAIN:return {'name':name,'type':kind,'records':[],'status':'domain does not exist'}
 except dns.resolver.NoAnswer:return {'name':name,'type':kind,'records':[],'status':'no records of this type'}
 except (dns.resolver.NoNameservers,dns.exception.Timeout):raise ValueError('DNS lookup failed or timed out; retry later') from None
