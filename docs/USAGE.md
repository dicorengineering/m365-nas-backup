# Using M365 NAS Backup

## Backups and status

**Overview → Back up now** backs up every enabled mailbox. Operations are serialized;
a second backup, verification, cleanup, or restore request receives a busy response while another
console operation is running. The latest operation shows its result. Failure in one mailbox
does not prevent attempts for the others. Completion requires all selected email folders in
that mailbox to have been saved.

After restart the latest-operation panel clears, but snapshots, mailbox attempt status and
restore records persist. Restore records are available through `GET /api/restores`.

Enable scheduling after acceptance. Default interval: 60 minutes; overdue threshold: 180 minutes.
The threshold must exceed the interval and allow for a full large-mailbox run. Enabled schedules
begin promptly on service startup. Keep the NAS clock synchronized.

Green means every currently enabled mailbox has a recent completed backup, its latest attempt
has not failed, and sufficient free storage remains. It does not mean a live restore was tested
or the second NAS is current. Removed/disabled mailboxes are no longer monitored.

## Adjustable history

Defaults: **40 days**, minimum **2 recovery points per mailbox**, automatic cleanup **off**.

- **Keep for N days:** points older than N days at completion time become eligible for cleanup.
- **Minimum recovery points:** newest N points survive even if older than the retention window.
  This is a lower bound, not a maximum number of versions.
- **Keep forever:** no completed points expire. Watch storage.
- **Automatic cleanup:** remove expired points after a wholly successful backup run.
- **Preview cleanup:** review eligible snapshot IDs/count and confirm manual removal.
  A changed plan requires a new preview.

Example: an email is backed up Monday, deleted Tuesday, and backed up again Wednesday.
Monday's retained point still contains the email. Choose that point to recover it.
When every point referencing that version expires and cleanup runs, it cannot be recovered.

Changing retention alone does not delete anything. Automatic cleanup or confirmed manual cleanup
does. Raising retention cannot restore removed versions. Unchanged objects are deduplicated,
but each recovery point has its own encrypted manifest.

## Message subjects

Alpha 5 fixes subject extraction when Graph returns a property tag such as `String 0x37`
instead of `String 0x0037`. Existing snapshots are displayed and searched using their saved
metadata when the old subject field is blank. No rebackup, tenant access or snapshot rewrite
is needed when that metadata contains the subject. Truly absent/empty subjects remain "(No subject)".

## Browse and restore email

1. In **Recovery**, choose the source mailbox/date from **Recovery point**. Use **Load older recovery points** to access history beyond the first 1,000 points.
2. A read-only comparison scans the current **source** mailbox's email metadata. It does not create a backup or change any mail. If another operation is busy, use **Compare with current mailbox** once it finishes.
3. Choose **Missing**, **Changed**, **Moved**, **Only in current mailbox**, or **Everything**. Search subject/folder, then use **Select all matching differences** (across pages) or **Select this page**. You can deselect individual messages. Selection persists while paging/filtering; **Clear selection** resets it. New messages have no version in this recovery point and cannot be selected.
4. Choose a destination from the explicitly configured mailboxes.
5. Click **Review restore** and confirm destination/count.
6. Confirm; follow the latest operation in Overview.
7. In Outlook, find **M365 Recovery YYYY-MM-DD HHMMSS …** in the destination.
   Source folders are separated into distinct children with short identifiers.
8. Check content/attachments before moving recovered mail into normal folders.

Comparison shows the source mailbox and scan completion time. Changing the restore destination does
not compare that different mailbox. The default hides unchanged items. Changed means Exchange's
version changed, including flags/properties; it is not a byte-level body/attachment diff. A move is
recognized only while Microsoft preserves the item ID. Changed identities, including prior restored
copies, may appear as missing plus new. No subject-based guessing or duplicate suppression is used.
The scan is not an atomic instant; refresh before selection if mail is changing. Failed scans publish
no partial result. Only one comparison is retained in service memory; restart or another comparison
replaces it. It downloads metadata, not attachment payloads, and does not advance backup cursors.

Restore must be enabled and the separate restore app configured. Each operation supports up to
1,000 selected items. Existing items are not overwritten. Restored items have new IDs.
Repeating a confirmed restore creates another copy.

If the result is **uncertain**, inspect the destination before retrying: Microsoft may have
received the import even if the response was lost. The app never automatically retries an
uncertain import. Failed restores can leave partial recovery folders; check results and
`GET /api/restores` for completed item IDs.

## Verify a point

Choose it in Recovery and click **Verify this backup**. The result checks decryption and content
hashes of every referenced object. This detects local corruption; it does not replace a live
restore. Verify periodically and after moving/restoring storage.

