# OlamidePanel Debian 12 setup guide

This guide installs the current foundation. It does not turn all catalog cards into operational hosting services. Live MySQL/Ansible/Debian installation and browser checks have not been completed in the authoring workspace.

## 1. Prepare the server

Use a clean Debian 12 host, a sudo-capable SSH account, a hostname you control and off-server backups. Avoid installing on the existing SIP host without reviewing Nginx, ports, services and resource conflicts.

- Point the panel hostname's A record to this server. If publishing AAAA, ensure IPv6 works too.
- Allow incoming 80/443 for HTTP, HTTPS and certificate validation; retain your SSH access.
- Keep port 8090 on loopback and do not expose MySQL to the public Internet.
- Have a running Oracle MySQL 8 server, preferably the project's CI target 8.4 LTS. Install it using the official guide: https://dev.mysql.com/doc/mysql-apt-repo-quick-guide/en/
- Ansible configuration here provisions an existing MySQL server; it does not install Oracle's APT repository/server.

On the control machine, install Git, Python and ansible-core using your supported package manager. The server needs SSH/sudo and Python for Ansible. Do not put secrets into Git, command-line arguments or screenshots.

## 2. Obtain source and private variables

```sh
git clone https://github.com/olamidebello/olamidepanel.git
cd olamidepanel
mkdir -p "$HOME/olamidepanel-private"
chmod 700 "$HOME/olamidepanel-private"
cp ansible/inventory.example.ini "$HOME/olamidepanel-private/inventory.ini"
```

Edit the inventory with the actual server hostname and SSH user. Configure SSH keys using your usual secure process. The examples use placeholder hostnames and passwords, not working credentials.

Create `$HOME/olamidepanel-private/mysql-vault.yml` in an editor:

```yaml
panel_mysql_root_password: "YOUR_EXISTING_MYSQL_ROOT_PASSWORD"
panel_mysql_password: "YOUR_NEW_UNIQUE_APPLICATION_PASSWORD_20_PLUS_CHARACTERS"
```

Encrypt it immediately:

```sh
chmod 600 "$HOME/olamidepanel-private/mysql-vault.yml"
ansible-vault encrypt "$HOME/olamidepanel-private/mysql-vault.yml"
```

If MySQL root uses a socket authentication plugin instead of password authentication, adjust operator connection settings to your installation rather than changing root authentication blindly. The playbook defaults to root and `/var/run/mysqld/mysqld.sock`; override `panel_mysql_root_user` or `panel_mysql_socket` as needed.

## 3. Provision MySQL configuration

```sh
ansible-playbook -i "$HOME/olamidepanel-private/inventory.ini" \
  ansible/configure-mysql.yml --ask-vault-pass --ask-become-pass \
  -e @"$HOME/olamidepanel-private/mysql-vault.yml"
```

This creates:

- Database `olamidepanel` using utf8mb4.
- Application database account `olamidepanel@localhost` with privileges limited to this database.
- `/opt/olamidepanel/venv` and the pinned PyMySQL driver.
- Linux service user `olamidepanel`.
- `/etc/olamidepanel/database.json`, owned by root, group olamidepanel, mode 0640.

The playbook reconciles the application database password every time. Restart a running panel after password/configuration changes. Check mode does not verify SQL provisioning. The root database password is not stored in the application configuration.

For remote MySQL, provision the database and narrowly scoped account manually, copy `deploy/database.example.json` to the protected path, configure the correct host and `ssl_ca`, and verify certificate hostname matching. The local-MySQL playbook is not a remote-server provisioning tool.

## 4. Install the panel on the server

SSH to the server. Clone the repository there if the control-machine checkout is elsewhere:

```sh
git clone https://github.com/olamidebello/olamidepanel.git
cd olamidepanel
sudo bash deploy/install.sh panel.example.com
```

Replace `panel.example.com`. The installer checks Debian 12/configuration, installs Python/Nginx/Certbot, copies app files, installs dependencies, creates a dedicated Nginx vhost, starts systemd, requests HTTPS and prompts for the initial account password. The created username is `admin`, with the **panel root** role. Use a unique password of at least 14 characters.

