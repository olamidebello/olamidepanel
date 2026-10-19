"""Same-origin, bounded country weather previews with ten minute cache."""
import json,time,threading,os
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlsplit,parse_qs,urlencode
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
ROOT=Path(__file__).parent
COUNTRIES={c['slug']:c for c in json.loads((ROOT/'countries.json').read_text())}
CACHE={}; LOCK=threading.Lock(); LIMIT=threading.BoundedSemaphore(8)
def forecast(country):
    """Prefer the country edition; fall back to the same model provider."""
    params=dict(latitude=country['cities'][0][1], longitude=country['cities'][0][2],
        timezone='auto', forecast_days=7,
        current='temperature_2m,weather_code,wind_speed_10m',
        daily='weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max')
    urls=[
        'https://'+country['domain']+'/api/weather?'+urlencode(dict(lat=params['latitude'],lon=params['longitude'])),
        'https://api.open-meteo.com/v1/forecast?'+urlencode(params)]
    for url in urls:
        try:
            with urlopen(url,timeout=12) as response:
                data=json.loads(response.read(2_000_000))
            current=data.get('current',{});daily=data.get('daily',{})
            if not isinstance(current.get('temperature_2m'),(int,float)) or not daily.get('time'):
                continue
            fields=['time','weather_code','temperature_2m_max','temperature_2m_min','precipitation_probability_max']
            if any(not isinstance(daily.get(k),list) or len(daily[k])!=len(daily['time']) for k in fields):
                continue
            return {k:data[k] for k in ['current','current_units','daily','daily_units','timezone','timezone_abbreviation'] if k in data}
        except Exception:
            continue
    raise ValueError('Forecast unavailable')

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT),**kw)
    def do_GET(self):
        u=urlsplit(self.path)
        if u.path=='/api/health':
            body=b'{"status":"ok","destinations":55}'
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
        if u.path!='/api/preview':
            if u.path not in ['/', '/index.html', '/app.js', '/download.js', '/style.css', '/countries.json', '/download.html', '/privacy.html', '/terms.html', '/copyright.html']:
                return self.send_error(404)
            return super().do_GET()
        slug=parse_qs(u.query).get('country',[''])[0]
        if slug not in COUNTRIES:return self.send_error(400)
        c=COUNTRIES[slug]
        try:
            with LOCK: cached=CACHE.get(slug)
            if cached and cached[0]>time.time():body=cached[1]
            else:
                if not LIMIT.acquire(blocking=False):return self.send_error(503)
                try:
                    data=forecast(c)
                    body=json.dumps(data).encode()
                    with LOCK:CACHE[slug]=(time.time()+600,body)
                finally:LIMIT.release()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        except Exception:self.send_error(502,'Country weather unavailable')
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',int(os.getenv('PORT','18999'))),Handler).serve_forever()
