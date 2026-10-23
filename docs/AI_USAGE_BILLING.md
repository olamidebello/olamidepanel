# OpenAI text services and 30% markup

Install on the panel host:

```bash
cd /opt/olamidepanel/repo
git pull --ff-only
ansible-playbook -i localhost, -c local ansible/enable-ai-billing.yml
```

1. Open **Administration → API Providers & Keys**. Add/reuse the OpenAI credential, enable it, and assign the domains allowed to use it. No key is included in GitHub or returned to browsers.
2. Open **Administration → AI Billing & Pricing**. Choose that credential, an exact text-chat model snapshot available in your OpenAI project, input/cached-input/output buying prices in USD per million tokens, a reference/date for those prices, and the output limit. Confirm pricing and enable the service. No model or price is silently selected.
3. Credit each user's separate AI balance after receiving payment, or explicitly grant credit with a reason. Credits are audited and idempotent; this action does not collect money. Automatic payment-gateway AI top-ups are not included.
4. Users open **Integrations → AI Services**, choose a domain and authorize usage billing before sending text.

Provider buying cost = ((input tokens − cached tokens) × input rate + cached tokens × cached rate + output tokens × output rate) / 1,000,000.

User charge = provider buying cost × **1.30**. For example, a $10 buying cost produces a $13 user charge. Decimal accounting retains ten decimal places; there is no per-request cent minimum. This is 30% markup on cost, not 30% gross margin. Buying cost is calculated from the configured rate snapshot and provider usage; it is not an automatically imported invoice cost. Enter your actual account buying rates and reconcile any discounts or invoice adjustments separately.

A conservative text-token reservation and output cap stop requests without sufficient credit. Successful usage settles the reservation and refunds the difference. Configuration is versioned at request confirmation and snapshotted in each request. Retries with the same request ID return the saved result without calling OpenAI or charging again; a different prompt with the same ID is rejected.

The initial adapter uses the standard text Chat Completions endpoint, one result, no tools, no streaming or automatic retries. Audio, images, tools, batch/flex/priority pricing and other provider features require separate billing adapters. Use an exact model snapshot: a returned model/tier mismatch or missing/unexpected usage is held for review instead of inventing a charge.

Definitive validation/auth/rate-limit rejections release the reservation. Timeouts, uncertain upstream failures and interrupted pending requests retain their hold. Admins reconcile using provider evidence; pending requests cannot be reconciled within the first ten minutes. Confirmed charges are immutable. Users can create a new request ID, but cannot start new work while an earlier request is pending or requires review. Saved answers are encrypted for owner-only replay; prompts are not stored by this component. OpenAI still receives the prompt to process the request.

Balances and recent metering are shown in the admin page. Currency is USD; no currency conversion, taxes, refunds, card collection or automatic external billing is implied. Hosted applications are not automatically wired into this panel endpoint; they require authenticated server integrations and per-user attribution. The current UI uses panel sessions and CSRF protection.

Official references (review current account pricing before enabling):

- https://developers.openai.com/api/docs/pricing
- https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create

No live paid API request is required by installation or automated tests.
