# OlamidePanel

Independent Debian 12 hosting-panel foundation, inspired by the hosting-user and server-admin workflows in the supplied cPanel/WHM inventory. This is **not cPanel**, is not affiliated with cPanel, and does not reproduce its proprietary implementation or licensed add-ons. **Not production-ready or a complete cPanel replacement.**

## Documentation

- [User manual](docs/USER_MANUAL.md): dashboard, file/domain tasks, account preferences and super-admin controls.
- [Setup guide](docs/SETUP_GUIDE.md): Debian 12, MySQL, HTTPS, Ansible registration, migration, upgrades and recovery.
- [Developer guide](docs/DEVELOPER_GUIDE.md): architecture, schema, permissions, API routes and testing.

## What works

* Admin and hosting-user sign-in, scrypt password hashes, one-hour sessions, CSRF checks, login throttling, secure cookies.
* Account-scoped file listing, reading, writing, folder creation, and API file deletion. Files are limited to 1 MiB per write; no total storage quotas yet.
* Domain inventory with validation and ownership filtering. **Does not provision DNS, websites, mail or certificates.**
* Server disk/load/hostname metrics, admin audit viewer and panel-user creation.
* Responsive searchable tool catalog covering all requested feature groups. Unimplemented modules are explicitly marked; no simulated success messages.
* Nginx reverse proxy, Let's Encrypt setup, hardened unprivileged systemd service.

## Automated bare Debian 12 deployment

