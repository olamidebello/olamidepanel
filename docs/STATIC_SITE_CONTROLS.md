# Static-site module repairs

This release adds working controls for Redirects, Indexes, Error Pages, Hotlink Protection and IP Blocker. They control OlamidePanel's DNS-verified static sites. They do not configure arbitrary PHP/application hosts or the hosting panel itself.

## Use

Add a domain in Domains and request it in Site Publisher. Publish the required ownership TXT record and point the domain to the configured server. Open one of the five new tools, select your domain and save its settings. The database records the new revision and queues the existing root provisioning worker. The GUI distinguishes saved and applied revisions; a successful form submission is not proof that Nginx applied the configuration. Reload status after the worker runs.

- Redirects use exact paths and HTTPS targets with HTTP 301/302/307/308. Variable/configuration injection, reserved paths and direct redirect cycles are rejected.
- Indexes toggles Nginx directory listing only where no index document exists in the managed static document root.
- Error Pages creates escaped text documents for selected 400/401/403/404/500/502/503 responses. Direct access to those generated documents is denied.
- Hotlink Protection protects common image extensions while allowing direct requests, your hostname and explicitly allowed referring domains.
- IP Blocker applies up to 20 IPv4/IPv6 addresses or CIDR networks to the selected static host.

All writes require account ownership, a fresh revision, an authenticated session and CSRF protection. Read-only accounts cannot save. Generated Nginx directives never include unvalidated arbitrary configuration. The root worker rechecks DNS proof, reserves the panel hostname and validates/reloads Nginx. A failed Nginx check restores the previous generated configuration and error documents. The include is installed after the hidden-file protection rule so image matching cannot expose dotfiles. Existing Certbot-managed TLS blocks are retained.

The shared GUI API helper also now accepts JSON from successful 201/202 responses, fixing queued-action acknowledgments that previously became null in the browser.

## Deploy

After merging this release, use the existing playbook and your root-only variable file on the hosting server:

```bash
cd /opt/olamidepanel/repo
git pull --ff-only origin main
ansible-playbook -i /root/olamidepanel-private/local.ini ansible/deploy-available-modules.yml --ask-vault-pass -e @/root/olamidepanel-private/deploy-vault.yml
```

Use your actual private inventory/variable paths if they differ. The base playbook copies the new Python module, applies the additive `website_controls` table through application initialization and enables the existing DNS-verified provisioning timer. Do not copy placeholder credentials from the example variable file into production.

## Remaining scope

Other catalog entries still require implementations. This release does not claim mail hosting, authoritative DNS, customer database provisioning, shell/cron isolation, application runtimes, commercial integrations or every cPanel feature is operational. Their availability remains explicit in Module Readiness. A current application deployment is needed to replace an older generic “This module is not implemented” screen with the current tool-specific status view.
