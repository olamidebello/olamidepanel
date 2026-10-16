# Module-by-module implementation audit

Reviewed 2026-10-16 against source, not a live server certification. Each named GUI tool is listed below. “Implemented” is limited to the stated scope; “partial” exposes working operations alongside explicit gaps. Unit checks passed locally; MySQL integration, browser and production deployment checks remain unconfirmed for this batch.

176 tools: 9 implemented in the stated scope, 18 partial, 149 not implemented.

Ansible installs and configures existing code and prerequisites; it cannot generate or complete missing service adapters. Planned cards remain marked Planned. The admin Module Readiness screen exposes this same inventory.

## Marketplace

| Tool | State | Source / API | Scope or missing implementation |
|---|---|---|---|
| Marketplace Dashboard | partial | panel/marketplace.py; panel/schema.sql / /api/marketplace/* | Persistent plans, orders, store profiles, role-based navigation, vendor approval and store ownership. No automated Linux account fulfillment, metering, recurring billing or payouts. |
| Hosting Plans | partial | panel/marketplace.py; panel/schema.sql / /api/marketplace/* | Persistent plans, orders, store profiles, role-based navigation, vendor approval and store ownership. No automated Linux account fulfillment, metering, recurring billing or payouts. |
| Browse Stores | partial | panel/marketplace.py; panel/schema.sql / /api/marketplace/* | Persistent plans, orders, store profiles, role-based navigation, vendor approval and store ownership. No automated Linux account fulfillment, metering, recurring billing or payouts. |
| My Orders | partial | panel/marketplace.py; panel/schema.sql / /api/marketplace/* | Persistent plans, orders, store profiles, role-based navigation, vendor approval and store ownership. No automated Linux account fulfillment, metering, recurring billing or payouts. |
| Reseller Catalog | partial | panel/marketplace.py; panel/schema.sql / /api/marketplace/* | Persistent plans, orders, store profiles, role-based navigation, vendor approval and store ownership. No automated Linux account fulfillment, metering, recurring billing or payouts. |
| Store Orders | partial | panel/marketplace.py; panel/schema.sql / /api/marketplace/* | Persistent plans, orders, store profiles, role-based navigation, vendor approval and store ownership. No automated Linux account fulfillment, metering, recurring billing or payouts. |
| Store Settings | partial | panel/marketplace.py; panel/schema.sql / /api/marketplace/* | Persistent plans, orders, store profiles, role-based navigation, vendor approval and store ownership. No automated Linux account fulfillment, metering, recurring billing or payouts. |
| Payment Gateways | partial | panel/payments.py / /api/payments/gateways | Scoped merchant settings, encrypted credentials; Stripe and Paystack hosted checkout adapters. Other providers unsupported; merchant testing required. |
| Payments | partial | panel/payments.py / /api/payments/transactions; /api/payments/checkout | Signed webhooks and verified one-time payments. No subscriptions, refunds, tax engine or automatic hosting provisioning. |

## Files

| Tool | State | Source / API | Scope or missing implementation |
|---|---|---|---|
| File Manager | partial | panel/storage.py / /api/storage/files; /api/storage/download | Create/edit/upload/download/copy/rename/delete and ZIP. No permissions editor, HTML editor, trash or shared hosting filesystem. |
| Images | implemented | panel/storage.py / /api/storage/files action=image | Bounded aspect-preserving PNG/JPEG/WEBP resizing/conversion; input 8 MiB, 10 million pixels. |
| Directory Privacy | not implemented | panel/static/app.js (planned card only) / None | Missing isolated FTP/WebDAV/Git or directory-access service adapter and corresponding API/GUI workflow. |
| Disk Usage | implemented | panel/storage.py / /api/storage/usage | Account workspace bytes and file/directory count. 250 MiB application limit; not a Linux hosting-package quota. |
| FTP Accounts | not implemented | panel/static/app.js (planned card only) / None | Missing isolated FTP/WebDAV/Git or directory-access service adapter and corresponding API/GUI workflow. |
| FTP Connections | not implemented | panel/static/app.js (planned card only) / None | Missing isolated FTP/WebDAV/Git or directory-access service adapter and corresponding API/GUI workflow. |
| Anonymous FTP | not implemented | panel/static/app.js (planned card only) / None | Missing isolated FTP/WebDAV/Git or directory-access service adapter and corresponding API/GUI workflow. |
| Web Disk | not implemented | panel/static/app.js (planned card only) / None | Missing isolated FTP/WebDAV/Git or directory-access service adapter and corresponding API/GUI workflow. |
| Git Version Control | not implemented | panel/static/app.js (planned card only) / None | Missing isolated FTP/WebDAV/Git or directory-access service adapter and corresponding API/GUI workflow. |
| Git Deployment | not implemented | panel/static/app.js (planned card only) / None | Missing isolated FTP/WebDAV/Git or directory-access service adapter and corresponding API/GUI workflow. |
| Backups | partial | panel/storage.py / /api/storage/backups; /api/storage/download | Manual account-file ZIP snapshots, five maximum, 64 MiB expanded limit; restore into new folder. No MySQL/mail/full-account backup or schedules. |
| Backup Wizard | partial | panel/storage.py / /api/storage/backups; /api/storage/download | Manual account-file ZIP snapshots, five maximum, 64 MiB expanded limit; restore into new folder. No MySQL/mail/full-account backup or schedules. |
| File Restoration | partial | panel/storage.py / /api/storage/backups; /api/storage/download | Manual account-file ZIP snapshots, five maximum, 64 MiB expanded limit; restore into new folder. No MySQL/mail/full-account backup or schedules. |

## Domains

| Tool | State | Source / API | Scope or missing implementation |
|---|---|---|---|
| Domains | partial | panel/server.py; panel/websites.py / /api/domains; /api/websites | Owned domain inventory. DNS-verified static publishing is separate; no authoritative zone editor or general web hosting. |
| Redirects | not implemented | panel/static/app.js (planned card only) / None | Missing DNS/provider integration or site-builder/social/SEO adapter, credentials and end-to-end workflow. |
| DNS Zone Editor | not implemented | panel/static/app.js (planned card only) / None | Missing DNS/provider integration or site-builder/social/SEO adapter, credentials and end-to-end workflow. |
| Dynamic DNS | not implemented | panel/static/app.js (planned card only) / None | Missing DNS/provider integration or site-builder/social/SEO adapter, credentials and end-to-end workflow. |
| Site Publisher | partial | panel/websites.py; deploy/provision_websites.py / /api/websites | Static template publication using TXT ownership and IPv4 checks, Nginx and Certbot worker. Needs live worker/DNS verification. |
| Site Builder | not implemented | panel/static/app.js (planned card only) / None | Missing DNS/provider integration or site-builder/social/SEO adapter, credentials and end-to-end workflow. |
| SEO | not implemented | panel/static/app.js (planned card only) / None | Missing DNS/provider integration or site-builder/social/SEO adapter, credentials and end-to-end workflow. |
| Social Media | not implemented | panel/static/app.js (planned card only) / None | Missing DNS/provider integration or site-builder/social/SEO adapter, credentials and end-to-end workflow. |

## Email

| Tool | State | Source / API | Scope or missing implementation |
|---|---|---|---|
| Email Accounts | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Forwarders | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Domain Forwarders | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Autoresponders | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Default Address | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Email Routing | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Email Filters | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Global Filters | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Email Deliverability | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Email Disk Usage | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Address Importer | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Archive | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Mailing Lists | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| BoxTrapper | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Greylisting | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Encryption | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Calendars and Contacts | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Calendar Sharing | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Calendar Delegation | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Spam Filters | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Track Delivery | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |
| Webmail | not implemented | panel/static/app.js (planned card only) / None | Missing mail tenancy, MTA/IMAP provisioning, storage quotas, authenticated webmail and corresponding API/GUI workflow. |

## Databases

| Tool | State | Source / API | Scope or missing implementation |
|---|---|---|---|
| Database Manager | not implemented | panel/static/app.js (planned card only) / None | Only the internal panel MySQL database exists. Missing tenant database/user/privilege broker and GUI operations. |
| Database Users | not implemented | panel/static/app.js (planned card only) / None | Only the internal panel MySQL database exists. Missing tenant database/user/privilege broker and GUI operations. |
| Database Wizard | not implemented | panel/static/app.js (planned card only) / None | Only the internal panel MySQL database exists. Missing tenant database/user/privilege broker and GUI operations. |
| phpMyAdmin | not implemented | panel/static/app.js (planned card only) / None | Only the internal panel MySQL database exists. Missing tenant database/user/privilege broker and GUI operations. |
| Remote Database Access | not implemented | panel/static/app.js (planned card only) / None | Only the internal panel MySQL database exists. Missing tenant database/user/privilege broker and GUI operations. |
| PostgreSQL | not implemented | panel/static/app.js (planned card only) / None | Only the internal panel MySQL database exists. Missing tenant database/user/privilege broker and GUI operations. |
| PostgreSQL Wizard | not implemented | panel/static/app.js (planned card only) / None | Only the internal panel MySQL database exists. Missing tenant database/user/privilege broker and GUI operations. |
| phpPgAdmin | not implemented | panel/static/app.js (planned card only) / None | Only the internal panel MySQL database exists. Missing tenant database/user/privilege broker and GUI operations. |

## Security

| Tool | State | Source / API | Scope or missing implementation |
|---|---|---|---|
| SSH Access | not implemented | panel/static/app.js (planned card only) / None | Missing tested SSH/TLS/WAF/firewall/token or other security adapter with account-scoped authorization. |
| IP Blocker | not implemented | panel/static/app.js (planned card only) / None | Missing tested SSH/TLS/WAF/firewall/token or other security adapter with account-scoped authorization. |
| SSL/TLS | not implemented | panel/static/app.js (planned card only) / None | Missing tested SSH/TLS/WAF/firewall/token or other security adapter with account-scoped authorization. |
| Private Keys | not implemented | panel/static/app.js (planned card only) / None | Missing tested SSH/TLS/WAF/firewall/token or other security adapter with account-scoped authorization. |
| Certificate Signing Requests | not implemented | panel/static/app.js (planned card only) / None | Missing tested SSH/TLS/WAF/firewall/token or other security adapter with account-scoped authorization. |
| Certificates | not implemented | panel/static/app.js (planned card only) / None | Missing tested SSH/TLS/WAF/firewall/token or other security adapter with account-scoped authorization. |
| SSL Sites | not implemented | panel/static/app.js (planned card only) / None | Missing tested SSH/TLS/WAF/firewall/token or other security adapter with account-scoped authorization. |
| SSL Status | not implemented | panel/static/app.js (planned card only) / None | Missing tested SSH/TLS/WAF/firewall/token or other security adapter with account-scoped authorization. |
| AutoSSL | not implemented | panel/static/app.js (planned card only) / None | Missing tested SSH/TLS/WAF/firewall/token or other security adapter with account-scoped authorization. |
| ModSecurity | not implemented | panel/static/app.js (planned card only) / None | Missing tested SSH/TLS/WAF/firewall/token or other security adapter with account-scoped authorization. |
| Hotlink Protection | not implemented | panel/static/app.js (planned card only) / None | Missing tested SSH/TLS/WAF/firewall/token or other security adapter with account-scoped authorization. |
| Leech Protection | not implemented | panel/static/app.js (planned card only) / None | Missing tested SSH/TLS/WAF/firewall/token or other security adapter with account-scoped authorization. |
| Two-Factor Authentication | implemented | panel/mfa.py; panel/schema.sql / /api/mfa; /api/login | TOTP enrollment/verification, encrypted secrets, replay checks, single-use recovery codes, password-confirmed changes and session revocation. |
| API Tokens | not implemented | panel/static/app.js (planned card only) / None | Missing tested SSH/TLS/WAF/firewall/token or other security adapter with account-scoped authorization. |
| Security Policy | not implemented | panel/static/app.js (planned card only) / None | Missing tested SSH/TLS/WAF/firewall/token or other security adapter with account-scoped authorization. |

## Software

| Tool | State | Source / API | Scope or missing implementation |
|---|---|---|---|
| PHP Manager | not implemented | panel/static/app.js (planned card only) / None | Missing isolated runtime/build worker, package/runtime lifecycle and matching API/GUI operations. |
| PHP-FPM | not implemented | panel/static/app.js (planned card only) / None | Missing isolated runtime/build worker, package/runtime lifecycle and matching API/GUI operations. |
| PHP INI Editor | not implemented | panel/static/app.js (planned card only) / None | Missing isolated runtime/build worker, package/runtime lifecycle and matching API/GUI operations. |
| Application Manager | not implemented | panel/static/app.js (planned card only) / None | Missing isolated runtime/build worker, package/runtime lifecycle and matching API/GUI operations. |
| Environment Variables | not implemented | panel/static/app.js (planned card only) / None | Missing isolated runtime/build worker, package/runtime lifecycle and matching API/GUI operations. |
| Application Dependencies | not implemented | panel/static/app.js (planned card only) / None | Missing isolated runtime/build worker, package/runtime lifecycle and matching API/GUI operations. |
| Optimize Website | not implemented | panel/static/app.js (planned card only) / None | Missing isolated runtime/build worker, package/runtime lifecycle and matching API/GUI operations. |
| Perl Modules | not implemented | panel/static/app.js (planned card only) / None | Missing isolated runtime/build worker, package/runtime lifecycle and matching API/GUI operations. |
| PEAR Packages | not implemented | panel/static/app.js (planned card only) / None | Missing isolated runtime/build worker, package/runtime lifecycle and matching API/GUI operations. |
| RubyGems | not implemented | panel/static/app.js (planned card only) / None | Missing isolated runtime/build worker, package/runtime lifecycle and matching API/GUI operations. |
| Ruby on Rails | not implemented | panel/static/app.js (planned card only) / None | Missing isolated runtime/build worker, package/runtime lifecycle and matching API/GUI operations. |
| Application Installer | not implemented | panel/static/app.js (planned card only) / None | Missing isolated runtime/build worker, package/runtime lifecycle and matching API/GUI operations. |

## Metrics

| Tool | State | Source / API | Scope or missing implementation |
|---|---|---|---|
| Server Metrics | partial | panel/server.py / /api/metrics | Real host disk totals/load/hostname. No historical traffic, per-tenant CPU accounting or uptime alerting. |
| Visitors | not implemented | panel/static/app.js (planned card only) / None | Missing scoped log/statistics collection, retention, query backend and matching UI. |
| Errors | not implemented | panel/static/app.js (planned card only) / None | Missing scoped log/statistics collection, retention, query backend and matching UI. |
| Bandwidth | not implemented | panel/static/app.js (planned card only) / None | Missing scoped log/statistics collection, retention, query backend and matching UI. |
| Raw Access | not implemented | panel/static/app.js (planned card only) / None | Missing scoped log/statistics collection, retention, query backend and matching UI. |
| AWStats | not implemented | panel/static/app.js (planned card only) / None | Missing scoped log/statistics collection, retention, query backend and matching UI. |
| Analog Stats | not implemented | panel/static/app.js (planned card only) / None | Missing scoped log/statistics collection, retention, query backend and matching UI. |
| Webalizer | not implemented | panel/static/app.js (planned card only) / None | Missing scoped log/statistics collection, retention, query backend and matching UI. |
| FTP Statistics | not implemented | panel/static/app.js (planned card only) / None | Missing scoped log/statistics collection, retention, query backend and matching UI. |
| Metrics Editor | not implemented | panel/static/app.js (planned card only) / None | Missing scoped log/statistics collection, retention, query backend and matching UI. |
| Resource Usage | not implemented | panel/static/app.js (planned card only) / None | Missing scoped log/statistics collection, retention, query backend and matching UI. |
| Site Monitoring | not implemented | panel/static/app.js (planned card only) / None | Missing scoped log/statistics collection, retention, query backend and matching UI. |

## Advanced

| Tool | State | Source / API | Scope or missing implementation |
|---|---|---|---|
| Terminal | not implemented | panel/static/app.js (planned card only) / None | Missing tenant isolation and constrained service broker or network/cron/scan adapter with matching API/GUI operations. |
| Cron Jobs | not implemented | panel/static/app.js (planned card only) / None | Missing tenant isolation and constrained service broker or network/cron/scan adapter with matching API/GUI operations. |
| Track DNS | not implemented | panel/static/app.js (planned card only) / None | Missing tenant isolation and constrained service broker or network/cron/scan adapter with matching API/GUI operations. |
| Indexes | not implemented | panel/static/app.js (planned card only) / None | Missing tenant isolation and constrained service broker or network/cron/scan adapter with matching API/GUI operations. |
| Error Pages | not implemented | panel/static/app.js (planned card only) / None | Missing tenant isolation and constrained service broker or network/cron/scan adapter with matching API/GUI operations. |
| Apache Handlers | not implemented | panel/static/app.js (planned card only) / None | Missing tenant isolation and constrained service broker or network/cron/scan adapter with matching API/GUI operations. |
| MIME Types | not implemented | panel/static/app.js (planned card only) / None | Missing tenant isolation and constrained service broker or network/cron/scan adapter with matching API/GUI operations. |
| API Shell | not implemented | panel/static/app.js (planned card only) / None | Missing tenant isolation and constrained service broker or network/cron/scan adapter with matching API/GUI operations. |
| Virus Scanner | not implemented | panel/static/app.js (planned card only) / None | Missing tenant isolation and constrained service broker or network/cron/scan adapter with matching API/GUI operations. |

## Preferences

| Tool | State | Source / API | Scope or missing implementation |
|---|---|---|---|
| Password and Security | implemented | panel/server.py; panel/schema.sql / /api/profile; /api/users; /api/users/update; /api/audit | Panel account/profile/password/role and audit operations only; panel root does not grant Linux root. |
| Language | not implemented | panel/static/app.js (planned card only) / None | Missing corresponding persisted settings or team membership model, authorization and GUI workflow. |
| Contact Information | implemented | panel/server.py; panel/schema.sql / /api/profile; /api/users; /api/users/update; /api/audit | Panel account/profile/password/role and audit operations only; panel root does not grant Linux root. |
| Account Preferences | not implemented | panel/static/app.js (planned card only) / None | Missing corresponding persisted settings or team membership model, authorization and GUI workflow. |
| User Manager | not implemented | panel/static/app.js (planned card only) / None | Missing corresponding persisted settings or team membership model, authorization and GUI workflow. |
| Manage Team | not implemented | panel/static/app.js (planned card only) / None | Missing corresponding persisted settings or team membership model, authorization and GUI workflow. |

## Administration

| Tool | State | Source / API | Scope or missing implementation |
|---|---|---|---|
| Module Readiness | implemented | panel/modules.py; panel/module-audit.json / /api/modules | Per-module and per-tool implementation inventory; deployment readiness still requires live verification. |
| Reseller Access | partial | panel/marketplace.py; panel/schema.sql / /api/marketplace/* | Persistent plans, orders, store profiles, role-based navigation, vendor approval and store ownership. No automated Linux account fulfillment, metering, recurring billing or payouts. |
| Hosting Catalog | partial | panel/marketplace.py; panel/schema.sql / /api/marketplace/* | Persistent plans, orders, store profiles, role-based navigation, vendor approval and store ownership. No automated Linux account fulfillment, metering, recurring billing or payouts. |
| Access Control | implemented | panel/server.py; panel/schema.sql / /api/profile; /api/users; /api/users/update; /api/audit | Panel account/profile/password/role and audit operations only; panel root does not grant Linux root. |
| Create Panel User | implemented | panel/server.py; panel/schema.sql / /api/profile; /api/users; /api/users/update; /api/audit | Panel account/profile/password/role and audit operations only; panel root does not grant Linux root. |
| Audit Log | implemented | panel/server.py; panel/schema.sql / /api/profile; /api/users; /api/users/update; /api/audit | Panel account/profile/password/role and audit operations only; panel root does not grant Linux root. |
| List Accounts | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Suspended Accounts | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Account Provisioning | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Account Suspension | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Account Termination | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Shell Access | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| IP Assignment | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Bandwidth Limits | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Packages | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Feature Manager | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Resellers | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Server Configuration | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Hostname and Resolvers | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| IP Management | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| DNS Zones | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| DNS Templates | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| DNS Cluster | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Configuration Cluster | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Backup Configuration | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Backup Restoration | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Account Transfers | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Apache Configuration | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| PHP Configuration | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Mail Configuration | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| FTP Configuration | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Service Manager | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Log Rotation | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Package Management | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Database Services | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Mail Queue | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Delivery Reports | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Brute Force Protection | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Host Access Control | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Compiler Access | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Service Certificates | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Process Manager | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Task Queue | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Service Restarts | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| System Reboot | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Contact Manager | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Hooks | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Plugins | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Branding | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Themes and Locales | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |
| Support | not implemented | panel/static/app.js (planned card only) / None | Missing OS-level account/service/resource management adapter, scoped authorization and matching GUI workflow. Existing Access Control manages panel accounts only. |

## Integrations

| Tool | State | Source / API | Scope or missing implementation |
|---|---|---|---|
| WP Toolkit | not implemented | panel/static/app.js (planned card only) / None | Missing provider software/license or API credentials plus tested integration and GUI workflow. |
| Softaculous | not implemented | panel/static/app.js (planned card only) / None | Missing provider software/license or API credentials plus tested integration and GUI workflow. |
| CloudLinux | not implemented | panel/static/app.js (planned card only) / None | Missing provider software/license or API credentials plus tested integration and GUI workflow. |
| LiteSpeed | not implemented | panel/static/app.js (planned card only) / None | Missing provider software/license or API credentials plus tested integration and GUI workflow. |
| JetBackup | not implemented | panel/static/app.js (planned card only) / None | Missing provider software/license or API credentials plus tested integration and GUI workflow. |
| Comet Backup | not implemented | panel/static/app.js (planned card only) / None | Missing provider software/license or API credentials plus tested integration and GUI workflow. |
| Imunify | not implemented | panel/static/app.js (planned card only) / None | Missing provider software/license or API credentials plus tested integration and GUI workflow. |
| External DNS/CDN | not implemented | panel/static/app.js (planned card only) / None | Missing provider software/license or API credentials plus tested integration and GUI workflow. |
| Billing | not implemented | panel/static/app.js (planned card only) / None | Missing provider software/license or API credentials plus tested integration and GUI workflow. |
| External Monitoring | not implemented | panel/static/app.js (planned card only) / None | Missing provider software/license or API credentials plus tested integration and GUI workflow. |
| AI Services | not implemented | panel/static/app.js (planned card only) / None | Missing provider software/license or API credentials plus tested integration and GUI workflow. |

## Next implementation dependencies

1. Establish a constrained privileged broker and Linux tenant isolation before customer database provisioning, web runtimes, mail, FTP, terminal or service controls.
2. Add tenant database provisioning with MySQL integration tests; keep internal panel database credentials isolated.
3. Add authoritative DNS and mailbox lifecycle adapters with ownership checks and real service integration tests.
4. Add runtime/Git deployment workers, scheduling, retention and full recovery drills.
5. Add optional licensed integrations only after provider installation, licensing and sandbox validation.

These are outstanding engineering tasks, not actions performed by the installation playbook.
