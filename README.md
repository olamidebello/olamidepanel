# OlamidePanel

Independent Debian 12 hosting-panel foundation, inspired by the hosting-user and server-admin workflows in the supplied cPanel/WHM inventory. This is **not cPanel**, is not affiliated with cPanel, and does not reproduce its proprietary implementation or licensed add-ons. **Not production-ready or a complete cPanel replacement.**

## What works

* Admin and hosting-user sign-in, scrypt password hashes, one-hour sessions, CSRF checks, login throttling, secure cookies.
* Account-scoped file listing, reading, writing, folder creation, and API file deletion. Files are limited to 1 MiB per write; no total storage quotas yet.
* Domain inventory with validation and ownership filtering. **Does not provision DNS, websites, mail or certificates.**
* Server disk/load/hostname metrics, admin audit viewer and panel-user creation.
* Responsive searchable tool catalog covering all requested feature groups. Unimplemented modules are explicitly marked; no simulated success messages.
* Nginx reverse proxy, Let's Encrypt setup, hardened unprivileged systemd service.

## Debian 12 installation

Use a **separate clean Debian 12 server** with root access and a hostname whose A/AAAA records point to it. Ports 80 and 443 must be reachable for certificate issuance. Do not install on your existing SIP server without reviewing conflicts and backups.

```sh
git clone https://github.com/olamidebello/olamidepanel.git
cd olamidepanel
sudo bash deploy/install.sh panel.example.com
```

The installer installs packages, adds a service user, copies the app to `/opt/olamidepanel`, configures a dedicated Nginx vhost, requests a certificate and prompts for the initial admin password (14+ characters). No default password is shipped. If certificate issuance fails, fix DNS/reachability, rerun `certbot --nginx -d panel.example.com --redirect`, then run the admin creation command below. Secure session cookies deliberately require HTTPS.

```sh
sudo -u olamidepanel python3 /opt/olamidepanel/panel/server.py --create-admin admin
```

## Local development

```sh
export PANEL_DATA="$PWD/.local-data"
export PANEL_SECURE_COOKIE=0
python3 panel/server.py --create-admin admin
python3 panel/server.py
```

Open http://127.0.0.1:8090. Never disable secure cookies on an exposed installation.

## Updates and backups

Back up `/var/lib/olamidepanel` with the service stopped, plus the Nginx configuration and certificates, to encrypted off-server storage. To update: review the diff, stop the service, back up, copy the new `panel` directory into `/opt/olamidepanel`, keep root ownership, and restart. Sessions are in memory and expire on restart. Roll back app and data together if schemas change.

## Remaining implementation

The UI catalog represents requested navigation, **not implemented service functionality**. Mail, DNS, virtual hosts, TLS management, SQL databases, FTP/WebDAV, Git deployments, backup restoration, cron, terminal, firewall, MFA, API tokens, package/reseller management, migrations, resource isolation, WordPress, billing and third-party products need implementation and integration tests. Legacy/vendor-specific names are references, not included software.

Before production: implement per-account OS isolation and quotas, a narrowly authorized privileged job agent, durable jobs and sessions, MFA/recovery, complete audit records, backup recovery testing, concurrency/load validation and independent security review. Do not run the web process as root or add unrestricted sudo access. Current file isolation is application-level only; this is not a multi-tenant OS security boundary. SQLite and the standard-library HTTP server are suitable for this foundation, not a high-volume production deployment.

## Validation

`python3 -m unittest discover -s tests -v`
