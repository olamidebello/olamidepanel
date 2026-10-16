# DNS-verified static website publishing

Domains previously stored inventory only. Site Publisher now stores title/tagline and a queued provisioning request in MySQL. A separately installed root timer verifies public DNS before creating a dedicated static Nginx site and requesting a certificate. It does not host PHP/Node applications, manage authoritative DNS zones, install a full website builder or upload arbitrary application files.

## Deploy on the hosting server

```sh
cd /root/olamidepanel
git pull --ff-only
ansible-playbook -i /root/olamidepanel-private/local.ini \
  ansible/enable-static-websites.yml --ask-vault-pass \
  -e @/root/olamidepanel-private/deploy-vault.yml \
  -e panel_public_ipv4=181.214.149.146
```

This imports normal panel deployment, installs dnspython, installs olamidepanel-websites.service/timer and writes root-only /etc/olamidepanel/provisioning.json. The website worker runs with OS root to manage its own Nginx files and Certbot, while the HTTP application stays unprivileged. The worker accepts only validated domain names, fixed generated paths and fixed command argument arrays. Restrict repository/deployment access because root executes that code. It processes at most five queued requests per pass; one pass can take several minutes due to certificate requests.

## Publish africandroid.world or another owned domain

1. Add the domain in Domains if it is not already listed.
2. Open Domains → Site Publisher. Enter the page title/tagline and request publishing.
3. Copy the returned token. At the authoritative DNS provider, add TXT `_olamidepanel.africandroid.world` with that exact value. Some providers expect the relative name `_olamidepanel` rather than the full name.
4. Point the domain's A record exclusively to `181.214.149.146`. Remove AAAA records for this IPv4-only publisher. Ports 80/443 must be publicly reachable. The worker does not change DNS at your registrar.
5. Request publishing once. The timer checks ownership and address, creates a static page and requests HTTPS. DNS failures enter `waiting_dns` and are retried automatically every minute, with at most five jobs per pass. Use Refresh publishing status to see progress; no resubmission is needed after correcting DNS. Server/Certbot failures still require operator attention and an explicit retry to avoid repeatedly requesting certificates.
6. Only a `published` status reports successful worker completion. Open the HTTPS link and verify it from outside the server.

Keep the TXT proof for subsequent page changes. The template escapes title/tagline as text; no arbitrary HTML, executable content or shell commands are accepted. www is a separate hostname and is not configured automatically. The panel's own hostname is reserved and cannot be replaced through Site Publisher.

## Files and lifecycle

The worker manages `/etc/nginx/sites-available/olamide-static-<domain_id>`, the matching sites-enabled link, root-owned `/var/www/olamidepanel-static/<domain_id>/index.html`, and a root-only manifest in `/var/lib/olamidepanel-provisioner`. These published pages are separate from File Manager storage. Do not edit the managed files manually if you expect updates through the GUI.

Deleting a domain or suspending/deleting its user removes the managed vhost on a later worker pass. Static files and certificates are retained for operator recovery; no automatic content erasure is promised. Restoring an account may require a new publishing request. The worker does not remove unrelated Nginx sites and refuses a domain already present in another enabled vhost. Existing Certbot-managed TLS configuration is retained on page updates.

## Troubleshooting

```sh
systemctl status olamidepanel-websites.timer --no-pager
journalctl -u olamidepanel-websites.service -n 80 --no-pager
nginx -t
```

If state is needs_attention, correct DNS/ownership or server configuration and submit again. Do not repeatedly retry certificate issuance before correcting DNS; CA rate limits can apply. A certificate failure can leave HTTP serving configured but HTTPS incomplete. Global timer failures before individual jobs are processed appear in service logs. DNS/provider certificate behavior and live Nginx provisioning have not been tested in the authoring workspace; syntax/unit tests do not substitute for server validation. Back up app/database, Nginx, managed page files, worker manifest and certificates before deployment.
