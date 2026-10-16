# Account files and two-factor authentication

## File manager and images

Open Files → File Manager. Upload individual files up to 8 MiB, download a file, create folders, edit UTF-8 text up to 1 MiB, rename/copy files or delete files/empty folders. The editor refuses oversized and binary files rather than truncating them. Upload overwrite requires a checked confirmation. Paths stay in the signed-in account's workspace; links and traversal are rejected.

Expand a file/folder's actions to compress a ZIP or extract an existing ZIP. Extraction requires a new destination directory and an existing parent. Only ZIP archives are supported. Expanded contents are limited to 64 MiB and 10,000 entries; links, encrypted archives, duplicate paths and special files are rejected. Extraction stages its output and removes incomplete output on error. Compression preserves empty directories. Operations serialize per account.

Files → Disk Usage reports actual workspace usage against an application-enforced 250 MiB / 10,000 file-and-directory limit. This is independent of marketplace plan labels. Existing over-limit accounts must remove files before adding data. It is not a kernel filesystem quota and does not cover external services. Each snapshot has a separate limit described below.

Files → Images resizes existing uploaded images while preserving aspect ratio and writes a new PNG/JPEG/WebP. Inputs are bounded to 8 MiB and 10 million pixels; output dimensions must be 1–4000. Original images remain intact. Animated images use their first frame; metadata is not preserved.

## Backup and restoration

Files → Backups, Backup Wizard and File Restoration share the same account-file snapshot workflow. Create up to five ZIP snapshots. Each snapshot is limited to 64 MiB of expanded files and 64 MiB compressed. Download, restore into a newly named `restored-*` folder, or explicitly confirm deletion. Restoration consumes normal workspace quota; existing files remain intact.

Snapshots live under `/var/lib/olamidepanel/backups/<user-id>`. These local copies do not protect against server loss. Back up panel MySQL, the data directory and configuration separately using the setup guide. These snapshots omit MySQL databases, mail, domain settings, external services and system configuration. Scheduling, incremental backups and full-account restoration remain unimplemented.

## Two-factor authentication

1. Open Security → Two-Factor Authentication and confirm your current password.
2. Add the displayed secret to an authenticator app as a time-based six-digit SHA-1 code with a 30-second period. Keep this secret private.
3. Enter your password and current authenticator code to enable protection.
4. Save the eight recovery codes offline. They appear once. Each code works once.
5. Sign in again with a fresh authenticator code or unused recovery code in the optional login code field.

Enable/disable revokes all account sessions. Disabling requires your password and a fresh code/recovery code. Previously used TOTP time steps cannot be reused. Server and authenticator clocks must be synchronized. Existing accounts remain password-only until enrolled; enforcement policies are not implemented.

Secrets are encrypted with the existing persistent `/etc/olamidepanel/payment.key` (also used for gateway credentials). Recovery codes are stored as hashes. Preserve this key with encrypted configuration backups; do not regenerate it on redeployment. Losing the key or all authenticator/recovery access requires operator recovery; there is no GUI bypass. Enrollment secrets/recovery codes are never written to the audit log. Password changes do not disable MFA.

## API and developer notes

Authenticated GET: `/api/storage/files?path=`, `/api/storage/download?path=`, `/api/storage/usage`, `/api/storage/backups`, `/api/storage/download?backup=`, `/api/mfa`.

Authenticated CSRF-protected POST: `/api/storage/files` actions `write`, `upload`, `mkdir`, `rename`, `copy`, `compress`, `extract`, `image`, `delete`; `/api/storage/backups` actions `create`, `restore`, `delete`; `/api/mfa` actions `setup`, `enable`, `disable`. Legacy `/api/files` routes use the same storage backend. MFA mutations require `current_password`; enable/disable also require `code`. Login accepts `mfa_code`.

`user_mfa` is created idempotently in MySQL. Verification locks the user's row before consuming a TOTP step or recovery code. File data remains on disk rather than SQL; ownership uses stable database user IDs. Uploads use bounded base64 JSON (12,000,000-byte API request cap, 16 MiB Nginx body cap). This implementation buffers bounded data in memory and is intended as a foundation, not a high-volume streaming storage system.

Validation: local storage tests cover cross-account isolation, traversal/links, overwrite confirmation, editor bounds, archive rejection/cleanup, quota, restore preservation and images. MFA unit tests use RFC 6238 test vectors; the MySQL integration suite covers enrollment, session invalidation and recovery-code reuse rejection. Live MySQL, browser and production checks must still run for this version.
