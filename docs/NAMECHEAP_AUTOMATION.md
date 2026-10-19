# Namecheap DNS automation

Save an API account in Administration → Namecheap Accounts and test the connection. API activation and the outgoing IPv4 allowlist must be configured at Namecheap. This playbook provisions DNS A records using that encrypted saved account; it does not create a Namecheap login, enable API access, buy domains or change nameservers.

On the panel server, deploy the latest panel code first. Use the saved account ID (visible in each account heading). Copy `ansible/namecheap.example.yml` to your own configuration and set the account ID, mode and DNS zones. Hosts are comma-separated relative names. Separate the registered domain into SLD/TLD (`example` / `co.uk`). No API key belongs in the configuration file.

```bash
cd /opt/olamidepanel-source
git pull --ff-only origin main
ansible-playbook -i localhost, -c local ansible/provision-namecheap.yml -e @ansible/namecheap.example.yml
```

The adapter runs as the panel service user and decrypts credentials in memory using the existing payment encryption key. Its output contains domain names and status only. Existing records are preserved; conflicting records, unsupported metadata, non-Namecheap DNS and concurrent edits stop the operation. Avoid simultaneous external DNS writers because Namecheap replaces whole zones without atomic compare-and-swap. Successful runs verify the returned zone; reruns report unchanged when A records already match. Multi-zone updates are sequential and not transactional: a later failure leaves earlier successful changes in place. Review the reported completed domains before retrying. Check mode validates prerequisites and skips DNS calls. This playbook does not deploy websites or issue TLS certificates.
