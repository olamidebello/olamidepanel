# Automated domain email (Debian 12)

`ansible/deploy-domain-email.yml` installs Postfix SMTP, Dovecot IMAP/LMTP,
and OpenDKIM. It reads active domains from the panel database using the existing
read-only exporter. `mail_extra_domains` adds operator-hosted domains outside
that inventory. An explicit inventory is also supported. The panel hostname must
be different from hosted mail domains; one shared mail hostname serves all domains.
This is an operator Ansible workflow, not a mailbox management GUI or webmail.

## Setup

Update the server source checkout at `/opt/olamidepanel/repo` first. Configure a
mail hostname such as `mail.dobhrap.com`, point its A record at the server, and
obtain a trusted Let's Encrypt certificate for that name before running. The
playbook verifies certificate trust, hostname and remaining validity. Existing
unmanaged Postfix, Dovecot or OpenDKIM configuration causes a refusal before
packages or configuration change; migrate an existing mail server separately.

Copy `ansible/domain-email.example.yml` outside the repository. Set
`mail_hostname` and list every mailbox with its full lowercase address and a
SHA512-CRYPT hash generated interactively using `doveadm pw -s SHA512-CRYPT`
(on a machine with dovecot-core installed). Encrypt the file with Ansible Vault.
Do not put plaintext passwords or hashes into shell arguments or Git.

```sh
ansible-playbook -i /secure/panel-inventory.ini \
  ansible/enable-domain-email-automation.yml \
  -e @/secure/mail-vault.yml --ask-vault-pass
```

For a single run, use `ansible/deploy-domain-email.yml` instead. The automation
variant performs an initial deployment and installs a 15-minute reconciliation
timer. New active panel domains receive routing and persistent DKIM keys on the
next successful pass. Mailboxes are created only from the operator list; no
shared default password or catchall is created. To add/change mailboxes, update
the vault file and rerun the automation variant; it replaces the root-only local
policy used by the timer. This local policy contains password hashes, not plaintext.
Do not run the playbook concurrently with the timer; stop the timer and wait for
its service before manual maintenance.

## DNS and connectivity

For each domain, follow `/etc/olamidepanel/mail-dns/DOMAIN.txt`, including the
DKIM TXT record from `/etc/opendkim/olamidepanel/DOMAIN/panel.txt` (public key only).
Publish MX, the shared hostname A record, SPF and DMARC. Merge SPF with any existing
provider record. Initial DMARC is monitoring (`p=none`); tighten after verification.
The hosting provider must set reverse DNS/PTR to the shared hostname and allow
outbound TCP 25. Allow inbound TCP 25, 587 and 993 through provider and host
firewalls. This playbook does not modify firewalls, registrar records or external
DNS. IPv4 only; do not advertise an AAAA record for this mail hostname.

Migrate any existing provider mailboxes and stored mail before switching MX.
Use the shared hostname for IMAPS port 993 and SMTP STARTTLS port 587. The login
is the full email address. Authenticated senders may use only their own mailbox
address. SMTP port 25 accepts incoming domain mail with opportunistic TLS;
authentication is offered only on TLS-required submission. Unknown recipients
are rejected rather than accepted into a catchall.

## Operations and limits

Configuration is validated before service restart. Ansible syntax and rendered
security invariants are tested locally; no live Debian installation, delivery or
external relay test has been performed in the development environment. After
installation, verify successful delivery in both directions with an external
account, SPF/DKIM/DMARC results, and that unauthenticated external relay is rejected.
A listening port alone does not establish deliverability.

Mail storage is `/var/vmail/olamidepanel/DOMAIN/LOCALPART/Maildir`. Reruns preserve
stored messages and DKIM private keys. The account list is authoritative: removing
an account disables authentication and new delivery while preserving mail. Removing
a domain still referenced by an account fails validation; remove those account
entries too. Domain ownership changes require operator review of mailbox policy;
this release does not automatically transfer mail to a new panel owner. There are
no mailbox quotas, spam/virus filtering, aliases, webmail, or mailbox GUI yet.
Back up mail storage, protected configuration and DKIM keys separately.

Certificate renewal reloads Postfix and Dovecot using a Certbot deploy hook.
The timer fails before changing mail if the certificate is expired or nearly expired.
Check `journalctl -u olamidepanel-mail.service`, `systemctl status postfix dovecot
opendkim`, and `/var/log/mail.log` where configured. Stop recurring reconciliation
with `systemctl disable --now olamidepanel-mail.timer`; this does not stop mail
services or delete data. Templates are backed up when replaced, but there is no
automatic multi-file rollback; restore backups before restarting after a failure.

