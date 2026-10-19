"""Idempotently add the shared app to installed country editions, including Nigeria."""
from pathlib import Path
import json
link='<p data-africaweather-app style="padding:20px;text-align:center"><a href="https://africaweather.africandroid.world/download.html">Download Africa Weather for Android</a> · <a href="https://africaweather.africandroid.world/">All Africa forecasts</a></p>'
roots={Path('/opt/olamide-weather')/c['slug']/'static' for c in json.loads((Path(__file__).parent/'countries.json').read_text())}
# Nigeria may be installed independently; only edit an explicit configured root.
roots.add(Path('/opt/weathernigeria/static'))
import os
if os.getenv('NIGERIA_STATIC_ROOT'):roots.add(Path(os.environ['NIGERIA_STATIC_ROOT']))
for root in sorted(roots):
    page=root/'index.html'
    if page.is_file():
        s=page.read_text()
        if 'data-africaweather-app' not in s and 'https://africaweather.africandroid.world/download.html' not in s:
            if '</body>' not in s:raise ValueError('Missing body end: '+str(page))
            page.write_text(s.replace('</body>',link+'</body>'))
