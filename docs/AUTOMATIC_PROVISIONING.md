# Automatic activation after confirmed payment

New paid hosting and reseller orders are immediately ready for checkout. Existing pending orders still need their original approval. Free orders retain manual review and do not trigger payment activation.

The existing Stripe and Paystack adapters independently verify payment with the provider, including identity/reference, exact amount, currency and live/test mode. Signed webhooks, the Verify action and operator reconciliation all use the same verifier. In the transaction recording a verified LIVE payment, a unique job is inserted for the order. Browser redirects and TEST payments never grant services.

The unprivileged `olamidepanel-fulfillment.timer` runs every minute. It recovers verified paid orders without jobs, locks a ready job with MySQL `FOR UPDATE SKIP LOCKED`, rechecks payment/order/customer/seller eligibility, creates the customer's panel storage directory and inserts exactly one service allocation using the purchased plan snapshot. Checkout requires an existing panel login, so activation preserves that login and password. It does not create another credential or Linux login. Queue, service allocation and reseller privilege changes commit atomically; interrupted filesystem creation is harmless on retry.

Supported adapters:

| Purchase | Automatic activation |
| --- | --- |
| Hosting | Existing buyer's panel storage directory, purchased disk allowance, website/domain allocation and 30-day service record |
| Reseller | Hosting allocations plus reseller role, enabled storefront and store profile for a buyer with the user role |

Previously disabled reseller storefronts require operator review; a purchase does not override that restriction. Higher administrative roles are never downgraded during activation. Each order grants a separate allocation; active allocations add together. Storage writes, copies, archive extraction, image output and usage displays use the purchased allowance. New domain registrations in the panel obey the purchased website count. Existing accounts without purchased service history retain their previous domain inventory behavior. Individual upload/archive limits remain in effect.

Services have a 30-day allocation period without automatic renewal or recurring charges. Expired allocations stop contributing to panel limits. Storage retains the original 250 MiB baseline. The timer removes reseller access only when that access was granted by fulfillment and no active reseller allocation remains. Account files and existing static websites are retained; this is not automatic website teardown.

A provisioning failure does not charge again or create another account. Attempts back off from two minutes to at most one hour. After five failures, My Orders / Store Orders displays `needs_attention`; an authorized store operator or super admin can request a retry. Backend authorization prevents buyers or other sellers from issuing operator retries. Suspended, deleted, mismatched, unsupported or unavailable storefront orders cannot be marked active.

## Deployment

Use the normal Debian deployment playbook (or the static-websites playbook that imports it). Schema creation is additive. The deployment installs and enables the fulfillment timer after initializing the database. Keep the existing private inventory and Vault configuration. Existing merchant credentials and signed webhook endpoints must be configured; enabling the worker does not enable live charging or change gateway settings.

```sh
cd /root/olamidepanel
git pull --ff-only
ansible-playbook -i /root/olamidepanel-private/local.ini \
  ansible/enable-static-websites.yml --ask-vault-pass \
  -e @/root/olamidepanel-private/deploy-vault.yml \
  -e panel_public_ipv4=181.214.149.146
systemctl status olamidepanel-fulfillment.timer --no-pager
journalctl -u olamidepanel-fulfillment.service -n 50 --no-pager
```

The first run also activates eligible historical verified live payments. Back up the database and account files before deployment, and review historical paid orders as part of rollout.

## Explicit boundaries

Bandwidth is recorded as an allocation, not metered or enforced. There are no VPS, dedicated-server, email, database, PHP, domain registrar or third-party provisioning adapters in this implementation. Unsupported service types never report successful activation. Static publication still uses the separate DNS-verified Nginx/Certbot worker. Domain ownership proof is not bypassed by payment. Automatic refunds, disputes, chargeback suspension, renewals, billing emails, infrastructure capacity reservation and reseller subaccount resource pools require separate implementations. This worker activates supported panel resources, not arbitrary external services.

## Validation

Unit/transactional tests cover duplicate confirmations, rollback when queue insertion fails, TEST payment exclusion, mismatched amounts/orders, suspension, unsupported kinds, failure recovery, reseller activation and expiry. Transaction tests use a SQLite compatibility harness; CI includes a separate disposable MySQL test for real schema SQL, concurrent worker locking and storage enforcement. No live provider charge or production deployment is performed by these tests.
