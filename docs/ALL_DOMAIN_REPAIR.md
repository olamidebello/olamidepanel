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
