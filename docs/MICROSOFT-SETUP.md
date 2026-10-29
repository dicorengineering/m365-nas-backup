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
| `MailboxItem.Read.All` | Whole-mailbox recovery: read destination items if folder counts are omitted |

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

New installations generate separate one-year RSA certificates. They cannot be indefinite.
Settings shows active/pending local expiry, and Overview warns within 45 days of local expiry.
The expiration registered in Entra may be earlier; record and monitor that date separately.
These console warnings do not change the Kuma backup-freshness response.

To renew or request a longer local lifetime, use **Settings → Certificate renewal**:

1. Back up configuration. Choose Backup or Restore and validity in days (default 365, maximum 3,650).
2. Click **Prepare replacement**, then **Download replacement**. Existing authentication continues.
3. Upload the replacement public PEM in the matching Entra app's **Certificates & secrets**.
   Keep the old certificate registered. Check the expiration Entra actually accepts.
4. Click **Test and activate replacement** and confirm. The app requests an authentication token
   using that exact replacement before switching. If this fails, the current certificate stays active.
5. Check Overview for success and run a backup (or an authorized test restore for the restore app).
   Back up configuration again. Remove the old registration after successful validation.

Longer local validity does not override Microsoft restrictions: [Microsoft's Graph credential
registration guide](https://learn.microsoft.com/en-us/graph/applications-how-to-add-certificate)
documents a maximum of one year for that registration method, and [tenant policies](https://learn.microsoft.com/en-us/graph/api/resources/keycredentialconfiguration?view=graph-rest-1.0)
can restrict certificate lifetime further. Do not assume a ten-year PEM means ten years of Entra
access. If Entra rejects the requested duration, prepare one with a permitted shorter lifetime.

Renewal reuses that application's private key and leaves the unrelated backup encryption key
unchanged. This is a validity renewal, not key rotation after compromise. The previous public
certificate is saved as backup-previous-public.pem or restore-previous-public.pem; with the app
stopped it can replace the active public file for rollback while its Entra registration remains
valid. Never replace encryption.key. Private keys and tokens are never downloaded by these controls.

## Official references

- [Mailbox discovery/User.Read.All](https://learn.microsoft.com/en-us/graph/api/usersettings-list-exchange?view=graph-rest-1.0)
- [Folder permissions](https://learn.microsoft.com/en-us/graph/api/mailbox-list-folders?view=graph-rest-1.0)
- [Change tracking permissions](https://learn.microsoft.com/en-us/graph/api/mailboxitem-delta?view=graph-rest-1.0)
- [Export permissions](https://learn.microsoft.com/en-us/graph/api/mailbox-exportitems?view=graph-rest-1.0)
- [Import sequence](https://learn.microsoft.com/en-us/graph/import-exchange-mailbox-item)

Verified against official documentation during alpha development, 2026-10-25.

## Optional portable EML capture (alpha 7)

For **Save MIME copies for EML exports**, add Microsoft Graph **Application Mail.Read** to
the **backup** registration and grant administrator consent. Keep its existing permissions;
Mail.Read does not replace MailboxItem.Export.All. User.Read.All already granted above is
also used to translate exact message IDs. The restore app does not need Mail.Read for EML.

Do this before enabling portable copies in Settings. The next successful backup captures
current message MIME, including unchanged messages; old recovery points remain unchanged.
Tenant consent/scoping is an administrator task and is not automated by this application.
See [portable-copy instructions](MAILBOX-RECOVERY.md#save-portable-copies-for-future-eml-export),
[Graph message MIME](https://learn.microsoft.com/en-us/graph/api/message-get?view=graph-rest-1.0)
and [ID translation permissions](https://learn.microsoft.com/en-us/graph/api/user-translateexchangeids?view=graph-rest-1.0).

For whole-mailbox recovery, destination folder reads use the existing folder permission.
MailboxItem.Read.All allows the emptiness/count fallback when Microsoft omits folder counts.
Existing selected-message restoration otherwise keeps its existing permissions.
