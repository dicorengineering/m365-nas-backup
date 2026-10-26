# Connect Microsoft 365

An Entra administrator must create/consent to the applications. This guide does not make tenant
changes automatically. Start with a test mailbox.

The alpha uses certificate-based application authentication in **Global Microsoft 365**.
Two single-tenant registrations keep backup credentials separate from restore access.
No user password, interactive user login, or EWS permission is required.

## Backup application

1. Sign in to the Microsoft Entra admin center for the intended tenant.
2. Open **App registrations → New registration**. Name it, for example, "M365 NAS Backup".
3. Select accounts in this organizational directory only. No redirect URI is needed.
4. Record the **Directory (tenant) ID** and **Application (client) ID**.
5. In the NAS console Settings, choose **Download backup certificate**.
6. Under **Certificates & secrets → Certificates**, upload `backup-public.pem`.
   Only upload the public certificate. Never share `backup-private.pem` in support messages.
7. Under **API permissions → Add a permission → Microsoft Graph → Application permissions**,
   add the permissions below and grant administrator consent.
8. Enter the tenant ID and backup application ID in the NAS console.

| Application permission | Purpose |
| --- | --- |
| `User.Read.All` | Resolve configured users' primary/shared mailbox identifiers |
| `MailboxFolder.Read.All` | Read folder structure |
| `MailboxItem.Read.All` | Track changes and read metadata |
| `MailboxItem.Export.All` | Export Exchange item data |

These permission names belong to the newer Exchange mailbox APIs; ordinary `Mail.Read`
alone is insufficient. Check availability and policies in your tenant. If a required permission
is unavailable, stop setup and investigate; do not substitute broad permissions experimentally.

## Separate restore application

Create another single-tenant registration, for example "M365 NAS Restore":

1. Download **restore certificate** from the NAS console.
2. Upload `restore-public.pem` to this second registration.
3. Grant these Microsoft Graph **Application** permissions and admin consent:

| Application permission | Purpose |
| --- | --- |
| `User.Read.All` | Resolve the destination mailbox |
| `MailboxFolder.ReadWrite.All` | Create recovery folders |
| `MailboxItem.ImportExport.All` | Create import sessions/import saved items |

4. Enter its client ID in **Restore application ID**.
5. Enable restoration when ready to test. Keep the first app ID for backups.

These are powerful permissions. The app mailbox list controls what this software processes;
it is **not** a tenant-enforced permission boundary. Do not assume legacy application access
policies or Exchange RBAC cover the newer `MailboxItem.*` permissions without checking
Microsoft's current support and testing denial for an out-of-scope mailbox.
The alpha does not automate consent, RBAC provisioning, or permission scoping.

## Mailbox selection

Enter a mailbox email address/UPN or Entra user object ID per line. List shared mailboxes
separately. Aliases are not separate backups. Online archives are excluded.
Each installation handles one tenant; separate installations/data directories are needed for
different tenants. Save and run a manual backup before enabling scheduling.

## Certificates and renewal

The app generates separate RSA certificates valid for one year. Private keys remain in
`config/`. Record expiry dates from Entra and set an administrator reminder. Certificate-expiry
alerts and a renewal wizard are not implemented.

To renew, stop the app, securely back up configuration, and move the **matching** public/private
pair for that application to a protected location. Restarting generates a new pair only if both
files are absent. Download/upload the new public certificate in Entra. Keep the old certificate
there until authentication with the replacement succeeds, then remove it.

Do not replace `encryption.key`; the encryption key and application certificates are unrelated.
For rollback, stop the app and restore the original matching pair. A single missing certificate
file causes an error instead of silent regeneration.

## Official references

- [Mailbox discovery/User.Read.All](https://learn.microsoft.com/en-us/graph/api/usersettings-list-exchange?view=graph-rest-1.0)
- [Folder permissions](https://learn.microsoft.com/en-us/graph/api/mailbox-list-folders?view=graph-rest-1.0)
- [Change tracking permissions](https://learn.microsoft.com/en-us/graph/api/mailboxitem-delta?view=graph-rest-1.0)
- [Export permissions](https://learn.microsoft.com/en-us/graph/api/mailbox-exportitems?view=graph-rest-1.0)
- [Import sequence](https://learn.microsoft.com/en-us/graph/import-exchange-mailbox-item)

Verified against official documentation during alpha development, 2026-10-25.
