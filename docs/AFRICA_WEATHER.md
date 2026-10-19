# Provision the 54 requested African weather editions

`ansible/provision-africa-weather.yml` provisions exactly the 54 domains in
`ansible/weather/countries.json`. Nigeria's existing site is not modified.
Each edition clones the complete WeatherNigeria source at the tested commit,
retains current conditions, 24-hour and seven-day forecasts, country city search,
geolocation, temperature units, map layers, retry controls and all three legal pages.
Country editions use country-specific branding, two initial cities, approximate
regional bounding boxes, map extents and country codes. Search adds other towns.
Forecasts use each location's timezone automatically. Bounding boxes are approximate
coverage limits, not political borders; country searches follow the geocoding
provider's country classifications, including its Western Sahara records.

## Run on the Olamidepanel hosting server

Pull this repository into the existing panel source checkout, install Ansible if
necessary (`apt-get install ansible`), then run from that checkout as root:

```bash
export WEATHER_TLS_EMAIL='your-real-certificate-contact@example.com'
export CLOUDFLARE_ZONE_ID='your-africandroid-world-zone-id'
read -rsp 'Cloudflare DNS Edit token: ' CLOUDFLARE_API_TOKEN
export CLOUDFLARE_API_TOKEN
ansible-playbook -i localhost, -c local ansible/provision-africa-weather.yml
```

The Cloudflare token must have DNS Edit access to the authoritative
`africandroid.world` zone. Credentials are read from the controller environment;
DNS task output is redacted. If DNS is hosted elsewhere, create all hostname A
records pointing to `181.214.149.146` (or your actual hosting IP), remove conflicting
AAAA/CNAME records, and pass `-e dns_provider=manual`. Manual mode verifies DNS; it
does not create records. Other providers need a DNS adapter before automatic DNS
creation is available. Do not supply secret tokens as command-line arguments.

To use a different server IP pass `-e dns_ipv4=YOUR_IP`. Both public HTTP port 80
and HTTPS port 443 must reach nginx. Run a small batch first if desired:

```bash
ansible-playbook -i localhost, -c local ansible/provision-africa-weather.yml \
  -e '{"weather_only":["ghana","kenya"]}'
```

Omit `weather_only` for all 54. Each domain gets a dedicated systemd service,
loopback port in the stable range 19000–19053, a root-owned application directory
under `/opt/olamide-weather`, nginx hosting, a hostname-specific Let's Encrypt
certificate and certificate renewal. Reserve that port range; do not change the
port base after deploying without planning the migration. Existing certificates
are preserved during reruns. Services are refreshed on each run.

Failures are recorded and the next country is attempted. The final play fails if
any selected edition is incomplete. Rerun failed slugs after correcting DNS,
provider or certificate errors. Large batches may encounter certificate issuance
limits; successful editions are retained and certificates are reused.

The existing super-admin **Hosting Domains** view reads the merged status snapshot:
`https_ready` is reported only after trusted public HTTPS health and a real forecast
have succeeded. The other hosted domains' snapshot entries are preserved. This is
operator inventory; it does not create customer ownership or publishing rights.
No panel restart or new database schema is needed. This playbook requires an
installed Olamidepanel with its `olamidepanel` group and Hosting Domains GUI.

The renderer deliberately fails if its expected source structure changes. To update
WeatherNigeria, review the renderer, change the pinned ref in both the playbook and
CI workflow, then rerun edition tests. Legal page branding is customized; source
repository support links and third-party attribution remain intact.

## Validation

```bash
ansible-playbook -i localhost, ansible/provision-africa-weather.yml --syntax-check
WEATHER_TEST_SOURCE=/path/to/pinned/weathernigeria \
  python -m unittest discover -s tests -p test_weather_editions.py -v
```

CI checks all 54 generated JavaScript editions, country-scoped search behavior,
coordinate acceptance/rejection and preservation of the existing UI features.
Live provisioning additionally verifies actual DNS, backend startup, certificates
and upstream forecast responses. Syntax and local tests alone do not mean that
public domains are deployed.
