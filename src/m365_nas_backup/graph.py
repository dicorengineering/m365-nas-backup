"""Microsoft Graph v1.0 adapter. No EWS and no MIME-as-draft restore."""

import base64
import hashlib
import re
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlsplit

import httpx
import msal
from cryptography import x509
from cryptography.hazmat.primitives import serialization

from .config import Configuration, Settings

BASE = "https://graph.microsoft.com/v1.0"
SAFE_CODE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


class GraphError(RuntimeError):
    def __init__(self, status: int, code: str = "request_failed"):
        self.status = status
        self.code = code if SAFE_CODE.fullmatch(code) else "request_failed"
        super().__init__(f"graph_{status}_{self.code}")


class UncertainWrite(GraphError):
    """A non-idempotent write may have succeeded. Never retry automatically."""


def segment(value: str) -> str:
    return quote(value, safe="")


class AppToken:
    def __init__(
        self,
        settings: Settings,
        config: Configuration,
        restore: bool = False,
        certificate_pem: bytes | None = None,
    ):
        client_id = settings.restore_client_id if restore else settings.client_id
        if not settings.tenant_id or not client_id:
            raise ValueError("Microsoft tenant/application settings are incomplete")
        prefix = "restore" if restore else "backup"
        private_key = config.secret(prefix + "-private.pem").decode()
        certificate = x509.load_pem_x509_certificate(certificate_pem or config.secret(prefix + "-public.pem"))
        thumbprint = hashlib.sha1(certificate.public_bytes(serialization.Encoding.DER)).hexdigest()
        self.app = msal.ConfidentialClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{settings.tenant_id}",
            client_credential={"private_key": private_key, "thumbprint": thumbprint},
        )

    def __call__(self) -> str:
        result = self.app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in result:
            # Do not expose server error descriptions, tokens or certificate contents.
            raise GraphError(401, result.get("error", "authentication_failed"))
        return result["access_token"]


