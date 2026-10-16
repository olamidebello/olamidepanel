#!/bin/bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run as root on a clean Debian 12 server.'; exit 1; }
. /etc/os-release
[[ $ID == debian && $VERSION_ID == 12 ]] || { echo 'Debian 12 required'; exit 1; }
if [[ $# != 1 || ! $1 =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]+$ ]]; then echo 'Usage: install.sh panel.example.com'; exit 1; fi
hostname_arg=$1
[[ ! -e /etc/nginx/sites-enabled/olamidepanel ]] || { echo 'Existing panel detected; use documented update process'; exit 1; }
[[ -r /etc/olamidepanel/database.json ]] || { echo 'Configure MySQL and /etc/olamidepanel/database.json first; see README.'; exit 1; }
apt-get update
apt-get install -y python3 python3-venv nginx certbot python3-certbot-nginx
id olamidepanel >/dev/null 2>&1 || useradd --system --home-dir /var/lib/olamidepanel --shell /usr/sbin/nologin olamidepanel
install -d -m 755 /opt/olamidepanel
cp -r "$(dirname "$0")/../panel" /opt/olamidepanel/
python3 -m venv /opt/olamidepanel/venv
/opt/olamidepanel/venv/bin/pip install -r "$(dirname "$0")/../requirements.txt"
chown -R root:root /opt/olamidepanel
chown root:olamidepanel /etc/olamidepanel/database.json
chmod 640 /etc/olamidepanel/database.json
/opt/olamidepanel/venv/bin/python - <<'PYKEY'
import os
from pathlib import Path
from cryptography.fernet import Fernet
key=Path('/etc/olamidepanel/payment.key')
if not key.exists():
    fd=os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(Fernet.generate_key())
PYKEY
chown root:olamidepanel /etc/olamidepanel/payment.key
chmod 640 /etc/olamidepanel/payment.key
if [[ ! -e /etc/olamidepanel/runtime.env ]]; then
  printf 'PANEL_PUBLIC_URL=https://%s\nPANEL_ENABLE_LIVE_PAYMENTS=0\n' "$hostname_arg" > /etc/olamidepanel/runtime.env
  chown root:olamidepanel /etc/olamidepanel/runtime.env
  chmod 640 /etc/olamidepanel/runtime.env
fi
install -d -o olamidepanel -g olamidepanel -m 700 /var/lib/olamidepanel
install -m 644 "$(dirname "$0")/olamidepanel.service" /etc/systemd/system/
cat > /etc/nginx/sites-available/olamidepanel <<EOF
server {
 listen 80;
 server_name $hostname_arg;
 client_max_body_size 16m;
 location / {
  proxy_pass http://127.0.0.1:8090;
  proxy_set_header Host \$host;
  proxy_set_header X-Forwarded-Proto \$scheme;
 }
}
EOF
ln -s /etc/nginx/sites-available/olamidepanel /etc/nginx/sites-enabled/olamidepanel
nginx -t
systemctl daemon-reload
systemctl enable --now olamidepanel
systemctl reload nginx
certbot --nginx -d "$hostname_arg" --redirect
runuser -u olamidepanel -- /opt/olamidepanel/venv/bin/python /opt/olamidepanel/panel/server.py --create-admin admin
echo "Open https://$hostname_arg — panel foundation installed; hosting service provisioning is not implemented."
