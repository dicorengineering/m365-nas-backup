# Using M365 NAS Backup

## Backups and status

**Overview → Back up now** backs up every enabled mailbox. Operations are serialized;
a second backup, verification, cleanup, or restore request receives a busy response while another
console operation is running. The latest operation shows its result. Failure in one mailbox
does not prevent attempts for the others. Completion requires all selected email folders in
that mailbox to have been saved.

After restart the latest-operation panel clears, but snapshots, mailbox attempt status and
restore records persist. Restore records are available through `GET /api/restores`.

Enable scheduling after acceptance. Choose **Every 12 hours**, **Every day (24 hours)**, hourly,
or a custom interval of 15–10,080 minutes. The next run is due that interval after the previous
attempt finishes; it is not a fixed wall-clock time. Restarting preserves this timing. With no
previous attempt, an enabled schedule starts promptly. An overdue schedule runs once when the
service resumes; missed runs are not queued. Manual runs also reset the interval. A failed run
waits for the next interval unless you choose **Back up now**. Keep the NAS clock synchronized.

Leave **Overdue threshold** empty for interval plus 50% (at least 60 extra minutes).
Daily means 2,160 minutes/36 hours; every 12 hours means 1,080 minutes/18 hours.
A custom threshold allows extra time for large mailboxes. Raising the interval above an existing
threshold switches to automatic monitoring instead of refusing to save. Overview shows the next
due time and effective threshold. New settings take effect on the next scheduler check (within
10 seconds), after any active operation finishes.

Green means every currently enabled mailbox has a recent completed backup, its latest attempt
has not failed, and sufficient free storage remains. It does not mean a live restore was tested
or the second NAS is current. Removed/disabled mailboxes are no longer monitored.

## Sign-in and password recovery

Alpha 6 uses one local administrator username/password. On the first visit after installing
or upgrading, enter your existing **admin.token** as the **One-time setup code**, then choose
a username and a password of at least 12 characters. Read the code with:

```sh
docker exec m365-nas-backup cat /config/admin.token
```

Never post the code/password in support messages. Account creation disables administrator-token
access, including old API scripts; Kuma's separate monitor token keeps working. Subsequent
visits use only the username/password. Sessions survive page reloads, expire after 12 hours,
and end on sign-out, password change or container restart. Sign-in is rate limited to five
attempts per minute per installation. Wait a minute after a 429 response.

**Settings → Console password** changes the password and signs out all sessions.
If forgotten, a NAS administrator can set/reset the account without deleting config or backups:

```sh
docker exec -it m365-nas-backup m365-backup set-password YOUR_USERNAME
```

Or run `m365-backup set-password YOUR_USERNAME` in Container Station's interactive container
terminal. It prompts twice without putting the password in command history. This also revokes
existing sessions. The username/password belongs to this application, not Microsoft or QNAP.
Keep `/config/account.json` with the rest of the protected configuration backup.

Passwords are stored as salted PBKDF2-SHA256 hashes (600,000 iterations), following the
[OWASP work-factor guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).
Authentication adds no database service. Browser sessions use HttpOnly, SameSite cookies;
state-changing requests require the console's custom header. No password/token is saved in
localStorage. Use HTTPS or protected Tailscale for traffic privacy. For an HTTPS reverse proxy,
preserve the Host header and set `M365_COOKIE_SECURE=true` on the container to require Secure
cookies; do not enable that setting for a direct HTTP-only installation.

## Incremental transfers and speed

The first backup downloads all supported messages and attachments. Subsequent runs use
[Microsoft Graph delta tracking](https://learn.microsoft.com/en-us/graph/api/mailboxitem-delta?view=graph-rest-1.0).
New/changed versions download; unchanged versions reuse their encrypted local data. Alpha 6
also skips payload and metadata downloads when Microsoft replays an unchanged item. If Microsoft
expires a folder's cursor, the app lists that folder again but reuses matching saved versions.
The previous successful cursor is committed only with a complete new recovery point.

Overview reports new, changed, unchanged and removed messages, downloaded count/MB and duration
(in Operation details). Selecting a recovery point shows its transfer summary; older points have
no statistics. A recovery point listing 50,000 messages does **not** mean 50,000 were downloaded
again. Each point contains a complete index referencing shared stored objects, so restoring it
does not require replaying a chain of incremental backups. Retention preserves objects needed
by every retained point.

A 7.5 GB mailbox needs an initial transfer; its next run normally transfers only changed items.
Changing flags/properties can also change Microsoft's version and require a new export.
Moves that change item/folder identity can require another export and appear as removed/new.
Downloads stay sequential, one item per export, to bound RAM on smaller NAS devices.
Lightweight metadata enumeration and writing the encrypted recovery index still take time.
Reused objects are checked for presence when encountered; run **Verify this backup** periodically
to read/decrypt/hash every object. Incremental transfer success alone is not a full disk-integrity scan.

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

1. In **Recovery**, choose **Email account**, then a dated **Recovery point**. Only that account’s backups are listed. **Load older recovery points** adds the next 200. Saved contents load without contacting Microsoft.
2. Optionally click **Compare with current mailbox** to scan the current **source** mailbox’s metadata. It does not create a backup or change any mail. You can select saved messages without running a comparison.
3. Choose **Missing**, **Changed**, **Moved**, **Only in current mailbox**, or **Everything**. Search subject/folder, then use **Select all matching messages** (across pages) or **Select this page**. You can deselect individual messages. Selection persists while paging/filtering; **Clear selection** resets it. New messages have no version in this recovery point and cannot be selected.
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

Data routes require an authenticated administrator session. GET /api/auth/session reports
whether initial setup is needed. POST /api/auth/login accepts username and password,
sets the session cookie, and requires the header "X-M365-Request: 1". Retain the cookie for
subsequent requests and include that header on mutations. POST /api/auth/logout invalidates
the cookie. POST /api/auth/setup additionally accepts setup_code and works only before an
account exists. POST /api/auth/password accepts current_password and password and revokes
all sessions. Administrator bearer tokens work only before account setup. The separate
monitor token works for /backup-status. Do not hard-code credentials in scripts.

| Method/route | Purpose |
| --- | --- |
| GET `/api/status` | Coverage, space, active/latest operation, next due time, monitoring threshold |
| GET `/api/mailboxes` | Mailboxes with retained backups and recovery-point counts |
| GET/PUT `/api/settings` | Read/replace validated non-secret settings |
| POST `/api/backup` | Start backup; send `{}` |
| GET `/api/snapshots?mailbox=…&limit=200` | Completed points, maximum 1,000 per response |
| GET `/api/snapshots/{id}/items?q=…&offset=0&limit=100` | Browse items and transfer statistics |
| GET `/api/snapshots/{id}/selection?q=…` | Matching saved item IDs, maximum 1,000 |
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
| 401 | Sign in again, or check the monitor token for Kuma |
| 429 during sign-in | Wait a minute; at most five attempts per minute |
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
