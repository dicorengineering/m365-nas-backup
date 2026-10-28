"""Schedule relative to the last persisted attempt, including across restarts."""

from datetime import UTC, datetime, timedelta


def next_backup_at(repo, settings, now=None):
    if not settings.scheduler_enabled or not any(m.enabled for m in settings.mailboxes):
        return None
    with repo.db() as db:
        row = db.execute("SELECT MAX(COALESCE(completed, started)) AS last FROM attempts").fetchone()
    if not row["last"]:
        return now or datetime.now(UTC)
    return datetime.fromisoformat(row["last"]) + timedelta(minutes=settings.interval_minutes)
