# Wrong application at olamidepanel.com

If olamidepanel.com shows Africa Media Hub or another application, run on the
hosting server 154.16.170.86:

```sh
ansible-pull -U https://github.com/olamidebello/olamidepanel.git -C main \
 -d /opt/olamide-hosting-repair -i localhost, -c local \
 ansible/hard-repair-hosting.yml
```

This entry point first runs `restore-panel-domain.yml`, then the existing
`repair-domain-routing-ssl.yml` sweep. It handles the known apex mismatch and SSL
fault, not every possible application/runtime/database issue.

The targeted repair requires a working installed OlamidePanel on loopback port
8090, confirmed by its HTML login identity. It removes the exact apex name from
conflicting Nginx server_name directives and removes server blocks that name only
that apex. Blocks also naming a media or other domain retain those names and their
routes. It creates a dedicated apex gateway to port 8090, validates and reloads
Nginx, then checks the returned application. Failed gateway changes roll back.
Only the apex is reclaimed; www and subdomains retain their existing configuration.
A media deployment with no proper media domain still needs its own vhost/DNS.

A root-only timestamped backup directory and manifest are created under
`/var/lib/olamidepanel-domain-repair`. It checks that the apex A points exclusively
to 154.16.170.86 with no AAAA, requests and installs the Let's Encrypt certificate,
and verifies the HTTPS hostname and OlamidePanel login through the local gateway.
Existing valid apex certificates can be used before issuance. If routing succeeds
but DNS or issuance fails, restored routing remains and the command fails with a
status report instead of falsely claiming SSL success. HTTP ACME requires public
port 80. Certificate authorities can impose rate limits; read the log before
rerunning.

Targeted report: `/var/lib/olamidepanel-domain-repair/report.json`.
Remaining-domain report: `/var/lib/olamide-domain-ssl-repair/report.json`.
The second phase runs only after the panel repair succeeds. It discovers active
panel and existing Nginx domains; ambiguous duplicates require reviewed mappings.
See DOMAIN_ROUTING_SSL_REPAIR.md to supply confirmed target ports/identity markers.
No arbitrary app port guessing or application code rebuild is performed. No
external DNS, databases, secrets, media assets or user accounts are reset.

This repair requires a syntactically valid initial Nginx configuration. If nginx
-T fails, it reports the failure before editing. Missing panel backend, missing
certificate files in existing vhosts, complex server_name includes and custom
infrastructure may require a specific repair after inspecting their actual error.
Other automated deployers can overwrite Nginx again: fix their domain inputs,
particularly any media installer configured with olamidepanel.com. The repair
does not disable unrelated timers or modify their deployment policies.
