"""Country scoping and feature preservation against a real pinned source checkout."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from urllib.request import urlopen
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('weather_render', ROOT / 'deploy/weather/render.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)

class WeatherEditions(unittest.TestCase):
    def test_all_editions_and_country_search(self):
        source = Path(os.environ.get('WEATHER_TEST_SOURCE', ROOT.parent / 'weathernigeria'))
        if not (source / 'server.py').exists():
            self.skipTest('Set WEATHER_TEST_SOURCE to the pinned WeatherNigeria checkout')
        countries = json.loads((ROOT / 'ansible/weather/countries.json').read_text())
        self.assertEqual(len(countries), 54)
        self.assertEqual(len({c['domain'] for c in countries}), 54)
        with tempfile.TemporaryDirectory() as tmp:
            for country in countries:
                with self.subTest(country=country['slug']):
                    dest = Path(tmp) / country['slug']
                    renderer.render(source, dest, country)
                    subprocess.run(['node', '--check', str(dest / 'static/app.js')], check=True, capture_output=True)
                    text = (dest / 'static/index.html').read_text()
                    self.assertIn(country['name'], text)
                    self.assertNotIn('Nigeria', text)
                    self.assertNotIn('WAT', text)
                    for feature in ['hourly', 'daily', 'map-layer', 'locate', 'units', 'terms.html', 'privacy.html', 'copyright.html']:
                        self.assertIn(feature, text)
                    spec = importlib.util.spec_from_file_location('edition', dest / 'server.py')
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    city = country['cities'][0]
                    self.assertEqual(module.coordinates({'lat':[str(city[1])], 'lon':[str(city[2])]}), tuple(city[1:]))
                    with self.assertRaises(ValueError):
                        module.coordinates({'lat':['90'], 'lon':['180']})
                    calls=[]
                    def upstream(host, path, params):
                        calls.append(params)
                        return {'results':[{'country_code':country['code']}, {'country_code':'NG'}]}
                    module.upstream=upstream
                    server=ThreadingHTTPServer(('127.0.0.1',0), module.Handler)
                    threading.Thread(target=server.serve_forever,daemon=True).start()
                    try:
                        with urlopen(f'http://127.0.0.1:{server.server_port}/api/search?q=city') as response:
                            data=json.load(response)
                        self.assertEqual(data['results'], [{'country_code':country['code']}])
                        self.assertEqual(calls[0]['countryCode'], country['code'])
                    finally:
                        server.shutdown(); server.server_close()
