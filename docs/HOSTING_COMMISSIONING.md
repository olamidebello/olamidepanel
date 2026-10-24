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
