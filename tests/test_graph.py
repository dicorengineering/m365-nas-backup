import base64

import httpx
import pytest

from m365_nas_backup.graph import Graph, GraphError, UncertainWrite


def graph_with(handler, sleep=None):
    return Graph(
        lambda: "test-graph-token",
        httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=sleep or (lambda _: None),
    )


def test_export_requires_every_requested_item():
    graph = graph_with(
        lambda _: httpx.Response(
            200,
            json={
                "value": [{"itemId": "one", "changeKey": "v1", "data": base64.b64encode(b"opaque").decode()}]
            },
        )
    )
    with pytest.raises(ValueError):
        graph.export("mailbox", ["one", "two"])


def test_export_preserves_opaque_stream():
    data = bytes(range(256))
    graph = graph_with(
        lambda _: httpx.Response(
            200,
            json={"value": [{"itemId": "one", "changeKey": "v1", "data": base64.b64encode(data).decode()}]},
        )
    )
    assert graph.export("mailbox", ["one"])["one"]["bytes"] == data


def test_retry_after_and_pagination():
    waits, requests = [], []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                429, headers={"Retry-After": "2"}, json={"error": {"code": "TooManyRequests"}}
            )
        if len(requests) == 2:
            return httpx.Response(
                200, json={"value": [{"id": "a"}], "@odata.nextLink": "https://graph.microsoft.com/v1.0/next"}
            )
        return httpx.Response(200, json={"value": [{"id": "b"}]})

    graph = graph_with(handler, waits.append)
    assert [r["id"] for r in graph.collection("/first")] == ["a", "b"]
    assert waits == [2]


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/v1.0/items",
        "https://graph.microsoft.com.evil.example/v1.0/items",
        "https://graph.microsoft.com@evil.example/v1.0/items",
        "https://graph.microsoft.com:8443/v1.0/items",
        "https://graph.microsoft.com/beta/items",
    ],
)
def test_pagination_url_cannot_exfiltrate_token(url):
    calls = []
    graph = graph_with(lambda request: calls.append(request) or httpx.Response(200, json={}))
    with pytest.raises(ValueError):
        graph.request("GET", url)
    assert not calls


def test_import_upload_never_contains_graph_authorization():
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.host == "graph.microsoft.com":
            assert request.headers["authorization"] == "Bearer test-graph-token"
            return httpx.Response(
                200, json={"importUrl": "https://outlook.office365.com/api/gv1.0/importItem?authtoken=opaque"}
            )
        assert "authorization" not in request.headers
        assert b'"Mode":"create"' in request.content
        return httpx.Response(200, json={"itemId": "new"})

    graph = graph_with(handler)
    assert graph.import_item("mailbox", "folder", b"original")["itemId"] == "new"
    assert len(calls) == 2


def test_uncertain_import_is_not_retried_and_url_is_not_exposed():
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.host == "graph.microsoft.com":
            return httpx.Response(
                200, json={"importUrl": "https://outlook.office365.com/api/importItem?authtoken=SECRET"}
            )
        raise httpx.ReadTimeout("timeout SECRET", request=request)

    graph = graph_with(handler)
    with pytest.raises(UncertainWrite) as exc:
        graph.import_item("mailbox", "folder", b"original")
    assert len(calls) == 2
    assert "SECRET" not in str(exc.value)


def test_redirects_are_not_followed():
    graph = graph_with(lambda _: httpx.Response(302, headers={"Location": "https://evil.example"}))
    with pytest.raises(GraphError):
        graph.mailbox_id("test@example.com")


def test_recursive_folder_discovery():
    def handler(request):
        if request.url.path.endswith("/childFolders"):
            return httpx.Response(200, json={"value": [{"id": "child", "childFolderCount": 0}]})
        return httpx.Response(200, json={"value": [{"id": "parent", "childFolderCount": 1}]})

    assert [f["id"] for f in graph_with(handler).folders("mailbox")] == ["parent", "child"]


def test_missing_delta_checkpoint_fails():
    graph = graph_with(lambda _: httpx.Response(200, json={"value": []}))
    with pytest.raises(ValueError):
        list(graph.delta("mailbox", "folder", None))
