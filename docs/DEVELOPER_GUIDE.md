# OlamidePanel developer guide

## 1. Architecture and current boundaries

The application is a Python standard-library HTTP server behind Nginx, with buildless HTML/CSS/JavaScript and MySQL persistence through PyMySQL. The web process binds to `127.0.0.1:8090` and runs as the unprivileged `olamidepanel` Linux user. This is a foundation requiring production HTTP serving, OS tenant isolation, quotas, durable sessions/jobs and independent security validation before public shared hosting.

Request flow: browser → HTTPS Nginx → HTTP loopback API → session/CSRF/role/ownership checks → MySQL or account files → JSON response. No privileged hosting-service agent exists yet.

## 2. Source map

| Path | Responsibility |
|---|---|
| `panel/server.py` | HTTP routes, authorization, account lifecycle, file/domain/profile operations, bootstrap CLI |
| `panel/database.py` | Credential loading, PyMySQL connections, transaction adapter, schema initialization |
| `panel/schema.sql` | InnoDB schema |
| `panel/static/index.html` | Dashboard structure and dialogs |
| `panel/static/style.css` | Responsive layout, themes and component styling |
| `panel/static/app.js` | Navigation, API client, tools and account-management UI |
| `deploy/install.sh` | Fresh Debian 12 install |
| `deploy/olamidepanel.service` | Restricted systemd runtime |
| `deploy/migrate_sqlite.py` | Offline import into empty MySQL target |
| `ansible/configure-mysql.yml` | Existing local MySQL server provisioning |
| `ansible/register-users.yml` | Panel-account reconciliation |
| `tests/` | Adapter unit tests and opt-in MySQL application tests |
| `.github/workflows/mysql-tests.yml` | Disposable MySQL 8.4 CI service |

## 3. Development environment