References: [Postfix virtual domains](https://www.postfix.org/VIRTUAL_README.html),
[Postfix relay control](https://www.postfix.org/SMTPD_ACCESS_README.html),
[Dovecot 2.3 passwd-file](https://doc.dovecot.org/2.3/configuration_manual/authentication/passwd_file/).

## Domain mailbox GUI

`ansible/enable-mailbox-gui.yml` installs **Email → Email Accounts**, an
ownership-scoped API, and the root-only policy broker. It requires the existing
managed email setup above, including `/etc/olamidepanel/mail-policy.json`, a
trusted mail-host certificate and the reconciliation inventory. It preserves the
existing account list, adds `afribulkhub.com`, and creates
`support@afribulkhub.com` with a persistent random password if it does not already
exist. Existing support passwords are preserved.

From the updated checkout on the hosting server:

```sh
ansible-playbook -i /etc/olamidepanel/mail-local.ini ansible/enable-mailbox-gui.yml \
  -e mail_operator_username=YOUR_PANEL_LOGIN
```

Replace `YOUR_PANEL_LOGIN` with your active panel root or super-admin login. The
playbook stops mail reconciliation while updating. If installation fails, inspect
the failed task before restarting `olamidepanel-mail.timer`; it stays stopped to
avoid concurrent policy writers. An interrupted worker marks in-flight requests
uncertain rather than replaying them. Failed deployments can leave partially
updated configuration: inspect services and rerun reconciliation before resubmitting.

New support credentials are in the root-only file
`/etc/olamidepanel/afribulkhub-support-credentials.json`. Read it locally as root;
do not post its contents. It contains the shared mail hostname and client ports.
Rotate the mailbox password in the GUI after retrieving it and remove this initial
credential file after recording credentials safely; the file is a bootstrap copy,
not a password-reset history. Existing mailboxes have no recoverable plaintext
password. Use full mailbox addresses to sign in, IMAPS 993 and SMTP STARTTLS 587.
There is no webmail in this feature.

The GUI supports create/reset and disable (messages retained), with recent request
status. The existing 15-minute timer applies queued requests and rechecks the
requester's active role and approved domain ownership. `applied` means the mail
playbook succeeded; it does not establish public deliverability. Passwords are
hashed using SHA512-CRYPT through stdin and never passed in command arguments or
returned by the API. Completed requests discard hashes. The broker limits domains
to 100 enabled mailboxes and requesters to 20 pending operations.

For each additional hosted domain, first verify control and mail routing, add it
to the root-owned mail policy's `mail_extra_domains` without replacing existing
entries, then delegate it locally:

```sh
systemctl stop olamidepanel-mail.timer
# Wait until olamidepanel-mail.service is inactive before changing mail policy.
/opt/olamidepanel/venv/bin/python /opt/olamidepanel/repo/deploy/mail_account_worker.py \
  --approve example.com PANEL_USERNAME
systemctl start olamidepanel-mail.timer
```

A regular panel account must already own the matching domain inventory record.
Creating an inventory entry alone does not authorize mail. Existing delegations
cannot be reassigned through this command: mailbox transfers require operator
review. Root/super-admin accounts can manage approved domains. Other accounts
cannot list or change another owner's mailboxes. Inventory removal or transfer
revokes future mailbox operations; it does not delete existing stored messages or
implicitly transfer mail access. Operators must separately disable mailboxes when
offboarding a domain or account.

Publish the generated `/etc/olamidepanel/mail-dns/afribulkhub.com.txt` records,
including DKIM, and verify the shared hostname's A/PTR records. Test incoming and
outgoing mail externally before advertising the support address. This installer
does not change registrar DNS, provider PTR, or firewall rules.

## Automatic build, mailbox installation and Namecheap mail DNS

For an **existing Debian 12 OlamidePanel installation**, use
`ansible/build-and-configure-mail-dns.yml`. This installs current Python source,
checks bytecode compilation, publishes the shared mail hostname A record, waits
for public address resolution, obtains trusted TLS, configures Postfix/Dovecot and
DKIM, installs the mailbox GUI and `support@afribulkhub.com`, and publishes
MX/SPF/DKIM/DMARC through Namecheap. Existing mailbox accounts, passwords and
operator extra domains are retained. No separate compiled frontend is required.

First add your API account under **Administration → Namecheap Accounts** and
allowlist the hosting server's public IPv4 in Namecheap API access. Domains must
use Namecheap authoritative DNS; registering a domain there alone is insufficient.
The workflow reuses the encrypted account and the panel's existing encryption key;
no API key belongs in the variables file or Git.

On the hosting server, from the updated source checkout:

```sh
cp ansible/mail-dns-automatic.example.yml /etc/olamidepanel/mail-dns-automatic.yml
chmod 600 /etc/olamidepanel/mail-dns-automatic.yml
# Edit the file: panel root login, saved account ID, public IP, ACME email,
# shared mail hostname, target domains and their explicit SLD/TLD zone mappings.
ansible-playbook -i /etc/olamidepanel/mail-local.ini \
  ansible/build-and-configure-mail-dns.yml \
  -e @/etc/olamidepanel/mail-dns-automatic.yml
```

For a first mail installation without that inventory, create a protected inventory
file containing:

```ini
[panel_servers]
localhost ansible_connection=local ansible_python_interpreter=/usr/bin/python3
```

Pass that file with `-i` instead. Run as root or with working privilege escalation.
The example uses `mail.olamidepanel.com` and `afribulkhub.com`; replace them when
needed. Only `mail_target_domains` receive mail-domain DNS changes. Include each
in `mail_extra_domains` and map both their authoritative zones and the shared
mail hostname's zone. Explicit mappings also support names such as `example.co.uk`;
the script never guesses the public suffix. Rerun after adding a domain to these
lists to install keys, publish its records and approve its operator mailbox GUI.

Unrelated records and their TTL/MX metadata are retained. Matching records are
idempotent. Conflicting MX/SPF/DKIM or a mail-host AAAA/CNAME/ALIAS stops the run;
migrate an existing mail provider explicitly. Existing single DMARC policies are
preserved, including stricter policies. `allow_custom_mx: true` explicitly permits
switching the target zone to Custom MX; it does not bypass record conflicts.
Unsupported records (including CAA if the API representation cannot be preserved)
and Dynamic DNS also require manual review rather than zone replacement.

Each phase preflights all its zones, checks for intervening changes and reads back
the full zone after writing. Namecheap has no atomic compare-and-swap here: avoid
concurrent DNS editing. Updates across zones or phases are not transactional;
a failure can leave earlier changes applied. Inspect provider DNS and the phase
reports before retrying. Reruns preserve persistent DKIM keys and mailbox passwords.
The workflow pauses mail reconciliation for installation; an early failure leaves
it paused for inspection. The final DNS phase restores the timer even on failure.

Forward-DNS provider read-back does not prove public propagation or email delivery.
The hostname must resolve publicly before ACME succeeds. PTR defaults to a pending
provider instruction report because the hosting provider controls reverse DNS;
set `mail_reverse_dns` to the existing RFC2136 adapter only with delegated reverse
zone credentials. Provider/host firewalls must allow TCP 25, 587 and 993, including
outbound 25. Finally test incoming/outgoing messages externally and inspect
SPF/DKIM/DMARC results. This workflow does not claim live deployment or public
message delivery from a successful code build alone.

## Provision the recovered hosting domains

`ansible/provision-all-domain-email.yml` removes the legacy single-domain
bootstrap restriction. Copy `ansible/all-domain-email.example.yml` to
`/root/all-domain-email.yml`, restrict it to mode 0600, and replace
`mail_operator_username` with the existing panel root/super-admin login.
Review the selected domain list before running. Active panel domains are also
included by the existing `mail_domains_source: panel` reconciliation policy.
For a strictly selected inventory use `mail_domains_source: inventory` and
`mail_domains: []` (the approved extras provide that inventory).

First point `mail.olamidepanel.com` A to `154.16.170.86`, remove a conflicting
AAAA record, and allow inbound HTTP for certificate issuance. Then run:

```sh
ansible-playbook -i 'localhost,' -c local ansible/provision-all-domain-email.yml \
  -e @/root/all-domain-email.yml
```

The installer preserves authoritative mailbox hashes, existing mailbox data and
DKIM keys; generates postmaster, abuse and support accounts with random initial
passwords; obtains a trusted mail-host certificate; enables SMTP 25, authenticated
SMTP 587/STARTTLS and 465/implicit TLS, IMAP 993; approves each selected domain in
the Email Accounts GUI; and installs the existing fifteen-minute reconciliation
broker. Use the complete email address as the mail-client username. The common
incoming/outgoing server name is `mail.olamidepanel.com`.

Initial generated passwords are saved only in the root-readable
`/etc/olamidepanel/mail-bootstrap-credentials.json`; use the GUI to reset passwords
without disclosing that file. Password resets make saved initial passwords stale.
DNS instructions and verification results are in
`/etc/olamidepanel/mail-dns/` and `mail-bootstrap-*-report.json`. Manual DNS mode
reports required MX, SPF, DKIM, DMARC and PTR records without changing provider
records. Ask the server provider to set reverse DNS for the server IP to the mail
hostname. Open the mail ports in the provider firewall and check outbound port 25.
Do not change MX for a domain still receiving mail on another server until ready
to cut over. This provisions new mailboxes; it does not migrate old messages.

This is a Postfix/Dovecot hosting stack, not cPanel. Roundcube webmail, POP3,
mailbox quotas, forwarding/aliases, vacation replies, spam filtering, mailing
lists and external delivery tests are not installed by this entry point. A
successful playbook verifies local service availability, not inbox placement.
