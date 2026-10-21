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
