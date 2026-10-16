# OlamidePanel user manual

This manual describes the current repository implementation. OlamidePanel is a hosting-control-panel foundation, not a complete cPanel replacement. A tool being visible does not mean its hosting service is installed. The latest MySQL backend still needs live deployment verification.

## 1. Sign in and navigate

1. Open the HTTPS panel address supplied by your operator.
2. Enter the username and password created for you. There is no public signup or default password.
3. Use the sidebar to select a category. On mobile, scroll the category bar horizontally.
4. Search by tool name or category; press `/` to focus search when not editing a field.
5. Select a tool card to open its controls below the catalog.
6. Use Sign out when finished. Sessions last one hour and are lost when the service restarts.

Repeated failed logins can trigger a five-minute throttle. The current implementation sees requests through the same local reverse proxy, so this throttle can affect multiple users. If a session is revoked, suspended or expires, sign in again or contact your operator.

## 2. Personalize your workspace

| Control | What it does |
|---|---|
| Appearance button | Switches light/dark mode |
| Star on a tool | Adds/removes a favorite |
| All tools | Shows tools in the selected category |
| Available | Shows tools with connected functionality |
| Favorites | Shows your starred tools within the selected category |
| Search | Filters names and categories |
| Question-mark button | Opens the workspace guide |

Theme and favorites are stored in this browser, not your server account. Clear search or return to Overview if a favorite is not visible.

## 3. Understand feature status

- **Available:** connected application functionality exists.
- **Inventory only:** domain records are stored, but hosting/DNS are not configured.
- **Planned:** a catalog entry only. Opening it does not install or configure a service.

The dashboard shows host-wide disk usage, hostname and system load, not your account quota. Load is not CPU percentage. Readings refresh when the dashboard is loaded; there is no continuous monitoring or alert service yet.

## 4. Files → File Manager

Your account starts in its own panel storage directory. These are panel-managed files; no public website document root is provisioned automatically.

### Browse, create and edit

1. Open File Manager and select a folder to enter it; use Up to return.
2. Under Create folder, enter a folder name and save.
3. Under Create file, enter a path relative to the current folder and text contents.
4. Select a text file to open its editor; edit and save.

Individual writes and copies are limited to 1 MiB. Existing text reads show at most the first 1 MiB of characters; do not edit oversized files through this interface because saving could truncate them. Binary files are not supported by the text editor. There is no autosave, revision history or total account quota yet.

### Rename, copy and delete

1. Open the file's entry under File actions.
2. Select rename or copy and enter an unused destination path **relative to the account root**. The prefilled path includes the current folder.
3. Save the operation. Destination parent folders must already exist.
4. To delete, type the exact displayed file/folder name and select Delete.

Only empty folders can be deleted. File deletion is immediate; there is no Trash or undo. Account-scoped path checks reject paths outside your home. Read-only users cannot write, rename, copy or delete; the backend enforces this even if a write control is visible.

## 5. Domains → Domains

Enter a valid domain name to add it to your private inventory. Duplicate domains across accounts are rejected. Remove record deletes the inventory entry.

Adding a record does not change registrar settings, public DNS, Nginx virtual hosts, email routing or certificates. Ask the server operator to configure those services separately until their adapters are implemented.

## 6. Preferences

### Contact Information

Update your display name and contact email, then save. These fields do not yet send notification emails or provide password recovery.

### Password and Security

Enter your current password and a new password with at least 14 characters. Save; all sessions become invalid and you must sign in again. MFA, password-reset email and recovery codes are not implemented.

## 7. Administration → Access Control

Only panel root and super admin have user-management permissions.

| Role | Level | Current effective permissions |
|---|---:|---|
| root | 100 | User management, audit read, own files/domains, host metrics |
| super_admin | 90 | Same capabilities, with a lower management ceiling |
| admin | 70 | Own files/domains, host metrics |
| reseller | 50 | Own files/domains, host metrics |
| user | 20 | Own files/domains, host metrics |
| readonly | 10 | Read own files/domain inventory and host metrics |

Panel roles do not grant Linux accounts, root, sudo or SSH. Admin and reseller are hierarchy levels; delegated reseller ownership and server administration are not implemented.

### Create an account

1. Open Access Control or Create Panel User.
2. Enter a username: 3–32 lowercase letters, digits or underscores, beginning with a letter.
3. Enter a unique password with at least 14 characters.
4. Select an allowed access level and save.
5. Share credentials through your organization's secure process. The panel does not email credentials.

Creation permits a role at or below the actor's level. Subsequent management only permits strictly lower-level accounts. A root may create another root, but cannot edit that peer in this GUI. A super admin may create another super admin, but cannot edit that peer. Use operator-controlled local provisioning when peer changes are necessary.

### Manage an existing account

Search by username/role. For a lower-level account:

- Select a role and Save role.
- Suspend blocks sign-in and invalidates sessions; Restore permits future sign-in.
- Manage opens contact editing, password reset and Revoke all sessions.
- Resetting a password does not notify the user automatically.
- Your own account and peer/higher-level accounts are protected from this screen.

### Delete an account

Suspend it first, open Manage, type its exact username and delete. The user and its domain inventory are removed. Files remain on disk for operator retention/recovery; a new account does not inherit them. There is no GUI account-restore operation, and recreating the same username creates a new identity. Operators must use backups for full restoration.

## 8. Administration → Audit Log

View up to the latest 100 recorded mutations, with actor, action/target and timestamp. This is a basic audit viewer, not a complete security event system: not every login, denial or failed request is recorded, and export/filtering are not implemented.

## 9. Troubleshooting

| Symptom | Next step |
|---|---|
| Invalid credentials | Check username/password; ask a privileged user whether the account is suspended |
| Too many attempts | Wait five minutes; contact the operator if other users are also affected |
| Invalid CSRF token | Sign out or reload and sign in again |
| Read-only access | Request an appropriate role from a privileged user |
| Role cannot be changed | Target may be your own account or at/above your level |
| File operation rejected | Check destination, parent folder, size and account boundary |
| Domain does not load | Inventory does not provision a live website |
| Tool says Planned | That module is not operational |
| Page/API unavailable | Operator should check Nginx, service logs and MySQL connectivity |

Do not send passwords, private keys or full database configuration in support screenshots.

## Files, backups and authenticator protection

See [Files and MFA](FILES_AND_MFA.md) for uploads/downloads, archives, image tools, account usage, snapshot restoration and two-factor enrollment. Administration → Module Readiness lists every tool's actual implementation scope. See [Module audit](MODULE_AUDIT.md) for remaining work.

## Working tools and module requirements

The default filter is now Available. All tools still lists planned entries with their status. Opening an unfinished tool shows its implementation requirements and a return to working tools; it does not perform server changes. Administration → Module Readiness tracks outstanding backend work.

Advanced → Track DNS queries A, AAAA, CNAME, MX, NS, TXT, SOA and CAA records, with a four-second resolver timeout. It does not modify DNS zones.

Super admins can use User Manager, List Accounts, Suspended Accounts, Account Suspension, Account Termination and Resellers to search panel accounts and manage lower-level users through the existing MySQL user APIs. Account Termination lists suspended accounts; Manage account requires exact username confirmation for deletion. Files remain for operator recovery. These tools manage panel accounts, not Linux hosting users.
