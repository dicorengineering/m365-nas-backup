"""Browser acceptance on temporary fake mail. Screenshots contain no real data."""

import copy
import socket
import threading
import time
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from playwright.sync_api import expect, sync_playwright

from m365_nas_backup.api import create_app
from m365_nas_backup.cli import certificates
from m365_nas_backup.config import Configuration, Mailbox, Settings
from m365_nas_backup.engine import Engine
from m365_nas_backup.repository import Repository
from tests.conftest import FakeGraph


class RecoveryGraph(FakeGraph):
    def __init__(self):
        super().__init__()
        self.target_folders = [
            {
                "id": "target-inbox",
                "displayName": "Inbox",
                "parentFolderId": "target-root",
                "wellKnownName": "inbox",
                "type": "IPF.Note",
                "totalItemCount": 0,
            }
        ]

    def folders(self, mailbox_id):
        if mailbox_id == "MBX:replacement@example.com":
            return copy.deepcopy(self.target_folders)
        return [
            {**f, "wellKnownName": "inbox", "parentFolderId": "source-root"}
            for f in super().folders(mailbox_id)
        ]

    def mime(self, *args):
        return b"From: demo@example.com\r\nSubject: Invoice\r\n\r\nSynthetic portable message\r\n"

    def create_folder(self, mailbox_id, name, parent=None):
        fid = super().create_folder(mailbox_id, name, parent)
        if mailbox_id == "MBX:replacement@example.com":
            self.target_folders.append(
                {
                    "id": fid,
                    "displayName": name,
                    "parentFolderId": parent,
                    "type": "IPF.Note",
                    "totalItemCount": 0,
                }
            )
        return fid

    def import_item(self, mailbox_id, folder_id, content):
        result = super().import_item(mailbox_id, folder_id, content)
        if mailbox_id == "MBX:replacement@example.com":
            next(f for f in self.target_folders if f["id"] == folder_id)["totalItemCount"] += 1
        return result


