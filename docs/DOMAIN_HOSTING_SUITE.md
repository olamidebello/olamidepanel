# Per-domain hosting suite automation

Run `ansible/deploy-domain-hosting-suite.yml` on an existing Debian 12 OlamidePanel
installation. This combines the existing static website request worker, recurring
per-domain Linux/SFTP provisioning and the new recurring email playbook. It does
not install proprietary cPanel or implement every feature in the tool catalog.

Update the installed panel application and `/opt/olamidepanel/repo` to the current
release first. This entrypoint intentionally does not run the bare-server bootstrap
against an existing production installation. Set values using
`ansible/domain-hosting-suite.example.yml`, copy outside Git and encrypt with
Ansible Vault. Review [email prerequisites](DOMAIN_EMAIL.md) and
[domain SSH policy](DOMAIN_SSH.md). Mail requires its own trusted certificate first.

```sh
ansible-playbook -i /secure/panel-inventory.ini \
  ansible/deploy-domain-hosting-suite.yml \
  -e @/secure/hosting-vault.yml --ask-vault-pass
```

Set `hosting_enable_email: false` to skip mail or `hosting_enable_domain_ssh: false`
to skip Linux domain accounts. Neither flag disables services installed previously.
The SSH owner policy defaults to disabled access; explicitly supply authorized
keys and access modes. Timers discover panel domains, but mailbox credentials
remain operator policy. Websites still require the existing domain-owner publish
request and DNS verification; the playbook does not overwrite unrelated live sites.

The final `/etc/olamidepanel/domain-feature-report.json` lists active domains,
the complete existing tool inventory and counts of implemented, partial and missing
tools. Implementation is distinct from service readiness, which is not verified by
this report. `hosting_require_complete: true` fails the final check when coverage
is incomplete; it does not implement missing features and is not a dry-run switch.
Earlier provisioning may already have applied before that check fails.

## Coverage

| Area | Delivered scope | Remaining work |
|---|---|---|
| Websites | Existing domain-owner static publish requests, TLS and controls worker | PHP/application hosting, tenant runtime isolation |
| Domain access | Recurring dedicated Linux identities and approved SSH/SFTP keys | Tenant terminal broker, FTP/WebDAV, filesystem quotas |
| Email | SMTP, TLS submission, IMAPS, virtual mailboxes, per-domain DKIM | Mailbox GUI, aliases, webmail, quotas, spam/virus filtering |
| Accounts and files | Existing panel API/GUI and account workspace operations | Full Linux hosting filesystem integration |
| Databases | Existing panel internal MySQL | Customer database/user lifecycle and management GUI |
| DNS | Existing read-only lookup and generated email DNS instructions | Authoritative DNS zones, DNSSEC and provider writes |
| Backups | Existing bounded workspace snapshots | Scheduled consistent database/mail/full-account restore |
| Security | Existing roles, TOTP and scoped account controls | WAF, malware scanning and tenant firewall workflows |
| Applications | Existing independent GitHub-site deployment adapters | General tenant Git/build/runtime/application installer |
| Reports and billing | Existing catalog, marketplace and payment adapters | Complete usage metering, recurring billing and resource enforcement |

The existing catalog is retained and does not mark unimplemented tools as working.
Exact cPanel parity requires substantial additional backend, tenant authorization,
GUI and service adapter implementation. A playbook can deploy those components
once implemented; package installation alone does not provide these workflows.