The installer changes server packages/configuration and is intended for a fresh installation, not repeat updates. It refuses an existing enabled panel vhost. An interrupted installation may leave a partially configured service/vhost; diagnose and resume the failed step rather than deleting configurations or rerunning blindly.

## 5. Verify installation

```sh
sudo systemctl status olamidepanel --no-pager
sudo journalctl -u olamidepanel -n 80 --no-pager
sudo nginx -t
curl -I https://panel.example.com/
```

A HEAD request may return 501 because the current application implements GET/POST only; use a GET for the actual application check:

```sh
curl --fail --silent --show-error https://panel.example.com/ -o /dev/null
```

Open the HTTPS URL, sign in as admin, and verify file creation/editing, a domain inventory record, metrics and Access Control. Create a test lower-level user and verify isolation. Do not assume a live website, mailbox or DNS zone was provisioned from an inventory record.

If certificate issuance fails, correct DNS, IPv6 and port reachability, then run:

```sh
sudo certbot --nginx -d panel.example.com --redirect
sudo -u olamidepanel /opt/olamidepanel/venv/bin/python \
  /opt/olamidepanel/panel/server.py --create-admin admin
```

Create the account only if it does not already exist. Secure session cookies require HTTPS.

## 6. Register users with Ansible

Copy the sample account file to the private directory, replace all passwords and choose roles. Each entry accepts username, role, active and password; password is needed for a new account and unchanged for existing accounts.

```sh
cp ansible/accounts.example.yml "$HOME/olamidepanel-private/accounts-vault.yml"
# Edit with unique passwords before the following commands.
chmod 600 "$HOME/olamidepanel-private/accounts-vault.yml"
ansible-vault encrypt "$HOME/olamidepanel-private/accounts-vault.yml"
ansible-playbook -i "$HOME/olamidepanel-private/inventory.ini" \
  ansible/register-users.yml --ask-vault-pass --ask-become-pass \
  -e @"$HOME/olamidepanel-private/accounts-vault.yml"
```

The playbook requires the updated app installed on the target. Accounts are panel identities, not Linux or MySQL accounts. Existing passwords are preserved. Role/active changes invalidate prior sessions; the last active panel-root account is protected. Account reconciliation tasks skip in check mode. Root and super-admin peers can only be changed through trusted local provisioning, not the peer's management UI.

## 7. Upgrade an existing MySQL installation

1. Review the release diff and compatibility. Back up MySQL, account homes, credentials, Nginx configuration, certificates and the current app/service files.
2. Stop the panel: `sudo systemctl stop olamidepanel`.
3. Update the checkout with `git pull --ff-only`. If local changes or diverging history block this, inspect them; do not force-reset.
4. From that checkout, update the app and dependencies:

```sh
sudo cp -r panel /opt/olamidepanel/
sudo /opt/olamidepanel/venv/bin/pip install -r requirements.txt
sudo chown -R root:root /opt/olamidepanel
sudo install -m 644 deploy/olamidepanel.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start olamidepanel
```

5. Check logs and perform the verification steps. Schema creation is idempotent, but arbitrary future schema upgrades are not handled by a versioned migration framework.

## 8. Migrate from SQLite

Do not run the fresh installer/bootstrap first against the new MySQL target: the importer requires an empty database.

1. Stop the old service and back up its code, SQLite database and account homes.
2. Provision a separate empty MySQL target with the protected configuration.
3. Install the new application/dependencies and systemd unit using the upgrade steps, but leave the service stopped.
4. From the updated checkout run:

```sh
sudo -u olamidepanel /opt/olamidepanel/venv/bin/python \
  deploy/migrate_sqlite.py /var/lib/olamidepanel/panel.db
```

5. Start the service and verify old account passwords, roles, file ownership, domain records and audit entries.

