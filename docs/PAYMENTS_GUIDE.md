# Payment gateway administration

> Current paid-service behavior: verified live Stripe/Paystack payments automatically activate supported panel hosting/reseller resources. See [automatic provisioning](AUTOMATIC_PROVISIONING.md) for scope, deployment and limitations; this supersedes older manual-activation descriptions below.

## Scope and adapter status

Stripe and Paystack have hosted checkout creation, payment verification and signed-webhook adapters in this release. They are **not merchant-tested or live-certified** in the authoring workspace. Other provider names in the GUI are an integration catalog, explicitly marked not implemented; their controls cannot be enabled. There is no universal “all payment gateways” API.

The catalog lists PayPal, Flutterwave, Square, Adyen, Authorize.Net, Braintree, Mollie, Razorpay, Checkout.com, Worldpay, OPay, Monnify and bank transfer as unimplemented. Product/country eligibility, currencies and supported methods depend on each merchant's agreement. Only USD plan pricing currently exists; Paystack USD support must be available on that merchant account.

Payment covers a **single month as a one-time charge**, with no automatic renewal. No card data is collected by the panel: customers leave for a provider-hosted checkout page. There is no invoice/tax/refund/chargeback/subscription/payout/commission automation. Hosting activation remains manual and separate from payment verification. No platform-wide routing of reseller revenue is implied: store-owned credentials select the merchant receiving funds.

## Deploy prerequisites

Use `ansible/deploy-available-modules.yml` with the existing inventory and encrypted deployment variables. It imports the bare-server deployment, installs requirements, initializes additive MySQL tables, creates a persistent Fernet key, sets the public HTTPS origin, restarts the service, runs local unit tests (database integration tests skipped) and prints module coverage.

```sh
cd /root/olamidepanel
git pull --ff-only
ansible-playbook -i /root/olamidepanel-private/local.ini \
  ansible/deploy-available-modules.yml --ask-vault-pass \
  -e @/root/olamidepanel-private/deploy-vault.yml
```

This playbook deploys the implementation present in the repository. It does not generate absent hosting-service adapters. `panel_require_all_modules: true` makes the final inventory check fail while partial/unimplemented modules remain; the check occurs after deployment and does not roll back a completed deployment.

The key `/etc/olamidepanel/payment.key` is root-owned/group olamidepanel, mode 0640. The app process must read it to decrypt credentials; database encryption alone does not protect against a compromised application/host. Keep encrypted off-server backups of the key together with the database. **Do not overwrite or delete the key**: gateway secrets would become unreadable. No automatic key-rotation workflow is supplied. `PANEL_PAYMENT_KEY` can override its path.

The runtime environment file `/etc/olamidepanel/runtime.env` contains `PANEL_PUBLIC_URL` and `PANEL_ENABLE_LIVE_PAYMENTS`. Live mode is disabled by default. After provider sandbox tests, webhook reachability tests and operator review, explicitly set `panel_enable_live_payments: true` in encrypted deployment variables and rerun. Enabling live mode can collect actual funds; configure paid-service terms, fulfillment, support and refund processes first. Never store merchant secrets in Git or screenshots.

## Super-admin controls

Navigation: Marketplace → Payment Gateways / Payments; Administration → Access Control / Reseller Access / Module Readiness.

1. Create/manage panel users and grant reseller role through Access Control.
2. Enable reseller publishing through Reseller Access.
3. In Payment Gateways add a Stripe/Paystack configuration. Store ID 0 is the operator; a nonzero ID must identify an active, publishing-enabled reseller.
4. Enter label, provider, test/live mode and merchant secret. Stripe also needs its endpoint's webhook signing secret. Use test mode first. For an existing gateway, blank secret inputs preserve stored credentials.
5. Set enabled when ready. Live enabling also requires explicit live confirmation and deployment permission.
6. Copy the displayed webhook URL into the matching provider account. Stripe should send checkout.session.completed and checkout.session.async_payment_succeeded. Paystack should send charge.success. The endpoint is `/api/payments/webhook/<gateway_id>`.
7. Test a hosted checkout and confirm it in Payments. A browser return page is never sufficient proof of payment.

