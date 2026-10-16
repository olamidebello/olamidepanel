> Payment update: Stripe/Paystack hosted checkout and verification adapters are now available for merchant testing. See [Payments guide](PAYMENTS_GUIDE.md). Statements below about no connected payment processing describe the original order-review workflow; billing, renewals, refunds and hosting provisioning remain unimplemented.

> Current paid-service behavior: verified live Stripe/Paystack payments automatically activate supported panel hosting/reseller resources. See [automatic provisioning](AUTOMATIC_PROVISIONING.md) for scope, deployment and limitations; this supersedes older manual-activation descriptions below.

# Hosting marketplace and dashboards

## Available workflows

The marketplace is a MySQL-backed catalog and manual order-review system. It does not charge cards, create invoices, activate hosting accounts, enforce resource allocations or renew services. Those integrations remain unimplemented. An approved request is not an active subscription.

Navigation: **Marketplace → Marketplace Dashboard / Hosting Plans / My Orders**. Root and super admin also have **Administration → Hosting Catalog**. Dashboards show enabled-plan counts and pending/approved/rejected/cancelled order counts. Customers see their own orders/counts; privileged operators see all accounts. Orders show the latest 200 entries. Search and status filters operate on the loaded results.

## Suggested plan templates

These editable examples are starting points, not market quotes, tested server capacity or contractual hosting offers:

| Template | Illustrative monthly USD price | Storage target | Transfer target/month | Websites target |
|---|---:|---:|---:|---:|
| Starter | $5 | 10 GB | 100 GB | 1 |
| Business | $15 | 30 GB | 500 GB | 5 |
| Growth | $30 | 75 GB | 1,500 GB | 15 |

Starter is intended as a planning example for a personal site; Business for a small business; Growth for several business websites. Actual capacity, performance, backup, support, tax, provisioning and profit margins require operator review. No limits are automatically enforced. Templates appear only to operators and are not inserted or published automatically. Prices are stored as integer cents and the current catalog supports USD monthly plans only.

## Operator: create and publish a plan

1. Open Hosting Catalog and choose Create plan or Customize a suggested template.
2. Enter a name, description, price in cents, and numeric resource targets.
3. Check Publish only when ready to receive requests. Check Feature to label the plan as operator featured.
4. Save. Published plans become visible in Hosting Plans.
5. To withdraw a plan, edit and disable Publish. Existing order snapshots remain unchanged. There is no hard-delete control.

A zero-cent plan is permitted but still requires manual review. “Featured” is an operator label, not an independent recommendation. Do not describe uninstalled services or unenforced allocations as available capacity.

## Customer: request a plan

1. Browse/search Hosting Plans and select Request this plan.
2. Review the displayed price, add an optional note and confirm the manual-review notice.
3. Submit. My Orders shows a pending request; no payment is collected.
4. Cancel a pending request if necessary. Approved/rejected/cancelled requests cannot be changed through this workflow.

If the price changed since the catalog was loaded, reload and confirm the new price. The API uses a client request key to prevent duplicate orders for a retry with the same key. A new dialog creates a new key and therefore a separate possible order. There is no shopping cart, multi-item checkout, payment gateway, subscription renewal or refund workflow yet.

## Operator: review requests

Open My Orders as root/super admin to see requests across accounts. Filter pending, enter an optional operator note (visible to the customer), then approve for follow-up or reject. Operators may cancel pending requests. Subsequent infrastructure setup and any commercial agreement/payment happen separately. Every catalog mutation and order state change writes an audit entry.

## Database and API

`hosting_plans` stores catalog fields; `hosting_orders` stores owner/plan links, unique (owner,request_key), immutable plan snapshot/quoted cents, status, customer/operator notes and timestamps. User deletion cascades to their orders. Plans referenced by orders are not deleted by the API. Back up MySQL before deployment; new tables initialize at service startup.

| Route | Method | Access |
|---|---|---|
| `/api/marketplace/plans` | GET | Authenticated; customers receive enabled plans only |
| `/api/marketplace/summary` | GET | Own totals or all-account totals for root/super admin |
| `/api/marketplace/orders` | GET | Own latest 200 orders; operators see all latest 200 |
| `/api/marketplace/plans/save` | POST | Root/super admin; optional id for edit |
| `/api/marketplace/orders/create` | POST | Writable account; plan_id, expected_price_cents, request_key, confirmed=true, note |
| `/api/marketplace/orders/action` | POST | Owner cancel or operator approve/reject/cancel; id, action, optional operator_note |