class Graph:
    def __init__(self, token, client: httpx.Client | None = None, sleep=time.sleep):
        self.token = token
        self.client = client or httpx.Client(timeout=httpx.Timeout(120, connect=20), follow_redirects=False)
        self.sleep = sleep

    def close(self):
        self.client.close()

    def request(self, method: str, path: str, body=None, *, safe=True, import_upload=False) -> dict:
        url = path if path.startswith("https://") else BASE + path
        parts = urlsplit(url)
        expected_host = "outlook.office365.com" if import_upload else "graph.microsoft.com"
        if (
            parts.scheme != "https"
            or parts.hostname != expected_host
            or parts.port not in (None, 443)
            or parts.username
            or parts.password
            or parts.fragment
        ):
            raise ValueError("Refusing an unexpected Microsoft API URL")
        if import_upload:
            if not parts.path.startswith("/api/") or not parts.query:
                raise ValueError("Invalid import session URL")
        elif not parts.path.startswith("/v1.0/"):
            raise ValueError("Only Microsoft Graph v1.0 is enabled")
        headers = {"Accept": "application/json"}
        if not import_upload:
            headers["Authorization"] = "Bearer " + self.token()
        attempts = 5 if safe else 1
        for attempt in range(attempts):
            try:
                response = self.client.request(method, url, headers=headers, json=body)
            except httpx.TransportError:
                if not safe:
                    raise UncertainWrite(0, "transport_result_unknown") from None
                if attempt + 1 == attempts:
                    raise GraphError(0, "transport_failed") from None
                self.sleep(2**attempt)
                continue
            if response.status_code in (429, 500, 502, 503, 504) and safe and attempt + 1 < attempts:
                delay = response.headers.get("Retry-After", str(2**attempt))
                try:
                    seconds = float(delay)
                except ValueError:
                    try:
                        seconds = (parsedate_to_datetime(delay) - datetime.now(UTC)).total_seconds()
                    except (ValueError, TypeError):
                        seconds = 2**attempt
                if seconds > 300:
                    raise GraphError(response.status_code, "retry_later")
                self.sleep(max(0, seconds))
                continue
            if not 200 <= response.status_code < 300:
                try:
                    code = response.json().get("error", {}).get("code", "request_failed")
                except (ValueError, AttributeError):
                    code = "request_failed"
                kind = UncertainWrite if not safe and response.status_code >= 500 else GraphError
                raise kind(response.status_code, code)
            try:
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError()
                return data
            except ValueError:
                kind = UncertainWrite if not safe else GraphError
                raise kind(response.status_code, "invalid_response") from None
        raise GraphError(0, "retry_exhausted")

    def collection(self, path: str) -> list[dict]:
        result = []
        seen = set()
        while path:
            if path in seen:
                raise ValueError("Pagination cycle")
            seen.add(path)
            page = self.request("GET", path)
            values = page.get("value")
            if not isinstance(values, list):
                raise ValueError("Missing collection")
            result.extend(values)
            path = page.get("@odata.nextLink")
        return result

    def mailbox_id(self, user: str) -> str:
        data = self.request("GET", f"/users/{segment(user)}/settings/exchange")
        return data["primaryMailboxId"]

    @staticmethod
    def root(mailbox_id: str) -> str:
        return "/admin/exchange/mailboxes/" + segment(mailbox_id)

    def folders(self, mailbox_id: str) -> list[dict]:
        # Recursively enumerate: the root list alone does not cover nested folders.
        root = self.root(mailbox_id)
        pending = [root + "/folders"]
        folders = {}
        while pending:
            for folder in self.collection(pending.pop()):
                fid = folder["id"]
                if fid in folders:
                    continue
                folders[fid] = folder
                if folder.get("childFolderCount", 0):
                    pending.append(root + f"/folders/{segment(fid)}/childFolders")
        return list(folders.values())

    def delta(self, mailbox_id: str, folder_id: str, cursor: str | None):
        path = cursor or self.root(mailbox_id) + f"/folders/{segment(folder_id)}/items/delta"
        seen = set()
        while True:
            if path in seen:
                raise ValueError("Delta pagination cycle")
            seen.add(path)
            page = self.request("GET", path)
            if not isinstance(page.get("value"), list):
                raise ValueError("Missing delta items")
            yield page
            if page.get("@odata.nextLink"):
                path = page["@odata.nextLink"]
            elif page.get("@odata.deltaLink"):
                break
            else:
                raise ValueError("Delta response omitted continuation token")

    def export(self, mailbox_id: str, ids: list[str]) -> dict[str, dict]:
        if not 1 <= len(ids) <= 20 or len(set(ids)) != len(ids):
            raise ValueError("Export requires 1 to 20 unique item IDs")
        data = self.request("POST", self.root(mailbox_id) + "/exportItems", {"itemIds": ids})
        result = {}
        for entry in data.get("value", []):
            item_id = entry.get("itemId")
            if item_id not in ids or item_id in result or not entry.get("data") or not entry.get("changeKey"):
                raise ValueError("Incomplete or inconsistent Exchange export")
            raw = base64.b64decode(entry["data"], validate=True)
            if not raw:
                raise ValueError("Empty Exchange export")
            result[item_id] = {"bytes": raw, "changeKey": entry["changeKey"]}
        if set(result) != set(ids):
            raise ValueError("Exchange did not export every requested item")
        return result

    def describe(self, mailbox_id: str, folder_id: str, item_id: str) -> dict:
        # Subject is a documented MAPI extended property, not part of mailboxItem.
        path = self.root(mailbox_id) + f"/folders/{segment(folder_id)}/items/{segment(item_id)}"
        return self.request(
            "GET", path + "?$expand=singleValueExtendedProperties($filter=id%20eq%20'String%200x0037')"
        )

    def create_folder(self, mailbox_id: str, name: str, parent: str | None = None) -> str:
        path = self.root(mailbox_id) + "/folders"
        if parent:
            path += "/" + segment(parent) + "/childFolders"
        result = self.request("POST", path, {"displayName": name, "type": "IPF.Note"}, safe=False)
        if not result.get("id"):
            raise UncertainWrite(200, "missing_folder_id")
        return result["id"]

    def import_item(self, mailbox_id: str, folder_id: str, content: bytes) -> dict:
        session = self.request("POST", self.root(mailbox_id) + "/createImportSession", {})
        # Never attach the Graph access token to the preauthenticated import URL.
        result = self.request(
            "POST",
            session["importUrl"],
            {"FolderId": folder_id, "Mode": "create", "Data": base64.b64encode(content).decode()},
            safe=False,
            import_upload=True,
        )
        if not result.get("itemId"):
            raise UncertainWrite(200, "missing_imported_item_id")
        return result