The importer preserves IDs/hashes and leaves SQLite unchanged. Inserts are transactional; MySQL schema DDL is separate and may remain after an unsuccessful import. Keep original backups until live verification succeeds. A successful import cannot be repeated into the populated target.

## 9. Backup, restore and rollback

Back up **both MySQL and account files**, not just `/var/lib/olamidepanel`. Stop application writes for a consistent pair. Use your MySQL administrator's backup tooling, with protected option files or a password prompt rather than a plaintext password argument. Include schema, data and AUTO_INCREMENT state, plus `/etc/olamidepanel`, app/service versions, Nginx and certificate configuration. Encrypt and copy backups off-server; test restore on an isolated host.

To restore: stop the service, restore the matching database/files/app version and permissions, restore configuration, start the service and repeat sign-in/ownership checks. To roll back a SQLite migration, restore the old SQLite application/data together. Writes made to MySQL after cutover are not automatically copied back to SQLite.

## 10. Troubleshooting

| Problem | Check |
|---|---|
| Nginx 502 | systemd status/logs, MySQL configuration, backend loopback port |
| Permission denied on database config | root ownership, olamidepanel group, 0640 mode, readable parent directories |
| MySQL access denied | username/password, socket or host, account host matching and database-scoped grants |
| Remote TLS error | Correct CA path, server certificate and matching hostname |
| Missing pymysql | Install requirements using `/opt/olamidepanel/venv/bin/pip` |
| New service still points at system Python | Install updated systemd unit and daemon-reload |
| Cannot sign in over plain HTTP | HTTPS is required by Secure cookies |
| Import refuses target | Target must be empty; back it up and choose a new database rather than deleting data blindly |
| Existing username during bootstrap | Use the existing account or operator provisioning, not duplicate creation |
| Planned module does nothing | It has no service adapter yet; see the developer guide |

Current operation limits include memory-only sessions, a coarse login throttle behind Nginx, no total disk quotas, no public hosting-service provisioning, incomplete audit/error coverage and application-level file isolation. Track these before expanding production exposure.

## 11. Automatic bare-server installation

`ansible/deploy-bare-debian12.yml` installs dependencies and Oracle MySQL 8.4 from its signed Debian repository, provisions the application database, clones this repository, installs the runtime/service, creates a panel-root account and configures Nginx/Let's Encrypt. It targets Debian 12 amd64. It refuses an unrelated pre-existing MySQL data directory. It does not enable unfinished hosting modules.

For server `181.214.149.146`, the example hostname is `hosting.dobhrap.com`. Confirm its A record resolves to that IP and inbound 80/443 work before certificate issuance. The inventory is prefilled with that IP; it contains no password. Establish and verify SSH host trust separately before remote execution.

To run directly from an already-authenticated root SSH shell on the bare server:

```sh
apt-get update
apt-get install -y git ansible python3-venv
cd /root
git clone https://github.com/olamidebello/olamidepanel.git
cd /root/olamidepanel
install -d -m 700 /root/olamidepanel-private
install -m 600 ansible/bare-server.example.yml /root/olamidepanel-private/deploy-vault.yml
nano /root/olamidepanel-private/deploy-vault.yml
ansible-vault encrypt /root/olamidepanel-private/deploy-vault.yml
```

Then create the local inventory and start deployment (the playbooks require the `panel_servers` group):

```sh
printf '[panel_servers]\nlocalhost ansible_connection=local\n' > /root/olamidepanel-private/local.ini
ansible-playbook -i /root/olamidepanel-private/local.ini \
  ansible/deploy-bare-debian12.yml --ask-vault-pass \
  -e @/root/olamidepanel-private/deploy-vault.yml
```

Replace **every** placeholder password and the ACME contact email before encryption. The hostname is prefilled as hosting.dobhrap.com. The initial panel username is owner; it receives the root panel role. Do not commit the private directory. Existing account passwords are preserved on repeat runs. Account bootstrapping reconciles role/active status; keep bootstrap variables under trusted operator control.

