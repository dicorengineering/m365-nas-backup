# Whole-mailbox recovery and Outlook exports

Available in alpha 7. There are three different recovery paths:

| Need | Use | Requires Microsoft access at recovery time? |
| --- | --- | --- |
| A few deleted or changed messages | Recovery → Review restore | Yes; restores into a new recovery folder |
| Rebuild all saved email in a replacement mailbox | Recovery → Review whole-mailbox recovery | Yes; an empty replacement mailbox and restore app |
| Open saved email without the tenant | Recovery → Export whole backup as EML ZIP | No, if that point contains saved portable copies |

An encrypted NAS recovery bundle is a fourth, separate feature: it moves this application's
repository to another installation. It is not a mail-client import file.
See [NAS/config recovery](RECOVERY.md).

## Rebuild a replacement mailbox

1. Upgrade to alpha 7 while keeping the existing config/data/exports volumes and encryption key.
2. Provision a replacement primary/shared mailbox in the same configured tenant. Provisioning,
   licensing, permissions, aliases and mail routing remain administrator tasks outside this app.
3. Keep the replacement unused and stop delivery into it while restoring. Remove any welcome/test
   email yourself if appropriate: the application requires an empty destination and never clears it.
   All supported email folders, including Deleted Items, must be empty.
4. Add its address to **Settings → Mailboxes**, configure the separate restore app and enable
   restoration. You can keep scheduling paused while performing disaster recovery. A destination
   already configured as disabled is also allowed; API settings support disabled mailboxes.
5. In **Recovery**, select the original **Email account** and the desired **Recovery point**.
   The original account does not have to exist or remain configured. No live comparison is needed.
6. Under **Whole-mailbox recovery & export**, choose **Replacement mailbox**. This is a separate
   choice from the destination for selected-message recovery.
7. Click **Review whole-mailbox recovery**. Read the mailbox, total message count and folder count.
   This includes the entire saved email tree regardless of search, filters or selected checkboxes.
8. Confirm. Follow **Whole-mailbox recovery jobs**, using **Refresh recovery progress & exports**
   or the console's periodic refresh. Leave the container running.
9. After success, check folder counts, representative old/sent/read messages and attachment
   contents in Outlook. Only then return the mailbox to normal use and mail delivery.

There is no 1,000-message selection limit for this operation. Imports run sequentially to limit
NAS memory use. They create new Exchange item IDs. The replacement must have a different mailbox
identity from the source snapshot; recreating the same address with a new identity is allowed.

Standard folders are mapped using Microsoft's locale-independent wellKnownName, so an Inbox
saved in one language can restore into a differently named Inbox. Custom folders retain their
saved parent hierarchy, including empty folders. Missing standard folders, cycles, ambiguous
names or unsupported non-email parents stop the plan. Parents outside the saved tree are treated
as mailbox-root placement; unexpected cases are shown in the preview. Existing older points
depend on the folder metadata actually saved at capture time; names alone are not reliable
identities for standard folders.

This recovers saved email, not an entire tenant or every mailbox setting. Contacts, calendars,
tasks, rules, permissions, aliases, retention/hold settings, online archives and tenant
configuration remain excluded. It is not an in-place rollback or a merge/deduplication tool.

## Failures, resume and retention

Every folder creation/import has a durable journal entry. Progress is saved after each confirmed
import; the whole result list is not repeatedly rewritten. A preflight verifies all Exchange
backup objects before creating folders or importing messages.

- **Failed:** a confirmed API rejection or failure before an uncertain write. Fix its cause,
  keep the destination unchanged, then choose **Review resume**. Confirmed imports are skipped.
  Resume verifies the mailbox identity, mapped folders and expected message counts first.
- **Uncertain:** a timeout, lost/malformed write response, or stopped process may have left a
  successful write in Exchange. The app blocks resume. Inspect the destination manually.
  Do not repeatedly launch the restore into it. For a clean restart, provision another empty
  replacement mailbox and create a new reviewed recovery job.
- **Abandon job:** permanently disables resume and releases the recovery point for ordinary
  retention cleanup. It does not remove imported mail or folders from Exchange.

Running, failed and uncertain whole-mailbox jobs pin their source point against cleanup.
Successful/abandoned jobs release the pin. Check pinned points if retention appears to retain
an older point unexpectedly. Unknown outcomes are deliberately not retried automatically.
Resume checks counts and structure; it cannot detect every external edit that keeps those
counts unchanged. Keep the destination isolated until completion.

Restore history and journals survive container recreation when /data is preserved.
The SQLite operational catalog contains mailbox identifiers, folder plans and progress;
protect the whole data volume even though message objects and manifests are encrypted.

## Save portable copies for future EML export

Opaque Exchange export data preserves Exchange properties but is not an EML or PST file.
Changing a filename cannot convert it. Portable copies are captured separately.

1. In Entra, grant the **backup application** Microsoft Graph **Application Mail.Read**
   with administrator consent, in addition to its existing permissions.
   User.Read.All is also used for exact message-ID translation. See [setup](MICROSOFT-SETUP.md).
