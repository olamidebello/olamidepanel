"""Create a country edition from the pinned, complete WeatherNigeria source."""
import argparse
import json
import pathlib
import shutil


def replace(text, old, new):
    if old not in text:
        raise ValueError('WeatherNigeria source contract changed: ' + old[:80])
    return text.replace(old, new)


def render(source, destination, country):
    source, destination = pathlib.Path(source), pathlib.Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source / 'static', destination / 'static', dirs_exist_ok=True)
    name = country['name']
    server = (source / 'server.py').read_text()
    server = replace(server, "ROOT = Path(__file__).parent / 'static'", "ROOT = Path(__file__).parent / 'static'\nCOUNTRY = json.loads((Path(__file__).parent / 'country.json').read_text())")
    server = replace(server, '4 <= lat <= 14 and 2.5 <= lon <= 15', "COUNTRY['bounds'][0] <= lat <= COUNTRY['bounds'][1] and COUNTRY['bounds'][2] <= lon <= COUNTRY['bounds'][3]")
    server = replace(server, "'countryCode': 'NG'", "'countryCode': COUNTRY['code']")
    server = replace(server, "r.get('country_code') == 'NG'", "r.get('country_code') == COUNTRY['code']")
    server = replace(server, "'timezone': 'Africa/Lagos'", "'timezone': 'auto'")
    # HTTP header values must stay ASCII even when display names contain Unicode.
    server = replace(server, "'User-Agent': 'WeatherNigeria/1.0'", "'User-Agent': 'AfricAndroidWeather/1.0'")
    server = server.replace('Nigerian', name).replace('Nigeria', name)
    (destination / 'server.py').write_text(server)
    (destination / 'country.json').write_text(json.dumps(country, ensure_ascii=False))
    app = (source / 'static/app.js').read_text()
    start, end = app.index('const cities='), app.index('\nlet unit=')
    app = app[:start] + 'const country=' + json.dumps(country, ensure_ascii=False) + ';\nconst cities=country.cities;\nconst [south,north,west,east]=country.bounds;' + app[end:]
    app = replace(app, 'saved[1]>=4&&saved[1]<=14&&saved[2]>=2.5&&saved[2]<=15', 'saved[1]>=south&&saved[1]<=north&&saved[2]>=west&&saved[2]<=east')
    app = replace(app, 'lat<4||lat>14||lon<2.5||lon>15', 'lat<south||lat>north||lon<west||lon>east')
    app = replace(app, ".setView([9,8],6)", '.fitBounds([[south,west],[north,east]])')
    app = replace(app, "'en-NG'", "'en-' + country.code")
    app = replace(app, ' WAT · Model-based conditions', " ${data.timezone_abbreviation || data.timezone} · Model-based conditions")
    app = app.replace('Nigerian', name).replace('Nigeria', name)
    (destination / 'static/app.js').write_text(app)
    for page in (destination / 'static').glob('*.html'):
        text = page.read_text().replace('Nigerian', name).replace('Nigeria', name)
        text = text.replace('WAT · UTC+1', 'Location local time').replace('Lagos', country['cities'][0][0]).replace('NiMet', 'your national meteorological service')
        text = text.replace('From the coast to the savannah', 'Across ' + name)
        page.write_text(text)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('source'); p.add_argument('destination'); p.add_argument('country')
    args = p.parse_args()
    render(args.source, args.destination, json.loads(pathlib.Path(args.country).read_text()))
