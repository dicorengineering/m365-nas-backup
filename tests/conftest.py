import copy

import pytest

from m365_nas_backup.config import Configuration, Mailbox, Settings
from m365_nas_backup.engine import Engine
from m365_nas_backup.repository import Repository


class FakeGraph:
    def __init__(self):
        self.state = {
            "inbox": {"one": {"key": "v1", "data": b"original message with attachment", "subject": "Invoice"}}
        }
        self.revision = 1
        self.fail_export = False
        self.expire_cursor = False
        self.imported = []
        self.created = []
        self.cursors = []

    def close(self):
        pass

    def mailbox_id(self, user):
        return "MBX:" + user

    def folders(self, mailbox_id):
        return [
            {"id": fid, "displayName": fid, "type": "IPF.Note", "childFolderCount": 0} for fid in self.state
        ]

    def delta(self, mailbox_id, folder_id, cursor):
        from m365_nas_backup.graph import GraphError

        self.cursors.append(cursor)
        if self.expire_cursor and cursor:
            self.expire_cursor = False
            raise GraphError(410, "syncStateNotFound")
        current = self.state[folder_id]
        values = [{"id": key, "changeKey": val["key"], "type": "IPM.Note"} for key, val in current.items()]
        if cursor and "one" not in current:
            values.append({"id": "one", "@removed": {"reason": "deleted"}})
        yield {
            "value": values,
            "@odata.deltaLink": "https://graph.microsoft.com/v1.0/checkpoint/" + str(self.revision),
        }

    def export(self, mailbox_id, ids):
        if self.fail_export:
            raise OSError("Injected disk/network failure")
        all_items = {key: val for folder in self.state.values() for key, val in folder.items()}
        return {key: {"bytes": all_items[key]["data"], "changeKey": all_items[key]["key"]} for key in ids}

    def describe(self, mailbox_id, folder_id, item_id):
        item = self.state[folder_id][item_id]
        return {
            "id": item_id,
            "changeKey": item["key"],
            "type": "IPM.Note",
            "size": len(item["data"]),
            "lastModifiedDateTime": "2026-10-25T10:00:00Z",
            "singleValueExtendedProperties": [{"id": "String 0x0037", "value": item["subject"]}],
        }

    def create_folder(self, mailbox_id, name, parent=None):
        new_id = "recovery-" + str(len(self.created))
        self.created.append((mailbox_id, name, parent))
        return new_id

    def import_item(self, mailbox_id, folder_id, content):
        self.imported.append((mailbox_id, folder_id, content))
        return {"itemId": "restored-" + str(len(self.imported)), "changeKey": "restored"}


@pytest.fixture
def setup(tmp_path):
    config = Configuration(tmp_path / "config")
    config.save(Settings(mailboxes=[Mailbox(user="test@example.com")], minimum_free_gb=0.1))
    repo = Repository(tmp_path / "data", config.secret("encryption.key"))
    graph = FakeGraph()
    engine = Engine(config, repo, factory=lambda *_args, **_kwargs: graph)
    return config, repo, graph, engine


@pytest.fixture
def completed(setup):
    config, repo, graph, engine = setup
    result = engine.backup()
    assert result[0]["status"] == "success"
    return setup


def manifest_of(data):
    return copy.deepcopy(data)
