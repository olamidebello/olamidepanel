# Domain marketplace and provider administration

Install on the existing MySQL-backed panel host:

```bash
cd /opt/olamidepanel/repo
git pull --ff-only
ansible-playbook -i localhost, -c local ansible/enable-domain-marketplaces.yml
```

Sign in again after restart. **Administration → API Providers & Keys** stores encrypted credentials with replacement, enable/disable, expiry and domain-assignment policies. Secrets are never returned to browsers. Preserve the vault `/var/lib/olamidepanel/api-provider-keys.json` and `/etc/olamidepanel/payment.key` together in secure backups. Application distribution and provider revocation are separate; storing an OpenAI key here does not configure hosted applications automatically.

Configure enabled operator-owned (`Store 0`) gateways in **Payment Gateways**. Stripe and Paystack are the existing implemented adapters; test/live and payment verification controls remain in place.

**Administration → Domain Marketplace Deployment** supports filtering, individual checkboxes, Select all visible domains, shared gateway selection, deploy/update, disable and per-domain job reports. Hidden selections remain selected; review the total selected count. Jobs are processed sequentially about every 30 seconds and recheck requester permissions and gateway availability.

Each domain needs an existing protected Nginx vhost with an exact server name and working HTTPS. The broker publishes `/marketplace` with the common operator catalog, while preserving the homepage. Buyers sign in and pay through the central panel. Domain-origin orders are bound server-side to assigned gateway IDs; merchant credentials are never copied into website files. Existing marketplace routes require operator review. Vhost backups and configuration-error rollback are included; HTTPS failures are reported as needs-attention.

This does not embed marketplaces inside unrelated application interfaces, import each app's product catalog, transfer balances or customer data, provision DNS, or enable live payments. Disabling a storefront blocks new checkouts; existing provider checkout sessions must be cancelled/expired at the provider if required.

Queue service: `olamide-domain-marketplaces.service`; timer: `olamide-domain-marketplaces.timer`. Inspect with `journalctl -u olamide-domain-marketplaces.service`. Stop processing with `systemctl disable --now olamide-domain-marketplaces.timer`. Vhost backups are under `/var/lib/olamide-domain-marketplaces/backups`.