## Uptime Kuma

Add an **HTTP(s)** monitor:

| Setting | Value |
| --- | --- |
| URL | `https://YOUR_PRIVATE_HOST/backup-status`, or HTTP over protected Tailscale |
| Method | GET |
| Accepted codes | 200 only |
| Interval | Start with 60 seconds |
| Header | `Authorization: Bearer YOUR_MONITOR_TOKEN` |
| Retries | 1–2 if appropriate for your alert policy |

Read the separate token using `docker exec m365-nas-backup cat /config/monitor.token`,
or run `cat /config/monitor.token` in the container terminal. In Kuma's headers field:

```json
{"Authorization":"Bearer YOUR_MONITOR_TOKEN"}
```

The endpoint returns **200** when all selected mailboxes are current; **503** for no completed
backup, failed latest attempt, overdue coverage, insufficient free space, or no configured
mailbox. Authentication failures return 401. Use the monitor token rather than the administrator
token. Never place tokens in URLs.

An optional second monitor for **/health** checks only process liveness and needs no token.
Configure notifications and exercise a failure alert. A running web service is not proof of
successful backup.

A remote Kuma server needs a network route and access rule to the NAS, such as Tailscale.
Loopback-only binding is not remotely reachable. HTTP polling is implemented; Kuma push is not.

## API reference

All `/api/*` routes require the administrator bearer token.

| Method/route | Purpose |
| --- | --- |
| GET `/api/status` | Coverage, space, active/latest operation |
| GET/PUT `/api/settings` | Read/replace validated non-secret settings |
| POST `/api/backup` | Start backup; send `{}` |
| GET `/api/snapshots?mailbox=…&limit=200` | Completed points, maximum 1,000 per response |
| GET `/api/snapshots/{id}/items?q=…&offset=0&limit=100` | Browse items |
| POST `/api/snapshots/{id}/verify` | Start verification; send `{}` |
| GET `/api/retention/preview` | Eligible removals and confirmation |
| POST `/api/retention/apply` | Send `{"confirmation":"…"}` |
| POST `/api/restore/preview` | Send snapshot_id, destination, selections |
| POST `/api/restore` | Same fields plus preview confirmation |
| POST `/api/snapshots/{id}/compare` | Start read-only comparison with the current source mailbox |
| GET `/api/comparisons/{id}` | Paged differences; status, q, offset, limit |
| GET `/api/comparisons/{id}/selection` | All matching restorable IDs, maximum 1,000 |
| GET `/api/certificates` | Local active/pending certificate expiry and thumbprints |
| POST `/api/certificates/{purpose}/prepare` | Prepare a replacement with days (1–3,650) |
| POST `/api/certificates/{purpose}/activate` | Test and activate the specified pending thumbprint |
| GET `/api/restores` | Persistent restore records |

Selections contain `folder_id`/`item_id` from the browse response. Confirmation binds the plan;
it does not replace authentication. Mutations require Content-Length no larger than 1 MiB.
Asynchronous requests return 202; check status for completion. Busy returns 409.
Settings never return private keys/tokens. Public certificates have authenticated download routes.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| App will not start | Container Station running, free space, port conflicts, bind IP available |
| Web shortcut fails | Default loopback binding; use the SSH tunnel or protected Tailscale/HTTPS route |
| Container killed / exit 137 | Inspect OOM status and memory use; see [resource guidance](RESOURCES.md) |
| Image pull/access denied | Import the bundled image first and disable forced image pulling |
| 401 | Correct admin/monitor token and exact Bearer header |
| `graph_401_…` | IDs, correct uploaded certificate, expiry, consent |
| `graph_403_…` | Exact application permissions, consent, tenant policy |
| `graph_429_…` / `retry_later` | Throttling; allow later run, adjust interval if needed |
| `ValueError` / incomplete backup | Connection setup or item changes during export; retry; investigate persistent failure |
| Overdue | Scheduler enabled, NAS awake, threshold appropriate, last successful time |
| Low space | Add capacity or deliberately preview cleanup; never delete objects manually |
| Verification fails | Stop cleanup; preserve data and recover from a verified copy |
| Missing encryption key | Restore original configuration; a new key cannot recover old data |
| Restore uncertain | Inspect the destination before retrying |
| Container-name conflict | Another container owns the name; the app refuses to replace it |

QNAP container: `m365-nas-backup`. NAS administrators can inspect status/logs in Container Station.
Logs avoid tokens and raw Microsoft error bodies. For support, include version/source commit,
QTS/Container Station versions, safe error code/time, and whether a test mailbox reproduces it.
Remove addresses and item IDs before public sharing. Never share config, import URLs or real data.
