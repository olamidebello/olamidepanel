# Automatic all-domain repair

Run on the hosting server 154.16.170.86:

```sh
ansible-pull -U https://github.com/olamidebello/olamidepanel.git -C main \
 -d /opt/olamide-all-domain-repair -i localhost, -c local \
 ansible/repair-all-domains.yml
```

This coordinator continues the domain sweep even when the dedicated panel repair
fails. It discovers active panel domains, configured Nginx domains and explicit
approved mappings; starts inactive/failed nginx, panel and explicitly mapped
application services; restores the panel apex; applies supported verified root
proxy repairs; installs trusted certificates where DNS permits; enables the
Certbot renewal timer; and saves one combined report. It does not restart healthy
apps. A failed panel inventory export is reported and Nginx discovery still runs.
Invalid initial Nginx syntax stops edits and leaves a preflight log.

Combined report: `/var/lib/olamide-all-domain-repair/report.json`. Timestamped
private logs and reports remain in the same directory. Root-only per-domain
backups/certificate logs remain under the component workers' report directories.
This is a one-shot operator workflow, not an unattended code update schedule.

The repair uses `/etc/olamidepanel/domain-routing-approved.json` when present,
otherwise targets from the existing protected
`/var/lib/olamide-domain-ssl-repair/config.json`. The mapping must be a regular
root-owned file, mode 0600/0400, not a symlink. Format:

```json
{"targets":{"your-domain.example":{"port":18840,"health":"/health","contains":"unique-application-identity","service":"your-app.service"}}}
```

This is an illustrative mapping, not a valid deployment of that domain. Populate
actual approved domains, current listening ports, unique identity markers and
optional installed service names. The backend must return the marker before
routing changes. Unknown applications are never inferred from a guessed port or
a successful generic HTTP response. Separate API/marketplace locations remain
unchanged. Duplicate/conflicting vhosts beyond the known panel apex repair,
nonstandard root proxies, incorrect external DNS, closed provider ports, certificate
rate limits and missing backends remain reported for targeted repair.

`verified_repairs_complete` requires every stage to pass and all selected app
identities to be verified. `checks_passed_identity_review_required` means service/
HTTPS checks passed but some apps still need approved identity mappings. Both
that state and `incomplete` produce a nonzero exit, retaining successful work.
Do not treat HTTPS success alone as proof of correct application mapping.

No script can safely fix every unknown runtime, application or database issue.
This workflow does not modify DNS-provider records, reset credentials, restore
user data, rebuild heterogeneous applications or disable unrelated deployment
jobs. Backups/rollback protect supported Nginx edits. Correct an offending app's
saved deployment domain to prevent it from overwriting routing again.

## Subdomain coverage

The coordinator includes exact subdomains at any depth from panel and Nginx
inventory, approved mapping keys, protected hosted-domain/recovery/feature
snapshots, the six-domain deployment inventory and saved mail domain policy.
It reads names only; no saved credentials are written to reports. Unsafe,
symlinked, oversized or invalid saved inventory files are skipped and reported.
A selected parent via `repair_domains` includes that apex and all known children,
using DNS label boundaries (not a substring match). `repair_extra_domains` adds
explicit known names absent from those inventories, for example:

```sh
ansible-pull -U https://github.com/olamidebello/olamidepanel.git -C main \
 -d /opt/olamide-all-domain-repair -i localhost, -c local \
 ansible/repair-all-domains.yml \
 -e '{"repair_extra_domains":["postmaster.justisolve.com","vitabridge.olamidemedical.health"]}'
```

Adding a name does not invent its vhost, backend mapping or DNS records. SSL and
supported routing fixes use the same per-domain checks for apex and subdomains.
Wildcard Nginx names are listed separately with DNS-01 certificate review required;
no certificate is requested for a literal wildcard using HTTP validation. Wildcard
coverage does not enumerate arbitrary DNS names. Subdomains known only to an
external DNS provider must be supplied explicitly or imported into the inventory.

## Diagnose the remaining faults without new certificate requests

Add `-e repair_diagnostics_only=true` to the ansible-pull command. This mode does
not start inactive services, edit Nginx, invoke the panel repair, request/renew
certificates or enable timers. It still installs prerequisites/stages the tools,
reads configuration, performs DNS/HTTPS checks and writes private reports/logs.
Its zero exit means the diagnostic sweep ran; it does not mean every site works.
Existing application identity is checked only where approved mappings exist.

DNS results now include actual A/AAAA answers and expected IPv4. Per-command
failures include the failing phase, exit code and a bounded stderr detail, plus a
private failure log. curl exit 22 indicates an HTTP error (inspect its actual
status); exit 60 indicates certificate validation, and connection/timeouts have
their own codes. Reserved `.invalid`, `.test`, `.localhost`, `.example` names and
the explicit `mail.your-domain.com` placeholder are reported as excluded rather
than treated as certificate candidates. Their Nginx configuration is not deleted.
Review DNS answers rather than replacing records blindly; CDN proxy and intended
IPv6 configurations can also explain the strict IPv4 DNS prerequisite.

## Preserve split hosting and current DNS destinations

`repair-all-domains.yml` now defaults `repair_follow_current_dns=true`. Existing
DNS destinations stay authoritative: a weather name pointing at 181.214.149.146
is not treated as a migration candidate. Before any local domain edits, the
worker resolves A/AAAA. Names not exclusively pointing at the local IPv4 are
checked through their public HTTPS hostname, without `--resolve`, local vhost
edits or local Certbot issuance. A successful result is
`https_verified_on_current_dns_server`; that verifies HTTPS response/certificate,
not application identity. Remote failures are reported with their phase/details.
Actual mapping/certificate repairs on another server require running its own
approved repair process with access to that host. This script does not acquire
remote SSH access, copy databases or move services. No DNS records are changed.
The panel-apex repair is skipped locally if its DNS is on another destination.
Mixed A/AAAA or intentional IPv6 deployments are also check-only from this IPv4
repair host. Domains without any address remain unresolved. For the old strict
local-only policy, explicitly set `repair_follow_current_dns=false`.