From another control machine, use `ansible/bare-server.inventory.example.ini` (or a private copy), SSH key access and the same encrypted variables. Add `--ask-pass` for SSH password authentication if required; some control-machine Ansible versions also require sshpass. Add `--ask-become-pass` for a non-root SSH user needing sudo.

Reruns retain an already-issued Nginx TLS configuration and reconcile the application. Keep hostname stable: changing it after first deployment requires a deliberate vhost/certificate migration because the initial vhost is not overwritten. Set panel_revision to a reviewed commit for repeatability. This is not a zero-downtime upgrade/rollback system; take the database/files/app backups described above first.

An interrupted MySQL install before the managed marker is recorded may be refused on the next run. Inspect the partial install and verify ownership before operator recovery; never remove MySQL data to force a rerun. Repository-key expiration/signature failures must be resolved using current Oracle key information, not by disabling package signature checks. Certificate failure leaves the application installed but HTTPS readiness incomplete; correct DNS/reachability and rerun. Renewal runs through certbot.timer. The HTTPS verification validates the certificate and hostname against the local server.

This automation does not change SSH or firewall rules. Configure provider/host firewall reachability separately. Fresh-host check mode is not a deployment simulation: later tasks depend on files/packages that earlier check-mode tasks do not create.

### Automatic initial passwords and GUI password management

The bare-server playbook now generates missing, short or placeholder database/admin passwords automatically. You only need a valid hostname, real ACME email and panel administrator username. Explicit valid passwords remain supported. Generated values are persisted on the target at `/etc/olamidepanel/bootstrap-credentials.json`, owned by root with mode 0600, and reused on reruns; do not remove this file while using generated MySQL credentials. The sensitive tasks use no_log and separate effective variables so extra-vars placeholders cannot override generated values.

After successful deployment, retrieve only the initial panel login from the server root terminal:

```sh
python3 - <<'PY'
import json
with open('/etc/olamidepanel/bootstrap-credentials.json') as f:
    credentials=json.load(f)
print('Username:', credentials['panel_admin_username'])
print('Initial panel password:', credentials['panel_admin_password'])
PY
```

Do not share that output. Sign in and change your own password in Preferences → Password and Security. Use Administration → Access Control → Manage to assign/reset lower-level users' passwords. These GUI features manage panel accounts, not MySQL root or application database credentials. The bootstrap file retains the initial password; it does not track subsequent GUI password changes. Provisioning preserves existing panel passwords, so rerunning deployment does not reset a password changed in the GUI. Store the bootstrap file with encrypted backups and restrict host root access.

This supersedes earlier instructions requiring manual entry of all three passwords for a bare installation. Existing external MySQL installations still require their actual operator credentials; the standalone configure-mysql playbook does not generate unknown existing-server passwords.

## Deploy and verify the reviewed module batch

The module deployment now includes the optional DNS-verified static-site worker, account storage tools, bounded uploads/archives/images, file snapshots and TOTP. See `docs/MODULE_AUDIT.md` for all 176 GUI tools and explicit gaps, and `docs/FILES_AND_MFA.md` for usage and limits.

On the authenticated server root shell:

```sh
cd /root/olamidepanel &&
git pull --ff-only &&
ansible-playbook -i /root/olamidepanel-private/local.ini \
  ansible/deploy-available-modules.yml --ask-vault-pass \
  -e @/root/olamidepanel-private/deploy-vault.yml \
  -e panel_public_ipv4=181.214.149.146
```

This installs dependencies including Pillow, updates schema/code/service configuration, enables the static publisher timer, verifies HTTPS, runs non-production unit tests and prints the implementation inventory. It preserves credentials, data and existing certificates. Keep `/etc/olamidepanel/payment.key`: MFA and gateway credential decryption depend on it. A successful playbook does not certify planned modules or payment-provider integration.

After deployment, test login, upload/download, ZIP extraction and non-destructive snapshot recovery in a test account. Enroll MFA and save recovery codes before signing out. Test publisher ownership and DNS/TLS separately with a domain you control. Never point integration tests at the production panel database: the CI suite uses a disposable MySQL 8.4 database and creates test accounts.