Super admins may manage any store's gateway metadata/secrets. Secret plaintext is never returned in listing APIs. Provider/mode/owner are immutable for a gateway; use a separate gateway for another merchant account, provider or mode. Do not replace a gateway with another merchant's key while payments still need verification. Disable rather than delete a configuration; existing payments/webhooks still need its credentials. Separate test/live gateways are recommended.

## Reseller controls

An active reseller with enabled publishing can manage only gateways belonging to its own user/store ID. It cannot use another store's credentials or select the operator's merchant account for its own orders. Super admin can disable publishing, which prevents new reseller checkout and gateway edits. The reseller can view and verify historical payments for its store; no raw gateway credentials are exposed by listing APIs.

## Customer checkout

1. Submit a plan request. The seller/operator approves it for manual follow-up.
2. In My Orders → Payment options, select an enabled gateway belonging to that seller.
3. Review price, one-month term and TEST/LIVE label, check confirmation, then continue.
4. Complete payment on the provider's hosted page.
5. Return and open Payments → Verify with provider, or wait for the signed webhook to update the record. A TEST paid status is simulated, not revenue.

A valid contact email in Preferences is required for Paystack. A free order is handled manually without checkout. There is one payment attempt per order; retries reuse an existing hosted checkout instead of creating another charge. If a request times out or setup fails, its state becomes needs_review. Do not make a new order merely to retry payment; reconcile the original attempt with the merchant first.

## Reconciliation and verification

Store administrators can enter a provider reference from their merchant dashboard. Stripe uses its Checkout Session ID and the displayed panel token in session metadata to identify the intended attempt. Paystack references are fixed as `panel-<token>`. Verification re-fetches the provider transaction and checks reference/metadata, exact integer amount, currency and live/test mode before marking paid. The GUI provides no manual “mark paid” override.

Stripe signatures use the original body and timestamp/HMAC checks with a five-minute tolerance. Paystack uses HMAC-SHA512 of the raw body. Webhooks require no browser session/CSRF token because signatures authenticate them. Paid transitions are idempotent. The system can miss an early event before a provider reference has been saved; manual verification/reconciliation is the recovery path. There is no autonomous reconciliation scheduler yet.

## Database and API

`payment_gateways` holds store ownership, provider, mode, enabled state and Fernet-encrypted credentials. `payment_transactions` holds unique order ID/token, buyer/seller IDs, selected gateway, amount/currency/mode, provider reference, checkout URL, state and timestamps. No card numbers or CVV fields exist. Payment rows intentionally do not cascade with account/order deletion; they need an operator financial-data retention/deletion process. Seller IDs are monotonic and not reassigned.

| Route | Method | Purpose |
|---|---|---|
| `/api/payments/providers` | GET | Adapter availability |
| `/api/payments/gateways` | GET | Authorized operator/reseller metadata only |
| `/api/payments/gateways/save` | POST | Scoped create/edit/enable/disable |
| `/api/payments/transactions` | GET | Buyer/store/all visibility |
| `/api/payments/options/<order_id>` | GET | Buyer's approved-order seller gateways |
| `/api/payments/checkout` | POST | order_id, gateway_id, confirmed boolean |
| `/api/payments/verify` | POST | id; server-to-server verification |
| `/api/payments/reconcile` | POST | id, reference; authorized store admin only |
| `/api/payments/webhook/<gateway_id>` | POST | Signed provider callback |
| `/api/modules` | GET | Super-admin implementation inventory |

Browser mutations require session/CSRF and role/ownership checks. Read-only users cannot mutate. API errors never intentionally include merchant secret responses. Back up both database and encryption key before upgrades.

## Verification and remaining work

Local tests cover signature tampering/timestamps, credential encryption, wrong amount/currency/mode/metadata, read-only access and customer restrictions on credential metadata. MySQL integration, hosted provider test transactions, real webhooks, failure reconciliation, concurrency and browser flows require live validation. Do not interpret local mocks as a successful payment test.

Official implementation references:

- https://docs.stripe.com/payments/checkout/quickstarts
- https://docs.stripe.com/webhooks/signatures
- https://paystack.com/docs/payments/accept-payments/
- https://paystack.com/docs/payments/verify-payments/
- https://paystack.com/docs/payments/webhooks/
