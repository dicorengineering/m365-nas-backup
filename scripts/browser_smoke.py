"""Browser acceptance on temporary fake mail. Screenshots contain no real data."""

import socket
import threading
import time
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


def main():
    output = Path("build/browser")
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        config = Configuration(root / "config")
        certificates(config)
        config.save(Settings(mailboxes=[Mailbox(user="demo@example.com")], minimum_free_gb=0.1))
        repo = Repository(root / "data", config.secret("encryption.key"))
        graph = FakeGraph()
        engine = Engine(config, repo, factory=lambda *args, **kwargs: graph)
        engine.backup()
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(create_app(config, repo, engine), log_level="error"))
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
                page.get_by_label("Administrator access token").fill(config.token())
                page.get_by_role("button", name="Open backup console").click()
                expect(page.locator("#health-banner")).to_contain_text("recent completed backup")
                page.screenshot(path=str(output / "overview.png"), full_page=True)
                page.get_by_role("button", name="Settings", exact=True).click()
                page.locator("#retention-days").fill("90")
                page.locator("#minimum-snapshots").fill("3")
                page.locator('[name="restore_enabled"]').check()
                page.get_by_role("button", name="Save settings", exact=True).click()
                expect(page.get_by_role("status")).to_have_text("Settings saved.")
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
                page.locator("#snapshot").select_option(repo.snapshots()[0]["id"])
                expect(page.locator("#item-rows")).to_contain_text("Invoice")
                expect(page.locator("#comparison-summary")).to_contain_text("1 missing", timeout=15000)
                expect(page.get_by_label("Select New mail")).to_be_disabled()
                page.get_by_role("button", name="Select all matching differences", exact=True).click()
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
                page.set_viewport_size({"width": 390, "height": 844})
                page.screenshot(path=str(output / "mobile.png"), full_page=True)
                page.get_by_role("button", name="Lock console").click()
                expect(page.locator("#login")).to_be_visible()
                assert not errors, errors
                browser.close()
                print("Browser passed: login, overview, retention, browsing, restore confirmation, lock.")
        finally:
            server.should_exit = True
            worker.join(timeout=15)
            listener.close()


if __name__ == "__main__":
    main()
