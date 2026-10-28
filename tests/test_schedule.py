from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from m365_nas_backup.api import create_app
from m365_nas_backup.config import Settings
from m365_nas_backup.schedule import next_backup_at


@pytest.mark.parametrize("interval", [720, 1440, 10080])
def test_long_schedule_upgrades_old_monitoring_threshold(setup, interval):
    config, repo, _, engine = setup
    with TestClient(create_app(config, repo, engine)) as client:
        settings = config.load().model_dump()
        settings.update(interval_minutes=interval, stale_after_minutes=180)
        response = client.put(
            "/api/settings", json=settings, headers={"Authorization": "Bearer " + config.token()}
        )
        assert response.status_code == 200
        assert config.load().interval_minutes == interval
        assert config.load().overdue_minutes == interval + interval // 2
        assert response.json()["stale_after_minutes"] is None


def test_schedule_uses_persisted_completion_and_changes_without_restart(completed):
    config, repo, _, _ = completed
    settings = config.load()
    settings.scheduler_enabled = True
    settings.interval_minutes = 1440
    completed_at = datetime(2026, 10, 28, 12, tzinfo=UTC)
    with repo.db() as db:
        db.execute("UPDATE attempts SET completed=?", (completed_at.isoformat(),))
    assert next_backup_at(repo, settings) == completed_at + timedelta(days=1)
    settings.interval_minutes = 720
    assert next_backup_at(repo, settings) == completed_at + timedelta(hours=12)
    settings.scheduler_enabled = False
    assert next_backup_at(repo, settings) is None


def test_first_schedule_is_due_now_and_empty_configuration_stays_idle(setup):
    config, repo, _, _ = setup
    settings = config.load()
    settings.scheduler_enabled = True
    now = datetime.now(UTC)
    assert next_backup_at(repo, settings, now) == now
    settings.mailboxes.clear()
    assert next_backup_at(repo, settings, now) is None
    assert Settings(interval_minutes=1440, stale_after_minutes=3000).overdue_minutes == 3000