Use Python 3.11+ and a disposable MySQL 8 database; do not test against production.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export PANEL_DB_CONFIG=/absolute/private/path/development-db.json
export PANEL_DATA="$PWD/.local-data"
export PANEL_SECURE_COOKIE=0
.venv/bin/python panel/server.py --create-admin developer
.venv/bin/python panel/server.py
```

The `developer` username is an example; the CLI creates a panel-root account and prompts for its password. Open http://127.0.0.1:8090. Disable secure cookies only for loopback development. Add `.venv/` to your local Git exclusions if needed; never commit virtual environments or credentials.

## 4. Configuration

| Setting | Default | Meaning |
|---|---|---|
| `PANEL_DATA` | `/var/lib/olamidepanel` | Account homes and retained files |
| `PANEL_DB_CONFIG` | `/etc/olamidepanel/database.json` | Protected MySQL JSON configuration |
| `PANEL_SECURE_COOKIE` | `1` | Secure cookie unless explicitly set to `0` |
| `--port` | `8090` | Loopback HTTP port |
| `--create-admin NAME` | None | Interactive bootstrap of panel-root account |
| `--provision-user` | False | Read one account JSON object from stdin |

Database JSON supports host, port, user, password, database, unix_socket and ssl_ca. Remote TCP hosts require a trusted TLS CA and certificate/hostname verification. Unix sockets or loopback are supported for local databases. Credentials are read for each connection. Runtime credentials must have only database-scoped privileges; the provisioning playbook uses separate operator credentials.

## 5. Persistence model

| Table | Fields / purpose |
|---|---|
| `user_ids` | Monotonic BIGINT AUTO_INCREMENT allocator; IDs remain reserved after user deletion |
| `users` | id, username, salt, password hash, role, active, email, display_name, session_version |
| `domains` | id, owner foreign key, unique domain name, creation timestamp |
| `audit` | id, actor, action text, creation timestamp |

Email/display names are metadata; there is no mail or notification integration. Domain records are inventory. Account files reside under `PANEL_DATA/homes/<id>` and are not public web roots.

Sessions are memory-resident token records. Each authenticated request rereads active/role/session_version from MySQL. Incrementing the version invalidates prior sessions. Cookies are HTTP-only, SameSite Strict and normally Secure. Sessions disappear on process restart; multiple independent workers would need shared session storage.

## 6. API contract

All bodies/responses use JSON unless a static asset is requested. Login returns a session cookie with an empty success body. Fetch `/api/me` after login to obtain CSRF and permission information. Mutating authenticated requests require `X-CSRF-Token` and the session cookie.

| Method | Route | Operation / body |
|---|---|---|
| POST | `/api/login` | username, password |
| POST | `/api/logout` | Empty object |
| GET | `/api/me` | Identity, role, CSRF token, permissions |
| GET | `/api/profile` | Own contact/role metadata |
| POST | `/api/profile` | email, display_name; optional password and current_password |
| GET | `/api/metrics` | Hostname, disk total/used, load averages |
| GET | `/api/domains` | Own inventory |
| POST | `/api/domains` | name |
| POST | `/api/domains/delete` | id, restricted to owner |
| GET | `/api/files?path=…` | Own directory list or text content |
| POST | `/api/files` | action, path; content for write; destination for rename/copy |
| GET | `/api/roles` | Assignable role definitions; requires users.manage |
| GET | `/api/users` | Account metadata list; requires users.manage |
| POST | `/api/users` | username, password, role |
| POST | `/api/users/update` | id, role, active boolean |
| POST | `/api/users/action` | id, action; profile/password/revoke_sessions/delete fields |
| GET | `/api/audit` | Latest 100 mutations; requires audit.read |

File actions: mkdir, write, rename, copy, delete. Account actions: profile (`email`, `display_name`), password (`password`), revoke_sessions, delete (`confirmation` matching username; target must be suspended).

Errors generally return `{ "error": "message" }`. Current routes use 400 for validation errors, 401 for unauthenticated requests, 403 for CSRF/selected permission failures, 404 for unknown/unavailable operations, 413 for oversized request bodies and 429 for login throttling. Error handling is not uniform across all database failures; do not treat every failure as a validation response.

## 7. Authorization rules

`ROLE_LEVELS` and `ROLE_PERMISSIONS` in server.py are authoritative. Read-only prohibits file/domain writes. Only root/super_admin have users.manage and audit.read. Creation may grant an equal or lower role; editing requires both target's existing role and desired role strictly below the actor. Self-edit through account-management routes is rejected. Local provisioning is an operator bootstrap mechanism and protects the last active root.

Never rely on hidden buttons as authorization. File ownership derives from authenticated user ID, not a client-provided owner. Domain queries always filter ownership. User deletion retains storage, deletes domain inventory, and must not recycle identity numbers.

## 8. Database adapter and migrations

`db()` returns a context manager that commits on success, rolls back on exception and closes the connection. Application SQL uses `?`; the narrow adapter converts these placeholders to `%s`. Do not introduce question marks in SQL literals/comments without replacing this simplistic translation. Values must always be passed separately.

The compatibility `BEGIN IMMEDIATE` operation starts a MySQL transaction and locks the current users table rows to serialize protected lifecycle operations. This is deliberately coarse and needs concurrency/load review. Schema initialization runs idempotent CREATE statements at startup; it is not a versioned schema-migration framework. MySQL DDL commits implicitly, so future upgrades need explicit migration design and backups.

The SQLite importer is the only code still reading SQLite. Stop the service, use an empty MySQL target and preserve original files; see the setup guide. Password hashes and identities are copied, not regenerated.

## 9. Tests and verification

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check panel/static/app.js
bash -n deploy/install.sh
```

Without live MySQL configuration, only the adapter tests run and the application test class is skipped. For integration tests:

```sh
export PANEL_TEST_MYSQL=1
export PANEL_DB_CONFIG=/absolute/private/path/disposable-test-db.json
.venv/bin/python -m unittest discover -s tests -v
```

Use a fresh empty database per run; the suite creates persistent fixture usernames. CI starts a fresh MySQL 8.4 container. Current tests cover authentication, CSRF, role limits, suspension, ownership/path boundaries, lifecycle operations, provisioning reconciliation and retained storage identity. Importer recovery, real Debian installation, browser interactions, load and concurrency need additional validation. A green syntax check is not browser verification.

## 10. Adding a real hosting module

1. Define what server/service change the module performs, its ownership model and its required privileges.
2. Add versioned schema changes and a reversible migration where needed.
3. Implement validation, server-side permissions, transactions and accurate errors.
4. For privileged operations, use a narrow allowlisted agent/job protocol; never give the HTTP process unrestricted sudo or accept shell command strings from users.
5. Connect forms and status views to the actual operation, including failures and rollback outcomes.
6. Test cross-account access, role restrictions, failure recovery and the real service integration.
7. Mark the catalog entry Available only after the implementation exists. Update these guides and the feature inventory.

Do not display vendor extensions as installed without their software/licensing and working adapters. Known unfinished systems include virtual hosts, DNS, mail, customer databases, backups, terminal, cron, quotas, MFA and billing.
