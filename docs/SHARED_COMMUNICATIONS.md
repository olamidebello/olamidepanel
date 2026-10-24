# Shared email, phone and PBX integration

The shared contract uses `sip.dobhrap.com`; `sip.dobhrapn.com` is not configured.
This is a backend integration kit, not completed signup wiring for every app.

## SIP server

From the SIP server, run the reviewed Sip repository playbook:

```sh
ansible-pull -U https://github.com/olamidebello/Sip.git -C main \
 -d /opt/sip-hosted-app-bootstrap -i localhost, -c local \
 deploy/ansible/hosted-app-services.yml
```

Default production source: `/opt/olamide/repo`; secrets:
`/etc/olamide/secrets.env`. Override `sip_repo`/`sip_secrets` when different.
The playbook preserves volumes, creates stable application tokens, rebuilds API
and validates HTTPS health. Per-application client JSON files are in
`/etc/olamide/hosted-apps/`, accessible to root only. Transfer each application's
own file privately to its service configuration directory on the hosting server;
never give any application the whole token map or another application's token.
Back up secrets.env and the database before production updates.

`POST /api/integrations/hosted-apps/provision` accepts Bearer plus X-Hosted-App.
Body fields: subject, email, name, emailVerified=true, accountType (individual,
business, court, organization), and organizationId for non-individuals. Only a
trusted backend may assert verified email, organization membership and type.
End users must not be able to submit arbitrary subject/organization IDs to that
backend. Revoke a compromised app by removing its token from the SIP map and
recreating the API service. No super-admin privileges are granted to app users.

New individuals receive isolated SIP workspaces. Organizations receive a tenant,
PBX feature group and numbered extensions starting at 1001. The first organization
user is that tenant's admin; subsequent members are users. A stable app/subject
mapping prevents duplicate accounts on retries. Existing global SIP email
collisions return 409 and require verified account linking; they are never
silently claimed. Cross-application consolidation and membership/type changes
are not implemented. Suspended users and tenants remain blocked. SIP switch
activation is handled by its existing provisioning worker and is reported
separately. PBX records do not commission an Asterisk runtime or external trunks.

## Hosting application adapters

Each application must call `integrations/hosted_services.py:enqueue` after its
verified registration commits. Import the installed module from
`/opt/olamide-shared-services`; keep its SQLite database in that application's
private state directory, writable by its existing service account. An unverified
email must never be marked verified simply because it was typed into a form.
Do not pass application passwords; SIP creates an independent unknown random
password and the user sets their own through the SIP recovery flow.

Example backend hook (subject and organization come from authenticated records):

```python
hosted_services.enqueue('/var/lib/myapp/communications.sqlite',
 subject=str(user.id), email=user.email, name=user.name,
 email_verified=user.email_verified, account_type=user.account_type,
 organization_id=user.organization_id)
```

Use `status(database, authenticated_user.id)` in a protected app endpoint. Never
accept another user's subject from the browser. Serve `phone-services.js` through
the app's authenticated workspace and pass a function fetching that endpoint.
It shows provisioning/switch status and opens the existing phone/PBX portal.
This widget is not an embedded dialer or SSO; SIP sign-in/passkey policies remain.
Each app's framework/router, account type model, verification and organization
membership need an application-specific adapter before automatic signup works.

Install the SDK and retry timers with `ansible/enable-shared-communications.yml`,
passing `communication_apps` entries with id, user, group, config. Private JSON:

```json
{"app_id":"myapp","token":"SERVER_GENERATED_PRIVATE_TOKEN","database":"/var/lib/myapp/communications.sqlite"}
```

File owner must be root or that service user; group must match its application
group; mode 0600 or 0640. Credentials must remain server-side. SDK permissions do
not replace application authorization. Jobs retain verified registration PII in
the private application database; apply the application's retention policy.

## System email

Optional `smtp` in each private JSON contains host, port (465 or 587), username,
password and from. Use a dedicated permitted sender, TLS certificate validation
and existing domain mail service. No shared SMTP password goes to a browser.
The worker sends a transactional account notice only after provisioning succeeds;
there is no marketing distribution. Retries can send a duplicate notice after
an ambiguous SMTP acknowledgment. SMTP absence does not block SIP provisioning.
This does not yet replace each app's password-recovery/verification mailer.
SIP password recovery email must already be configured to let new users sign in.

Registration events, status API routes, navigation mounting and account type
selection are not automatically patched into heterogeneous repositories by this
kit. Live commissioning requires those adapters, token handoff, configured SMTP,
SIP switch/PBX readiness and a real test registration for every application.
