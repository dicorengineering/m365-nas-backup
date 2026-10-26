# How restoration works

Research checked 2026-10-25. This describes documented mechanisms, not every provider's internals
or a guarantee that the alpha has passed live restore testing.

## Commercial evidence

Veeam documents `MailboxItem.Export.All` for backup and `MailboxItem.ImportExport.All` for
restore, together with mailbox item/folder permissions in current Microsoft 365 guidance.
This is evidence of the newer Graph Exchange APIs in a commercial approach:
[Veeam upgrade permission checks](https://helpcenter.veeam.com/docs/vbo365/guide/vbo_upgrade_app_permissions_check.html),
[Veeam application permissions](https://helpcenter.veeam.com/docs/vbo365/guide/ad_app_permissions_sd.html).

Boxafe/HDP internals have not been verified. Marketing alone does not establish API/fidelity.

## Chosen mechanism

Microsoft's [Exchange import/export overview](https://learn.microsoft.com/en-us/graph/api/resources/mailbox-import-export-api-overview?view=graph-rest-1.0)
describes opaque Exchange item export/import, but also says the APIs are not designed for backup.
That qualification remains material: commercial use is not an availability, performance or support
guarantee for this app.

The alpha uses:

1. [Mailbox discovery](https://learn.microsoft.com/en-us/graph/api/usersettings-list-exchange?view=graph-rest-1.0)
   for primary/shared mailbox identifiers.
2. Folder enumeration and
   [incremental change tracking](https://learn.microsoft.com/en-us/graph/api/mailboxitem-delta?view=graph-rest-1.0).
3. [ExportItems](https://learn.microsoft.com/en-us/graph/api/mailbox-exportitems?view=graph-rest-1.0)
   in batches of at most 20, storing opaque decoded data encrypted on the NAS.
4. [Import sessions](https://learn.microsoft.com/en-us/graph/import-exchange-mailbox-item)
   to create new items from saved data in a recovery folder. No bearer token is sent to the
   preauthenticated import URL; that URL is not saved or logged.

This avoids reconstructing messages from selected fields or turning MIME into new drafts.
The intended behavior is preservation of the exported Exchange representation. Attachments,
original dates, flags, categories and unusual message classes still require live acceptance.
Imported item IDs change. Folder permissions/rules are not restored; distinct recovery folders
are newly created.

The managed Microsoft 365 Backup service has a different storage model: data stays within the
Microsoft service boundary rather than becoming locally owned NAS files. See
[Microsoft architecture](https://learn.microsoft.com/en-us/microsoft-365/backup/backup-architecture?view=o365-worldwide).

## Failure behavior

Item change keys must match across enumeration, export and metadata reading. Concurrent changes
fail that mailbox's run rather than marking a mixed export complete. Later runs use the last
completed cursor; expired cursors trigger rebaselining. Source deletions leave older snapshots
intact. Retention removes only eligible points and unreferenced objects.

Imports/folder creation are non-idempotent. Timeout or ambiguous success is recorded as uncertain,
without an automatic retry that could duplicate mail.
Complete [acceptance](ACCEPTANCE.md) before treating these mechanisms as operational protection.
