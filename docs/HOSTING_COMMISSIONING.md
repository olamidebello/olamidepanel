# Hosting commissioning

This entry point installs existing OlamidePanel components; it does not generate
missing application code or install licensed cPanel. Run it from a reviewed
checkout, as root, on Debian 12 amd64:

```sh
install -m 600 ansible/commission-hosting.example.yml /root/hosting-commission.yml
nano /root/hosting-commission.yml
ansible-playbook -i localhost, -c local ansible/commission-hosting.yml
```

Keep an existing configuration instead of copying the example over it. Override
its target-side path with `-e commission_config=/root/another-config.yml`.
Fresh hosts bootstrap the panel and MySQL; hosts with the existing panel database
configuration skip bootstrap. Existing gateways and keys are retained by their
component installers. Prerequisites are installed from configured repositories.
Panel DNS must point to the server and ACME must be reachable for fresh TLS setup.

The runner installs module management/repair, hosting domain GUI, shared
marketplace and AI controls, and domain watchdog. If `/root/all-domain-email.yml`
exists, it also runs bulk domain email commissioning. That file must contain the
reviewed operator/domain/DNS configuration. No mail configuration means a
`configuration_required` report entry; provider credentials are never invented.

A stage failure is recorded while subsequent independent stages are attempted.
The final assertion fails for any failed stage, invalid Nginx configuration or
failed local panel HTTP check. Review `/var/lib/olamidepanel-commission/report.json`
and root-only stage logs. A pass applies only to component installation and local
checks. It does not establish tenant isolation, external mail delivery, billing
settlement, public DNS readiness or complete cPanel feature parity. HTTP checks
use loopback; public HTTPS is validated by the fresh bootstrap, not by the final
local readiness check on existing installations.

The implementation inventory enumerates missing or partial features, including
customer databases, FTP/WebDAV, authoritative DNS, terminal/cron isolation,
complete mail/webmail, full backups, resource enforcement and licensed products.
These need implementation and integration testing. They cannot be commissioned
by installing packages alone. The report always sets exact_cpanel_parity=false.

Reruns reconcile components and replace commissioning logs/report. This is a
one-shot operator workflow; it does not schedule future source pulls. Individual
components install their documented service timers. Back up production data and
private encryption keys through your established backup workflow.

## Runtime profiles and detailed coverage

`install-hosting-prerequisites.yml` adds fixed Debian package profiles. Set
`hosting_prerequisite_profiles` in the private commissioning config to any of:
`web_runtime`, `file_tools`, `statistics`, `malware_scanner`, `postgresql`.
The commissioning example selects all five. Existing configs without this setting
select web runtime and file tools only. PHP extensions, Node/npm, Ruby/Perl,
rsync/archives, GoAccess/AWStats, ClamAV and PostgreSQL are prerequisites, not
finished hosting features. Apt service starts are suppressed during installation;
no PHP pools, database tenant accounts, scanners or analytics jobs are activated.
Existing running services are not stopped. Distribution package versions apply.

Run the prerequisite play directly on an existing machine with:

```sh
ansible-playbook -i localhost, -c local ansible/install-hosting-prerequisites.yml \
  -e @/root/hosting-commission.yml
```

Full commissioning also writes `/var/lib/olamidepanel-commission/features.json`,
containing the panel's per-tool implementation inventory, package presence and
commercial integration requirements. Its coverage is the existing panel catalog,
not every nested cPanel/WHM action. It does not test external integrations or
infer that a feature works because a package exists. Commercial product entries
require licensing, OS compatibility and a supported adapter; they are not
installed or purchased. cPanel public website links and sales buttons are not
server packages. This workflow does not reproduce those websites.

## Single-command automatic entry point

On the configured Debian 12 server, run:

```sh
ansible-pull -U https://github.com/olamidebello/olamidepanel.git \
  -C main -d /opt/olamidepanel-commission-bootstrap \
  -i localhost, -c local ansible/automatic-hosting.yml
```

Install `ansible-core git ca-certificates` with apt first if ansible-pull is absent.
The entry point creates missing `/root/hosting-commission.yml` using this
operator's domain, email and IP defaults, preserves an existing configuration,
and selects all five prerequisite profiles through a separate root-only file.
Existing `/root/all-domain-email.yml` is used when present. It does not fabricate
mail/DNS/payment credentials or implement missing tools. It runs once per command;
component service timers continue their established background work. Rerun the
command to apply later reviewed updates. Reports and private logs remain under
`/var/lib/olamidepanel-commission`. Use a reviewed commit instead of main for a
fixed source revision.
