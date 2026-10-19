#!/bin/bash
set -euo pipefail
if [[ ${EUID} -ne 0 ]]; then
    echo 'Run with sudo bash scripts/deploy-hosting.sh [policy-file]' >&2
    exit 1
fi
panel_repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
panel_policy=${1:-/etc/olamidepanel/hosting-bootstrap.yml}
if [[ ! -f "$panel_policy" ]]; then
    echo "Missing policy: $panel_policy" >&2
    echo "Copy ansible/hosting-bootstrap.example.yml to that path, chmod 600 it, and configure mail hostname and DNS credentials." >&2
    exit 1
fi
exec 9>/run/lock/olamidepanel-hosting-deploy.lock
flock -n 9 || { echo 'A hosting deployment is already running.' >&2; exit 1; }
# Refuse local changes; never reset production source.
git -C "$panel_repo" pull --ff-only origin main
if ! command -v ansible-playbook >/dev/null; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y ansible-core
fi
panel_inventory=$(mktemp)
trap 'rm -f "$panel_inventory"' EXIT
chmod 600 "$panel_inventory"
printf '[panel_servers]\nlocalhost ansible_connection=local ansible_python_interpreter=/usr/bin/python3\n' > "$panel_inventory"
ansible-playbook -i "$panel_inventory" "$panel_repo/ansible/deploy-hosting-automatic.yml" -e "@$panel_policy"