Use [the bare-server setup instructions](docs/SETUP_GUIDE.md#11-automatic-bare-server-installation) and `ansible/deploy-bare-debian12.yml` for a fresh Debian 12 amd64 server. It installs Oracle MySQL, Python dependencies, Git, Nginx and HTTPS, then deploys the application and bootstrap panel-root account. Example inventory targets `181.214.149.146`; example hostname is `hosting.dobhrap.com`. Encrypted variables are required for database/admin passwords. This automation has not yet been executed on the live server.

## MySQL setup (required before installation)

The runtime uses **MySQL 8.0+ / 8.4 LTS**, not SQLite. Install Oracle MySQL using its official Debian APT repository or connect to an existing MySQL server. This project does not install MariaDB as a substitute or alter your server's APT repositories. Official guide: https://dev.mysql.com/doc/mysql-apt-repo-quick-guide/en/

Install `ansible-core` on your control machine, configure the inventory, and store `panel_mysql_root_password` and `panel_mysql_password` (20+ characters) in an Ansible Vault encrypted file outside the repository. Then run:

```sh
ansible-playbook -i /secure/path/panel-inventory.ini ansible/configure-mysql.yml \
  --ask-vault-pass --ask-become-pass -e @/secure/path/mysql-vault.yml
```

This playbook requires a running local MySQL server. It creates the application database, a dedicated database user scoped to `olamidepanel.*`, a Python virtual environment, and `/etc/olamidepanel/database.json` readable only by root and the panel service group. It reconciles the database password on each run; it reports changed because provisioning SQL is executed. Restart the panel after changing credentials. Application accounts and MySQL login accounts are separate.

For an existing remote MySQL server, create the database/user with the equivalent schema-scoped grants, and use `deploy/database.example.json` as the protected configuration template. Set `ssl_ca` to a trusted CA file for remote connections; certificate and hostname verification are required. `PANEL_DB_CONFIG` overrides the configuration path. Do not commit database credentials. The application database user needs SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX and REFERENCES on this database only. No global MySQL privileges or database root credentials are used by the web service.

## Debian 12 installation

Use a **separate clean Debian 12 server** with root access and a hostname whose A/AAAA records point to it. Ports 80 and 443 must be reachable for certificate issuance. Do not install on your existing SIP server without reviewing conflicts and backups.

```sh
git clone https://github.com/olamidebello/olamidepanel.git
cd olamidepanel
sudo bash deploy/install.sh panel.example.com
```

The installer installs packages, adds a service user, copies the app to `/opt/olamidepanel`, configures a dedicated Nginx vhost, requests a certificate and prompts for the initial admin password (14+ characters). No default password is shipped. If certificate issuance fails, fix DNS/reachability, rerun `certbot --nginx -d panel.example.com --redirect`, then run the admin creation command below. Secure session cookies deliberately require HTTPS.

```sh
sudo -u olamidepanel /opt/olamidepanel/venv/bin/python /opt/olamidepanel/panel/server.py --create-admin admin
```

## Local development

```sh
export PANEL_DATA="$PWD/.local-data"
export PANEL_SECURE_COOKIE=0
/opt/olamidepanel/venv/bin/python panel/server.py --create-admin admin
/opt/olamidepanel/venv/bin/python panel/server.py
```

Open http://127.0.0.1:8090. Never disable secure cookies on an exposed installation.

## Updates and backups

Back up the MySQL database and `/var/lib/olamidepanel` with the service stopped, plus protected database configuration, Nginx configuration and certificates, to encrypted off-server storage. To update: review the diff, stop the service, back up, copy the new `panel` directory into `/opt/olamidepanel`, keep root ownership, and restart. Sessions are in memory and expire on restart. Roll back app and data together if schemas change.

## Remaining implementation

The UI catalog represents requested navigation, **not implemented service functionality**. Mail, DNS, virtual hosts, TLS management, SQL databases, FTP/WebDAV, Git deployments, backup restoration, cron, terminal, firewall, MFA, API tokens, package/reseller management, migrations, resource isolation, WordPress, billing and third-party products need implementation and integration tests. Legacy/vendor-specific names are references, not included software.

Before production: implement per-account OS isolation and quotas, a narrowly authorized privileged job agent, durable jobs and sessions, MFA/recovery, complete audit records, backup recovery testing, concurrency/load validation and independent security review. Do not run the web process as root or add unrestricted sudo access. Current file isolation is application-level only; this is not a multi-tenant OS security boundary. The standard-library HTTP server still needs replacement and load validation before a high-volume production deployment.

## Validation

`python3 -m unittest discover -s tests -v`

## Workspace interface

The responsive dashboard includes light/dark appearance, browser-persisted favorites, availability filters, tool counts, category navigation, keyboard search (`/`), a workspace guide, quick file/domain/metrics access and accessible status messages. Theme and favorites are browser preferences, not server-side account settings. Planned tool cards describe their implementation status; they do not provision services.

## Super-admin access control and Ansible registration

Open **Administration → Access Control** as panel root or super admin. Search accounts, assign strictly lower roles, suspend/restore accounts, register new accounts, and inspect each role's permission list. Role changes and suspension from the GUI invalidate that account's sessions. Privilege checks run on the backend, and each request rechecks the stored role and active flag. You cannot alter your own access or a peer/higher account in the GUI. Root can create additional panel-root accounts; only local provisioning can change an existing root account, and it preserves the last active root.

| Role | Level | Implemented permissions |
|---|---:|---|
| root | 100 | Account management, audit read, own files/domains, metrics |
| super_admin | 90 | Account management below own level, audit read, own files/domains, metrics |
| admin | 70 | Own files/domains, metrics |
| reseller | 50 | Own files/domains, metrics |
| user | 20 | Own files/domains, metrics |
| readonly | 10 | Own files/domain inventory read, metrics read |

Admin/reseller levels establish the hierarchy; server management and reseller-owned customer delegation remain unimplemented. Panel root does not grant Linux root, SSH, sudo, terminal access or cross-account filesystem access. Existing `admin` accounts are not automatically elevated. New `--create-admin` bootstrap accounts use the panel `root` role. To elevate a legacy account, explicitly provision its username with `role: root` locally through the playbook.

On an Ansible control machine with `ansible-core` installed, copy the sample inventory and accounts variables **outside the checkout**, replace the hostname and passwords, and encrypt the variables:

```sh
cp ansible/inventory.example.ini /secure/path/panel-inventory.ini
cp ansible/accounts.example.yml /secure/path/panel-accounts.yml
# Edit both files before encrypting; use unique passwords of at least 14 characters.
ansible-vault encrypt /secure/path/panel-accounts.yml
ansible-playbook -i /secure/path/panel-inventory.ini ansible/register-users.yml \
  --ask-vault-pass --ask-become-pass -e @/secure/path/panel-accounts.yml
```

The playbook requires the updated application installed at `/opt/olamidepanel`, a service user named `olamidepanel`, and Debian 12. It sends account data to the local CLI through stdin with `no_log: true`; it never opens public self-registration. Repeated runs preserve passwords and report unchanged when role/active status match. Password rotation is not implemented. Account tasks skip in check mode. No Ansible execution on a Debian host or browser verification has been performed in this workspace; YAML parsing, backend integration tests and JS syntax checks were performed.

## Connected account and file operations

Access Control → Manage opens account contact editing, password reset, session revocation and suspended-account deletion. Deletion requires the exact username, removes the account and its domain inventory, and retains its account files for operator-managed recovery. Monotonic account IDs prevent retained storage from being reassigned to another account. Session versions in MySQL invalidate access after role/password changes and revocation, including changes made through local provisioning.

Preferences → Contact Information and Password and Security are connected to the profile API. Password changes require the current password and invalidate existing sessions. File Manager includes rename, copy, and confirmed file/empty-folder deletion. Domains includes removal of inventory records. All mutations use CSRF validation and ownership/role checks. The MySQL schema includes email, display-name and session-version fields; back up data before updating.

The larger cPanel checklist remains incomplete: production website/DNS/mail/database provisioning, backups, scheduled jobs, terminal, TLS automation controls and licensed integrations are still planned. No live server deployment or browser QA is claimed.

## Migrate an existing SQLite installation

1. Stop `olamidepanel` and back up `/var/lib/olamidepanel`, the old app, and the target MySQL database.
2. Provision a new **empty** MySQL database and its configuration. Install `requirements.txt` into the runtime virtual environment and update the service/app files.
3. Before creating any account in MySQL, run the importer from the checkout:

```sh
sudo -u olamidepanel /opt/olamidepanel/venv/bin/python deploy/migrate_sqlite.py /var/lib/olamidepanel/panel.db
```

4. Start the service and verify account sign-in, roles, files and domain inventory. The importer keeps account IDs, password hashes, session versions and audit entries. Account files stay in their existing homes. It never modifies the SQLite source and refuses a populated target. Row inserts are transactional; schema creation uses MySQL DDL and is separate from the import transaction. Do not rerun after a successful import.
5. Keep the SQLite backup until verification succeeds. For rollback, stop the service and restore the old application and SQLite data together; writes made after switching to MySQL will not be reflected in that old backup.

## MySQL verification

Two local adapter unit tests cover parameter binding and transaction commit/rollback. Application integration tests require `PANEL_TEST_MYSQL=1` and `PANEL_DB_CONFIG` pointing to a **disposable, empty MySQL database**. They create test accounts and must never target production. GitHub Actions runs these tests with a MySQL 8.4 service. A skipped integration class is not evidence that MySQL integration passed. Live MySQL migration, Debian installation and browser QA remain unverified in the authoring workspace.

## Terms, privacy and copyright

Public Terms and Conditions, Privacy Notice and Copyright pages are linked in the login/footer. Sign-in requires terms agreement and privacy acknowledgment; the backend records the current version and latest acceptance timestamp in MySQL. Read [operator legal review notes](docs/LEGAL_REVIEW.md) before public/commercial use. These drafts describe the current foundation and need operator-specific legal review.

## Hosting marketplace

[Marketplace guide](docs/MARKETPLACE_GUIDE.md): customer/operator dashboards, editable plan catalog, illustrative Starter/Business/Growth templates, published-plan search, confirmed order requests, status tracking, manual approval/rejection and pending cancellation. Plans and orders are stored in MySQL with role/ownership checks, price snapshots and retry idempotency. Payments, customer hosting provisioning, resource enforcement, billing and renewals are not implemented.

Reseller storefronts are supported through super-admin publishing approval, seller-owned catalog editing, seller-scoped order review and hosting/reseller plan categories. See the marketplace guide for sample reseller templates and exact authorization boundaries. These controls do not grant hosting-service provisioning, payment processing or reseller Linux-account delegation.

## Payments and module deployment

[Payments guide](docs/PAYMENTS_GUIDE.md) covers encrypted store-owned gateway administration, Stripe/Paystack hosted checkout adapters, verified payment tracking and manual reconciliation. Other providers are labeled unimplemented; live payment collection defaults off until operator testing and explicit deployment enablement. No refunds/subscription/payout or hosting-provisioning automation is claimed.

`ansible/deploy-available-modules.yml` installs implemented code/prerequisites, runs local tests and reports remaining gaps. Administration → Module Readiness shows the same implementation inventory. It does not manufacture code for absent modules or claim that all cPanel functions are complete.

## Static domain publishing

[Static websites guide](docs/STATIC_WEBSITES.md) describes the DNS-verified title/tagline publisher and separate Nginx/Certbot worker. Install it with `ansible/enable-static-websites.yml`. Domain inventory alone still does not publish a site; ownership TXT proof and a publishing request are required. Authoritative DNS, application hosting, website file uploads and a full builder remain unfinished.
