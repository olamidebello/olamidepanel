# One Linux user per domain, with managed SSH keys

`ansible/domain-ssh.yml` creates one deterministic Linux identity for each domain: `dom_` plus the first 16 hexadecimal SHA-256 characters of its lowercase DNS name. The same domain keeps its username on subsequent runs. Separate domains have separate users, private homes, primary groups and keys. No account receives sudo membership. Existing unrelated usernames and unmarked storage paths are refused rather than adopted.

Access modes:

| Mode | Behavior |
| --- | --- |
| `sftp` | Default. Public-key access only, internal SFTP, root-owned chroot, private writable home, no terminal or forwarding. |
| `shell` | Explicit operator choice. Normal `/bin/bash` Linux shell with key-only authentication and no forwarding. This shell has ordinary host filesystem visibility; it is not container isolation. |
| `disabled` | Expired Linux account, nologin shell, empty managed authorized-keys file. Files and identity are retained. |

Keys are public keys provided by the operator/account owner. Never upload private keys, and do not replace the server operator's SSH keys. The playbook validates keys with `ssh-keygen`, replaces each domain's managed key set, validates the full SSH configuration and effective options, and reloads SSH only after validation. Earlier conflicting SSH Match policies cause failure rather than silently weakening the managed rules. Main and managed SSH configuration files are restored on validation failure; account/file/key changes are retained for operator inspection. Existing established sessions are not forcibly terminated by suspension.

The inventory is authoritative for these managed users. An empty explicit inventory is refused unless `domain_accounts_allow_empty=true` is deliberately set; an empty database source suspends previously managed domain accounts. Domains removed from the inventory are suspended on the next run; data is not deleted. Database source also suspends domains whose panel owners are inactive. Missing owner keys default to disabled access. Manual exceptions to a managed domain policy will be reconciled on the next run.

## Explicit domain inventory

Copy `ansible/domain-ssh.example.yml` to a private file, insert REAL SSH public keys and select the access mode. Then run:

```sh
cd /root/olamidepanel
ansible-playbook -i /root/olamidepanel-private/local.ini \
  ansible/domain-ssh.yml \
  -e @/root/olamidepanel-private/domain-ssh.yml
```

The final output lists each domain's username. Connect using that username and the key's corresponding private key on your own device:

```sh
sftp -i ~/.ssh/your_private_key dom_HASH_FROM_PLAY_OUTPUT@181.214.149.146
```

User files are under `/srv/olamidepanel-domains/USERNAME/home/USERNAME`. Domain markers live under `/etc/olamidepanel/domain-users`; public keys are root-managed under `/etc/ssh/olamidepanel-domain-keys`.

## Automatically discover panel domains

A private policy can use:

```yaml
domain_accounts_source: panel
domain_owner_ssh:
  '42':  # existing numeric panel owner ID
    access: sftp
    public_keys:
      - 'ssh-ed25519 YOUR_REAL_PUBLIC_KEY owner-device'
```

The read-only exporter runs as `olamidepanel` using its existing protected database configuration. It returns only domain names, owner IDs and owner active states. Keys and shell choices come from the operator's policy, never from user-controlled domain metadata. Each domain owned by owner 42 gets its own Linux identity, using that owner's authorized public keys. A domain can have multiple listed keys for multiple devices. Changing the key list rotates/revokes access on the next run.

## Continuous automatic creation and management

After deploying the current source to `/opt/olamidepanel/repo`, install the reconciliation timer:

```sh
cd /root/olamidepanel
ansible-playbook -i /root/olamidepanel-private/local.ini \
  ansible/enable-domain-ssh-automation.yml \
  -e @/root/olamidepanel-private/domain-ssh.yml
```

This stores the owner policy root-only, installs local Ansible and runs the initial reconciliation before enabling `olamidepanel-domain-ssh.timer`. Every two minutes, new domains receive separate Linux users and existing users receive their configured key/access changes. Suspended owners and deleted domains lose new-login access. Update the private policy and rerun the enable playbook to update the scheduled policy. With no configured keys, accounts are created disabled.

```sh
systemctl status olamidepanel-domain-ssh.timer --no-pager
journalctl -u olamidepanel-domain-ssh.service -n 80 --no-pager
```

The root timer executes deployed repository code; keep `/opt/olamidepanel/repo` and the private policy writable only by trusted server operators. Stop/disable the timer before intentionally applying one-off policies. This is a separate opt-in deployment; it does not grant the HTTP application sudo or root access.

## Boundaries and validation

These Linux homes are independent of the existing unprivileged panel file-manager homes and static publisher directories. This playbook does not move/chown existing websites, create DNS records, issue TLS certificates, implement Linux disk quotas, or connect a paid purchase to Linux account lifecycle. Payment-based panel allocation remains handled by the existing fulfillment worker. Database discovery operates on domain inventory, not proof of payment or DNS ownership.

Ansible syntax and OpenSSH effective configuration are tested locally, including SFTP confinement, shell mode and disabled-mode defaults. Full remote account creation, SFTP transfers, production SSH access and the systemd timer must be verified on the target Debian server.
