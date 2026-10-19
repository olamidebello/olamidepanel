# Africa Weather hub

The hub lists all 55 requested destinations, including Nigeria and Western Sahara. Each card shows the named city's model temperature, timestamp, and timezone. Previews use a bounded, cached same-origin gateway; unavailable editions remain linked with an honest unavailable message. It does not provision country applications by itself.

On the hosting server, from the latest olamidepanel checkout:

```bash
export WEATHER_TLS_EMAIL='your-certificate-email'
export NAMECHEAP_API_USER='your-api-user'
export NAMECHEAP_USERNAME="$NAMECHEAP_API_USER"
export NAMECHEAP_CLIENT_IP='your-allowlisted-server-public-ip'
read -rs -p 'Namecheap API key: ' NAMECHEAP_API_KEY
export NAMECHEAP_API_KEY
ansible-playbook -i localhost, -c local ansible/provision-africaweather-hub.yml
```

Requires Namecheap API access, allowlisted outgoing IPv4, and Namecheap authoritative DNS. Credentials are passed on stdin and Ansible hides the DNS task output. Existing records are read and preserved; conflicting records, CAA and DynamicDNS configurations fail closed. Namecheap's whole-zone replacement cannot guarantee protection from an unrelated simultaneous DNS writer; avoid concurrent DNS edits. No nameserver migration is performed. Set `-e provision_namecheap=false` if DNS is already configured elsewhere. DNS includes the hub and all 55 country names, with `181.214.149.146` as the default target; override `dns_ipv4` if needed.

Country hosting remains the existing `ansible/provision-africa-weather.yml`, now supporting `-e dns_provider=namecheap`. Nigeria's independent installation is not moved. The hub installer adds app links to country editions under `/opt/olamide-weather/<slug>/static`. For a separately installed Nigeria site, run `NIGERIA_STATIC_ROOT=/actual/static/path python3 /opt/africaweather/install_links.py`. Existing country services need no restart for static changes. Future editions receive links from the renderer.

The shared Africa Weather Android development app opens the hub and allows navigating to country editions. GitHub Actions builds and signature-checks the APK when mobile source is pushed to main, and publishes `AfricaWeather.apk` with SHA-256. Every download section resolves an actual release asset before enabling the APK link. This is a debug-signed development download; it is not a Play Store release. Android 6+ and internet are required.

The hub playbook verifies HTTPS pages and then exports its status into Olamidepanel Hosting Domains. It does not mark country DNS or hosting as verified merely because a link exists. Terms, privacy and copyright reflect the implemented directory behavior; update the privacy notice when tracking or advertising is introduced. Verify hosting log retention and the operator's public contact route before launch. Weather provider commercial licensing must match actual usage; country services currently inherit the existing provider configuration.

## Forecast landing page and preferred country

The directory now displays current conditions, highs/lows, rain probability and wind for each featured city, with a seven-day forecast dialog. All 55 unique destinations have country-edition links. Celsius/Fahrenheit, search, retry and refresh controls are included. The gateway prefers country-edition data and falls back to Open-Meteo for the same city when an edition is unavailable. Responses are cached for ten minutes and upstream concurrency is bounded. Provider usage/licensing must match deployment requirements.

The page and download page both include a preferred-country selector saved in browser local storage. The chosen card moves first on the landing page. Clearing the selector removes the stored preference. The download button is enabled only when GitHub returns a published AfricaWeather.apk release asset; SHA-256 is linked when present. Browser preference is not transferred to a newly installed app. The Android app has a native country selector populated from the same 55-country catalog and saves the chosen country locally. New mobile-source pushes trigger the existing Android build workflow. Until a new build succeeds, downloads can still point to an earlier published APK.

Update an already provisioned hub on the hosting server:

```bash
cd /opt/olamidepanel-source
git pull --ff-only origin main
ansible-playbook -i localhost, -c local ansible/update-africaweather-landing.yml
```

The update playbook backs up changed files, restarts the hub when needed, and verifies the health endpoint and public HTTPS page. It does not change DNS or certificates. First-time installation continues to use `provision-africaweather-hub.yml`. Frontend validation includes download/preference checks via `node tests/test_weather_download.cjs`; backend forecast tests use `python3 -m unittest discover -s tests -p test_africaweather_landing.py`.
