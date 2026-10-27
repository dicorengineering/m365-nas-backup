# Acceptance before relying on the alpha

Automated tests use fake data/mocked HTTP. Browser/container checks exercise the packaged service
without tenant credentials. They do not replace physical QNAP installation and real Exchange
restoration. Use a dedicated test mailbox and disposable messages.

Record app/source version, QTS/Container Station versions, tenant cloud, date and results.
Keep your existing backup until acceptance succeeds.

## Installation and persistence

- Import the image on the intended QTS/NAS model; confirm the exact tag appears in Images
  (or `docker image ls`) before creating the Compose application. A success notification alone
  does not establish that the image was loaded.
- Confirm Container Station runs it without privileged/root application access.
- Open through a protected route; confirm unauthenticated data access is denied.
- Save retention, stop/start in Container Station, and verify settings survive.
- Reboot and check startup order/access/state.
- Confirm config/data/exports persist in the intended named volumes or explicit local mounts.
- Monitor memory/CPU during baseline and verification; record peaks and any restarts.
- Recreate the container keeping its volume names and verify old recovery points survive.
- On spare test state, check an upgrade/reinstall preserves recoverability.

## Real mail backup and restore

1. Prepare messages with text, HTML, Unicode, inline images, ordinary/multiple attachments,
   categories/read flags, old dates, and sent mail. Include nested/duplicate folder names
   and a configured shared mailbox.
2. Run baseline; record count/time and verify it.
3. Change a disposable message; back up again.
4. Delete a disposable message/folder; run another successful backup.
5. Select the earlier point and restore the original version into the test mailbox.
6. Compare subject/body, sender/recipients, dates, flags/categories and attachment bytes.
   Check items appear as intended rather than unexpected drafts; originals must remain intact.
7. Test another explicitly configured destination if cross-mailbox recovery is required.
8. Record exclusions/fidelity differences. HTTP success alone is not acceptance.

## Failure and monitoring

- Interrupt a test backup; restart. Confirm failed/interrupted status and preserved old point.
- Temporarily revoke test-app access; confirm failed backup and Kuma alert. Restore access,
  run a successful backup and confirm the alert clears.
- Pause scheduling until overdue; /backup-status should fail while /health stays up.
- Exercise the actual notification channel.
- Inspect any uncertain/partial restore before retrying.

## Retention and second copy

- With disposable data test minimum points, keep forever, cleanup preview/confirmation.
- Verify retained points after cleanup; do not shorten real retention just for testing.
- Export, copy to the second NAS and compare SHA-256; retain the original key separately.
- Recover into a new empty repository with scheduling disabled.
- Verify old/new points and perform a real restore from the recovered copy.

No physical NAS or live Microsoft acceptance is implied by passing automated CI.
