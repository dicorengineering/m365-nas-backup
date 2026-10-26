from fastapi.testclient import TestClient

from m365_nas_backup.api import create_app


def test_old_recovery_points_remain_accessible_beyond_first_thousand(completed):
    config, repo, _, engine = completed
    original = repo.snapshots()[0]
    with repo.db() as db:
        for index in range(1100):
            db.execute(
                "INSERT INTO snapshots VALUES(?,?,?,?,?,?)",
                (
                    f"{index:032x}",
                    original["mailbox"],
                    original["started"],
                    "2000-01-01T00:00:00+00:00",
                    original["manifest"],
                    1,
                ),
            )
    with TestClient(create_app(config, repo, engine)) as client:
        headers = {"Authorization": "Bearer " + config.token()}
        first = client.get("/api/snapshots?limit=1000", headers=headers).json()
        older = client.get("/api/snapshots?limit=1000&offset=1000", headers=headers).json()
        assert len(first) == 1000
        assert len(older) == 101
        assert not ({s["id"] for s in first} & {s["id"] for s in older})
