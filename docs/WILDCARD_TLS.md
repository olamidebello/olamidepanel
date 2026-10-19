# Shared AfricAndroid wildcard TLS

This uses automated Cloudflare DNS-01 verification for africandroid.world and *.africandroid.world.
It requires an ACTIVE authoritative Cloudflare zone, not simply a domain registered at another registrar.
If your DNS is still hosted elsewhere, this playbook cannot validate it; do not run it until the appropriate provider is configured.
It does not change nameservers, A records, or existing certificates.

Create a Cloudflare token restricted to africandroid.world with Zone:DNS:Edit and Zone:Zone:Read.
Store the following in a private Ansible Vault file outside the repository:
```yaml
wildcard_zone_id: YOUR_ZONE_ID
wildcard_cloudflare_token: YOUR_SCOPED_TOKEN
```
Never paste tokens in chat or commit them. The installed credentials file is root-only and retained for renewal.

Run after the CA's retry time, from /root/olamidepanel:
```bash
git pull --ff-only
ansible-playbook -i localhost, -c local ansible/enable-africandroid-wildcard.yml --ask-vault-pass -e @/root/olamidepanel-private/wildcard-vault.yml
ansible-playbook -i localhost, -c local ansible/provision-africa-weather.yml -e dns_provider=manual -e tls_email=dobcalldemo@gmail.com
```

The first playbook installs isolated Certbot 5.8.0 and the matching Cloudflare plugin, issues one combined apex/wildcard certificate, and enables twice-daily renewal checks with randomized delay and nginx reload after renewal.
The second reuses that certificate for all country vhosts, including countries previously failing TLS. Existing per-country certificates and timers are retained.
The wildcard supports one-level subdomains, not names such as city.weathernigeria.africandroid.world.
Initial wildcard issuance still counts against the registered-domain rate limit. There is no automatic rapid retry. Respect the new retry time on any failure.
The apex is included in the certificate, but this does not rewrite the separate AfricAndroid apex nginx vhost.

Checks:
```bash
systemctl status olamide-wildcard-renew.timer --no-pager
/opt/olamide-certbot/bin/certbot renew --cert-name africandroid-world-wildcard --dry-run
nginx -t
```
A dry-run uses the staging CA. Normal renewal is automatic; it does not require keeping the shell environment token.
YAML and nginx template rendering were checked in the authoring environment; live DNS issuance and systemd execution require server validation.
