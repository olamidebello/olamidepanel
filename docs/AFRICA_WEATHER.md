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

## Automatic repair and blank-email recovery

The repair entry point detects an email from explicit settings, Certbot's
`/etc/letsencrypt/cli.ini`, production ACME account registration, or the existing
panel deployment configuration `/etc/olamide-github-deploy.json`. It reads DNS
credentials only from explicit settings, `/etc/olamide-weather/provision.json`, or
`/etc/letsencrypt/cloudflare.ini`. It does not search arbitrary files for secrets.
Cloudflare zone discovery requires Zone Read permission; otherwise supply the zone
ID explicitly. Without a token it selects manual DNS and reports unresolved names
as incomplete rather than claiming they are hosted.

Run from the existing installer checkout:

```bash
git pull --ff-only origin main
ansible-playbook -i localhost, -c local ansible/repair-africa-weather.yml
```

If no valid existing email is available, provide it once:

```bash
ansible-playbook -i localhost, -c local ansible/repair-africa-weather.yml \
  -e tls_email=YOUR_REAL_EMAIL
```

For reusable settings, create `/etc/olamide-weather/provision.json` with root
ownership and mode `0600`, using `ansible/weather/provision.example.json` as its
schema. Replace every placeholder. Do not commit this file or put tokens in command
arguments. The repair playbook runs the complete existing provisioning sequence:
it restores edition files and services, regenerates managed nginx configuration,
repairs configured DNS, reuses/renews certificates and verifies real forecasts.
Failures remain visible individually in Hosting Domains. It is a manually invoked
repair run, not a background timer, and cannot resolve missing external credentials.

## Global nginx hash failure

Long country hostnames may exceed Debian nginx's default server-name hash bucket.
The provisioning playbook now repairs and validates global nginx configuration
once before the edition loop. It raises the bucket to at least 256 and the maximum
hash size to at least 8192; larger existing values are retained. It also moves only
byte-identical redundant files/aliases from `sites-enabled` into a timestamped
backup under `/var/backups/olamide-weather/nginx`. Distinct virtual hosts that claim
the same name remain untouched, with their warnings reported. Backups and moved
aliases are restored if `nginx -t` fails. No reload happens on a failed test.

For the reported `could not build server_names_hash` failure, stop any older
provisioning run first, pull the updated source, then run:

```bash
cd /opt/olamide-weather-deploy
git pull --ff-only origin main
ansible-playbook -i localhost, -c local ansible/repair-weather-nginx.yml
ansible-playbook -i localhost, -c local ansible/repair-africa-weather.yml
```

The first playbook requires no DNS credentials or certificate email. It validates
and starts/reloads nginx. The second retries country provisioning. Existing
backend processes may already be healthy despite the previous global nginx test
failures. Remaining duplicate-name warnings require comparison of the distinct
virtual hosts; they are separate from the fatal hash-size error.

## Hostnames do not resolve; DNS creation was skipped

`socket.gaierror: Name or service not known` during the manual DNS check means the
server resolver cannot resolve that name. A skipped authoritative DNS task means
Cloudflare automation was not selected. Creating nginx sites does not create public
DNS records. The updated playbook audits all selected manual DNS names before any
application rebuild and writes a BIND-format import file:
`/var/lib/olamidepanel/africa-weather-dns.zone`.

Generate the file without an application deployment or certificate email:

```bash
ansible-playbook -i localhost, -c local ansible/export-weather-dns.yml
```

This audit deliberately fails if any hostname is absent or points elsewhere; the
import file is still written. Import its A records into the authoritative DNS
provider for `africandroid.world`, resolve conflicting AAAA/CNAME records explicitly,
and wait for DNS propagation before rerunning repair. Importing a file is a DNS
provider operation; placing the file on the web server alone does not publish DNS.

For a Cloudflare-hosted authoritative zone, supply its DNS Edit token and zone ID
through the documented environment or root-only settings file and run the repair
playbook with `-e dns_provider=cloudflare`. Zone ID discovery also requires Zone Read
permission. No script can create authoritative records without access to the
provider managing the domain. Avoid fake local hosts-file entries: those do not
make public HTTPS validation work.