2. In **Settings**, enable **Save MIME copies for EML exports** and save.
3. Run **Back up now**. Wait for a successful new recovery point.
4. Verify that point before depending on it for offline recovery.

The first enabled run captures portable copies for all current saved messages, including
unchanged messages omitted from delta responses. Later backups reuse unchanged copies and
capture new/changed versions. Captures are checked against the Exchange item version before
and after reading MIME. A mismatch, missing supported identity, permission failure or missing
MIME fails that mailbox's backup; the previous completed point and cursor remain intact.

The feature defaults off. It adds API calls, downloads and an additional encrypted representation
of each message, often substantial extra space. Transfers remain sequential. Overview's operation
details include mime_items and mime_downloaded_bytes. Disabling the option stops future capture;
copies already referenced by retained points stay available until normal retention removes them.

**It does not rewrite old points.** A deleted historical message without saved MIME cannot acquire
an authentic portable copy later. Restore that version to Exchange and export through Outlook.
Current newer versions must not be substituted for historical content.

## Download a whole mailbox or selected messages

1. Select an account and recovery point.
2. Choose **Export whole backup as EML ZIP**, or select up to 1,000 messages and choose
   **Export selected messages**. Whole-point export has no selection limit.
3. The preview checks coverage. If any requested item lacks saved MIME, the export is refused;
   it will not silently produce an incomplete mailbox archive.
4. Confirm creation of an **unencrypted ZIP**. The archive is written on disk in /exports,
   one message at a time; it is not built as a mailbox-sized memory buffer.
5. After completion, refresh the Downloads list and click **Download EML ZIP**.
6. Extract it to a protected local directory. Each message is an .eml file with MIME headers,
   body and attachments. index.json records folder identities, versions and SHA-256 checksums.
   Folder/file names are sanitized for Windows; very long paths go under Deep-folders and
   remain mapped in the index.
7. After verifying your download, **Delete export** removes the unencrypted NAS ZIP only.
   Retained backups remain intact. Exports do not automatically expire.

Downloads require the administrator session; Kuma's monitor token cannot access them.
Unpublished partial archives are removed after an error or on the next service startup.
Protect /exports and downloaded files as carefully as the original mailbox. Leave enough free
space for the archive in addition to the encrypted repository. A download is usable without
Microsoft or the NAS encryption key because it contains plaintext MIME.

## Classic Outlook for Windows and PST

An EML file can be opened as an individual message in a compatible Outlook installation.
An EML ZIP is **not** a PST file, and classic Outlook's PST import wizard cannot import it.
MIME does not preserve every Exchange-specific property; retain the original encrypted
Exchange backup for higher-fidelity server recovery.

For bulk recovery into classic Outlook's familiar PST format:

1. Complete the replacement-mailbox recovery above.
2. Add/open that Exchange mailbox in **classic Outlook for Windows**.
3. Ensure all restored mail is synchronized locally. With Cached Exchange Mode, set the
   download range to **All** and wait for folders to finish syncing before exporting.
4. Use **File → Open & Export → Import/Export → Export to a file → Outlook Data File (.pst)**.
5. Select the mailbox root and **Include subfolders**, then export to a new protected local file.
6. Verify by opening the PST in Outlook and checking folders and attachments.
   Use Outlook's PST import wizard when importing it into another mailbox.

Microsoft documents the [classic Outlook PST export process](https://support.microsoft.com/en-us/outlook/export-emails-contacts-and-calendar-items-to-outlook-using-a-pst-file)
and [PST import process](https://support.microsoft.com/en-us/outlook/import-email-contacts-and-calendar-from-an-outlook-pst-file).
These steps require a working Exchange destination for the intermediate restore.
The Linux/NAS app does not currently generate native PST files. A standalone Windows PST
conversion tool is not included. Neither live Exchange restoration nor classic Outlook
acceptance has been performed by the developer on your mail; test with disposable mail first.

## API additions

All routes require administrator authentication; mutations use X-M365-Request: 1.

| Route | Request / result |
| --- | --- |
| POST /api/mailbox-restore/preview | snapshot_id, destination; returns bound confirmation, folders and total |
| POST /api/mailbox-restore | snapshot_id, destination, confirmation; starts full restore |
| GET /api/mailbox-restore/jobs | Persistent jobs and progress |
| POST /api/mailbox-restore/jobs/{id}/resume | Empty JSON object; explicit safe resume |
| POST /api/mailbox-restore/jobs/{id}/abandon | Empty JSON object; releases retention pin |
| POST /api/exports/preview | snapshot_id; selections=null for whole point, or folder_id/item_id pairs |
| POST /api/exports | Same fields plus confirmation; starts ZIP creation |
| GET /api/exports | Completed export IDs, timestamps and sizes |
| GET /api/exports/{id}/download | Authenticated ZIP download |
| POST /api/exports/{id}/delete | Empty JSON object; deletes the generated ZIP |

Set M365_EXPORTS to a dedicated writable directory for non-container development.
The distributed container already has the persistent /exports volume.