def main():
    output = Path("build/browser")
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        config = Configuration(root / "config")
        certificates(config)
        config.save(
            Settings(
                mailboxes=[
                    Mailbox(user="demo@example.com"),
                    Mailbox(user="replacement@example.com", enabled=False),
                ],
                minimum_free_gb=0.1,
                portable_email_enabled=True,
            )
        )
        repo = Repository(root / "data", config.secret("encryption.key"))
        graph = RecoveryGraph()
        engine = Engine(config, repo, factory=lambda *args, **kwargs: graph)
        engine.backup()
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(
                create_app(config, repo, engine, exports_directory=root / "exports"), log_level="error"
            )
        )
        worker = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        worker.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.1)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1050})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{port}")
                expect(page.get_by_role("button", name="Create account")).to_be_visible()
                page.get_by_label("One-time setup code", exact=True).fill(config.token())
                page.get_by_label("Username", exact=True).fill("demo")
                page.get_by_label("Password", exact=True).fill("Synthetic password only!")
                page.get_by_label("Confirm password", exact=True).fill("Synthetic password only!")
                page.get_by_role("button", name="Create account").click()
                expect(page.locator("#health-banner")).to_contain_text("recent completed backup")
                page.reload()
                expect(page.locator("#console")).to_be_visible()
                page.screenshot(path=str(output / "overview.png"), full_page=True)
                page.get_by_role("button", name="Settings", exact=True).click()
                page.locator("#schedule-preset").select_option("720")
                expect(page.locator('[name="interval_minutes"]')).to_have_value("720")
                page.locator("#schedule-preset").select_option("1440")
                expect(page.locator('[name="interval_minutes"]')).to_have_value("1440")
                page.locator("#retention-days").fill("90")
                page.locator("#minimum-snapshots").fill("3")
                page.locator('[name="restore_enabled"]').check()
                page.get_by_role("button", name="Save settings", exact=True).click()
                expect(page.get_by_role("status")).to_have_text("Settings saved.")
                assert config.load().interval_minutes == 1440
                assert config.load().overdue_minutes == 2160
                assert config.load().retention.days == 90
                assert config.load().retention.minimum_snapshots == 3
                page.locator("#certificate-days").fill("3650")
                page.get_by_role("button", name="Prepare replacement", exact=True).click()
                expect(page.get_by_role("status")).to_contain_text("Replacement prepared")
                expect(page.locator("#certificate-status")).to_contain_text("replacement until")
                with page.expect_download() as download_info:
                    page.get_by_role("button", name="Download replacement", exact=True).click()
                downloaded = Path(download_info.value.path()).read_bytes()
                assert downloaded == config.secret("backup-pending-public.pem")
                assert b"PRIVATE KEY" not in downloaded
                page.screenshot(path=str(output / "settings.png"), full_page=True)
                # Compare a deleted original and a live-only message; bulk selection must
                # restore only the backed-up original, leaving the new message untouched.
                original = graph.state["inbox"].pop("one")
                graph.state["inbox"]["later"] = {**original, "subject": "New mail"}
                page.get_by_role("button", name="Recovery", exact=True).click()
                expect(page.locator("#snapshot")).to_be_disabled()
                page.locator("#source-mailbox").select_option("demo@example.com")
                page.locator("#snapshot").select_option(repo.snapshots()[0]["id"])
                expect(page.locator("#item-rows")).to_contain_text("Invoice")
                assert engine.comparison is None
                page.get_by_role("button", name="Select all matching messages", exact=True).click()
                expect(page.get_by_label("Select Invoice")).to_be_checked()
                page.screenshot(path=str(output / "recovery.png"), full_page=True)
                page.get_by_role("button", name="Compare with current mailbox", exact=True).click()
                expect(page.locator("#comparison-summary")).to_contain_text("1 missing", timeout=15000)
                expect(page.get_by_label("Select New mail")).to_be_disabled()
                page.get_by_role("button", name="Select all matching messages", exact=True).click()
                expect(page.get_by_label("Select Invoice")).to_be_checked()
                page.screenshot(path=str(output / "comparison.png"), full_page=True)
                page.get_by_role("button", name="Review restore", exact=True).click()
                expect(page.locator("#review")).to_be_visible()
                expect(page.locator("#review-body")).to_contain_text("demo@example.com")
                page.screenshot(path=str(output / "restore-review.png"), full_page=True)
                page.get_by_role("button", name="Confirm", exact=True).click()
                expect(page.get_by_role("status")).to_contain_text("Restore started")
                for _ in range(100):
                    if graph.imported:
                        break
                    time.sleep(0.05)
                assert graph.imported[0][2] == b"original message with attachment"
                page.locator("#replacement-mailbox").select_option("replacement@example.com")
                page.get_by_role("button", name="Review whole-mailbox recovery", exact=True).click()
                expect(page.locator("#review-title")).to_contain_text("Rebuild 1 messages")
                expect(page.locator("#review-body")).to_contain_text("entire recovery point")
                page.screenshot(path=str(output / "mailbox-review.png"), full_page=True)
                page.get_by_role("button", name="Confirm", exact=True).click()
                expect(page.get_by_role("status")).to_contain_text("Whole-mailbox recovery started")
                for _ in range(100):
                    if len(graph.imported) == 2:
                        break
                    time.sleep(0.05)
                assert graph.imported[1][0:2] == ("MBX:replacement@example.com", "target-inbox")
                page.locator("#refresh-recovery").click()
                expect(page.locator("#recovery-jobs")).to_contain_text("success")
                expect(page.locator("#recovery-jobs")).to_contain_text("1 / 1 messages")
                page.get_by_role("button", name="Export whole backup as EML ZIP", exact=True).click()
                expect(page.locator("#review-body")).to_contain_text("unencrypted ZIP")
                page.get_by_role("button", name="Confirm", exact=True).click()
                expect(page.get_by_role("status")).to_contain_text("Export started")
                for _ in range(100):
                    if list((root / "exports").glob("*.zip")):
                        break
                    time.sleep(0.05)
                page.locator("#refresh-recovery").click()
                with page.expect_download() as export_download:
                    page.get_by_role("link", name="Download EML ZIP", exact=False).click()
                with zipfile.ZipFile(export_download.value.path()) as archive:
                    eml = next(n for n in archive.namelist() if n.endswith(".eml"))
                    assert archive.read(eml) == graph.mime()
                page.screenshot(path=str(output / "whole-recovery-export.png"), full_page=True)
                page.get_by_role("button", name="Delete export", exact=True).click()
                page.get_by_role("button", name="Confirm", exact=True).click()
                expect(page.locator("#exports-list")).to_have_text("No completed exports.")
                page.set_viewport_size({"width": 390, "height": 844})
                page.screenshot(path=str(output / "mobile.png"), full_page=True)
                page.get_by_role("button", name="Sign out").click()
                expect(page.locator("#login")).to_be_visible()
                expect(page.locator("#setup-code-field")).to_be_hidden()
                page.get_by_label("Username", exact=True).fill("demo")
                page.get_by_label("Password", exact=True).fill("Synthetic password only!")
                page.get_by_role("button", name="Sign in", exact=True).click()
                expect(page.locator("#console")).to_be_visible()
                assert not errors, errors
                browser.close()
                print(
                    "Browser passed: account setup, password login/logout, session reload, daily schedule, recovery selection, optional comparison, selected restore, whole-mailbox recovery, EML download/delete."
                )
        finally:
            server.should_exit = True
            worker.join(timeout=15)
            listener.close()


if __name__ == "__main__":
    main()