All mutations require session/CSRF validation. Read-only accounts cannot submit or change records. Row locks serialize pending-order state transitions. Price/name/resource details are snapshotted when requested; later catalog edits do not rewrite prior orders. This release does not implement state-transition notifications, tax/currency conversion, revenue reporting, discounts, inventory limits or external vendor APIs.

## Validation limits

Local unit tests cover plan numeric validation, role restrictions and permitted transitions. The integration test adds catalog creation, idempotency, stale-price rejection, snapshot storage and approval. That test requires the disposable MySQL test environment and is skipped locally without it. Browser and live-server marketplace verification remain pending.

## Reseller storefronts and super-admin control

Super admin manages user roles through **Administration → Access Control** and storefront approval through **Administration → Reseller Access**. Assign reseller role first, then enable publishing. Disabling a reseller storefront removes its plans from the public catalog and prevents reseller edits/order review. Suspending the user or changing its role also makes its plans unavailable to other customers. Operators can still see and edit those catalog entries and handle orders. Restoring the role/account and publishing permission can restore visibility; disabling access does not delete historical orders.

A reseller opens **Marketplace → Reseller Catalog** to create/edit/publish only its own plans. It can view its purchases and orders addressed to its store in My Orders, approve/reject pending store orders while publishing is enabled, and cancel its own pending purchases. It cannot edit another seller's catalog, enable its own publishing permission, grant privileges, access unrelated orders or approve another seller's request. Customers see the seller and plan category on each card. Buying a reseller-category plan does not automatically grant the reseller role; a privileged operator assigns roles separately after manual review.

Additional illustrative monthly USD templates:

| Template | Example price | Storage target | Transfer target | Websites target |
|---|---:|---:|---:|---:|
| Reseller Launch | $25 | 50 GB | 500 GB | 20 |
| Reseller Business | $50 | 100 GB | 1,500 GB | 50 |
| Reseller Scale | $100 | 250 GB | 4,000 GB | 100 |

These are editable planning examples, not market-rate claims, tested capacity, delegated Linux accounts or enforced quotas. Root/super admin can publish operator-owned plans in hosting/reseller categories or disable a reseller-owned plan. Existing user-management screens remain the authority for account lifecycle and passwords.

`marketplace_vendors` stores reseller publishing permission. Plans/orders preserve seller IDs in addition to buyer IDs and the order snapshot. Seller IDs are not reassigned to another user after account deletion; an orphaned seller's plans remain hidden from public requests. Buyer deletion cascades to their orders, so the current database is not a legally durable financial ledger. No payouts, commissions, reseller billing, taxation, license resale, subscription automation or infrastructure provisioning is supplied.

Additional APIs: GET `/api/marketplace/capabilities`, GET `/api/marketplace/vendors` and POST `/api/marketplace/vendors/save` (super-admin only; id and enabled boolean). Plan saves accept `plan_kind=hosting|reseller`; the server assigns seller ownership for new plans and forbids reassignment through the client.

The disposable MySQL integration suite includes cross-reseller edit/order isolation and disabled-storefront visibility checks. These tests remain unexecuted locally without MySQL. A browser/live-server verification is still required after deployment.

## Marketplace menus and store profiles

The Marketplace sidebar submenu and in-page navigation load from authenticated `/api/marketplace/navigation`. Shoppers see Dashboard, Hosting Plans, Browse Stores, My Orders and Payments. Resellers additionally see Reseller Catalog, Store Orders, Store Settings and Payment Gateways. Root/super admins see Hosting Catalog, all-store orders/settings, Reseller Access, gateways and Access Control. Hidden menu items do not replace server authorization. Browser Back/Forward and saved `#tool=` links restore the selected tool; Refresh reloads its records.

Browse Stores lists the operator and enabled, active reseller storefronts; View store plans filters the existing plan catalog. Show all stores clears the filter. Store Settings persists name, description and contact email in MySQL `marketplace_stores`. These fields are visible to signed-in shoppers. A reseller can edit only their own enabled store. Super admins can choose the operator (ID 0) or a reseller from the selector. Disabling a reseller hides its store/profile/plans and blocks edits. Store profiles do not collect card credentials.

My Orders uses `/api/marketplace/orders?scope=purchases` and shows only the signed-in buyer's purchases. Store Orders uses `scope=store` and shows the reseller's incoming orders, or all stores for root/super admin. Existing approval/rejection/cancellation and hosted checkout buttons call their authorized APIs. The unfiltered API remains compatible; each query is limited to the latest 200 visible orders. Order approval and successful payment still require separate manual hosting fulfillment.
