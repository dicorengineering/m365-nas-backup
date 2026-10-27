import copy

import pytest
from fastapi.testclient import TestClient

from m365_nas_backup.api import create_app
from m365_nas_backup.metadata import item_subject, metadata_subject


@pytest.mark.parametrize("property_id", ["String 0x0037", "String 0x37", "string 0X0037", " String  0x037 "])
def test_subject_tag_is_numeric(property_id):
    metadata = {"singleValueExtendedProperties": [{"id": property_id, "value": "Résumé – invoice"}]}
    assert metadata_subject(metadata) == "Résumé – invoice"
    assert item_subject({"subject": "", "metadata": metadata}) == "Résumé – invoice"


@pytest.mark.parametrize(
    "property_id", ["String 0x1037", "Integer 0x37", "String {guid} Id 0x37", "String 0x0037001F"]
)
def test_other_properties_are_not_treated_as_subject(property_id):
    assert metadata_subject({"singleValueExtendedProperties": [{"id": property_id, "value": "Other"}]}) == ""


def test_empty_subject_and_missing_properties():
    assert metadata_subject({"singleValueExtendedProperties": None}) == ""
    assert metadata_subject({"singleValueExtendedProperties": [{"id": "String 0x37", "value": ""}]}) == ""
    assert item_subject({"subject": "Existing subject", "metadata": {}}) == "Existing subject"


def test_existing_blank_subject_snapshot_browses_searches_and_compares_without_rewrite(completed):
    config, repo, graph, engine = completed
    old = copy.deepcopy(repo.latest("test@example.com"))
    old["folders"]["inbox"]["items"]["one"]["subject"] = ""
    job = repo.begin("test@example.com")
    repo.commit(job, old)
    digest = next(r for r in repo.snapshots() if r["id"] == job)["manifest"]
    before = repo.manifest(job)
    with TestClient(create_app(config, repo, engine)) as client:
        admin = {"Authorization": "Bearer " + config.token()}
        # Offline browsing reads only the stored metadata, including in an old snapshot.
        response = client.get("/api/snapshots/" + job + "/items?q=invoice", headers=admin)
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["subject"] == "Invoice"
    graph.state["inbox"] = {}
    engine.compare(job)
    assert engine.comparison["items"][0]["subject"] == "Invoice"
    assert repo.manifest(job) == before
    assert next(r for r in repo.snapshots() if r["id"] == job)["manifest"] == digest
    assert not graph.created and not graph.imported
