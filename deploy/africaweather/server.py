"""Same-origin, bounded country weather previews with ten minute cache."""
import json,time,threading,os
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlsplit,parse_qs,urlencode
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
ROOT=Path(__file__).parent
COUNTRIES={c['slug']:c for c in json.loads((ROOT/'countries.json').read_text())}
CACHE={}; LOCK=threading.Lock(); LIMIT=threading.BoundedSemaphore(8)
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT),**kw)
    def do_GET(self):
        u=urlsplit(self.path)
        if u.path!='/api/preview': return super().do_GET()
        slug=parse_qs(u.query).get('country',[''])[0]
        if slug not in COUNTRIES:return self.send_error(400)
        c=COUNTRIES[slug]
        try:
            with LOCK: cached=CACHE.get(slug)
            if cached and cached[0]>time.time():body=cached[1]
            else:
                if not LIMIT.acquire(blocking=False):return self.send_error(503)
                try:
                    url='https://'+c['domain']+'/api/weather?'+urlencode(dict(lat=c['cities'][0][1],lon=c['cities'][0][2]))
                    with urlopen(url,timeout=15) as res:data=json.loads(res.read(2_000_000))
                    body=json.dumps({k:data[k] for k in ['current','current_units','timezone','timezone_abbreviation'] if k in data}).encode()
                    with LOCK:CACHE[slug]=(time.time()+600,body)
                finally:LIMIT.release()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        except Exception:self.send_error(502,'Country weather unavailable')
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',int(os.getenv('PORT','18999'))),Handler).serve_forever()
