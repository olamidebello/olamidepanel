# Repair domain routing and HTTPS

Run on the OlamidePanel Debian 12 server:

```sh
ansible-pull -U https://github.com/olamidebello/olamidepanel.git -C main \
 -d /opt/olamide-domain-repair-bootstrap -i localhost, -c local \
 ansible/repair-domain-routing-ssl.yml
```

The default selection includes active panel domains and exact names already in
Nginx. Default IP is 154.16.170.86, ACME email dobcalldemo@gmail.com. Override with
repair_ipv4/repair_email or a root-owned extra-vars file. This requires an existing
panel and Nginx; it does not build app source or restore data.

For routing repairs, copy `ansible/domain-routing-ssl.example.yml` to a private
root file and populate `repair_targets` with confirmed ports, a health path and a
unique response marker identifying the intended application. Run with
`-e @/root/domain-routing-ssl.yml`. Examples are commented to avoid reusing stale
ports. Without a mapping the worker checks existing vhosts and installs SSL but
cannot establish that the correct application is behind them.

A mapped backend must answer locally with the required marker. The worker changes
only a plain `location /` loopback HTTP proxy, retaining other locations, paths
and controls. It backs up modified configuration, checks Nginx and reloads. Failed
Nginx changes roll back. Duplicate HTTP/HTTPS vhosts, nonstandard upstreams and
shared blocks with unrelated aliases are reported for review. It does not delete
vhosts or rewrite DNS records. No source builds, app restarts or schema changes
are performed.

SSL issuance requires the domain's A answers to contain only this IP and no AAAA.
Proxied CDN DNS or intentional IPv6 requires a separately reviewed deployment.
Port 80 must be publicly reachable for HTTP validation. Certbot installs HTTPS
and redirect with its nginx plugin, keeps unexpired certificates and installs its
renewal timer. Each certificate is verified through local TLS with the correct
hostname. This is not an outside-network reachability test. Existing aliases are
processed independently; wildcard certificates are not requested. Certbot errors
and rate limits are retained in private logs, not retried continuously.

Read `/var/lib/olamide-domain-ssl-repair/report.json` after the run. Domains are
processed sequentially and successful repairs remain when another domain fails.
The playbook exits unsuccessfully when any selected domain needs attention.
Backups and logs are under the timestamped directory recorded in the report.
Review and resolve the reported domain before rerunning; do not assume SSL
success establishes application identity on domains without a mapping.
