import json
from urllib.parse import parse_qs

import httpx
import pytest

from tools.connect_analytics.client import PREFIX, ConnectAnalyticsClient

PLACEHOLDER = "CONNECT_ANALYTICS_API_KEY"


@pytest.fixture(autouse=True)
def placeholder_env(monkeypatch):
    # In a Centaur sandbox the placeholder is literally the secret's name.
    monkeypatch.setenv("CONNECT_ANALYTICS_API_KEY", PLACEHOLDER)


def make_client(handler):
    return ConnectAnalyticsClient(transport=httpx.MockTransport(handler))


def test_summary_url_header_and_params():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = request.url
        seen["headers"] = request.headers
        return httpx.Response(200, json={"data": [{"clientId": "c1"}]})

    data = make_client(handler).summary(date_from="2026-08-01", client_id="c1")

    assert data == [{"clientId": "c1"}]
    assert seen["url"].host == "api.narval.xyz"
    assert seen["url"].path == f"{PREFIX}/summary"
    assert seen["headers"]["x-api-key"] == PLACEHOLDER
    qs = parse_qs(seen["url"].query.decode())
    assert qs == {"dateFrom": ["2026-08-01"], "clientId": ["c1"]}  # None values dropped, camelCase


def test_transactions_params_and_include_resolution():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = request.url
        return httpx.Response(200, json={"data": {"events": [], "nextCursor": None}})

    client = make_client(handler)
    client.transactions(account_address="0xabc", network_id="eip155:1", limit=10, include_resolution=True)
    qs = parse_qs(seen["url"].query.decode())
    assert seen["url"].path == f"{PREFIX}/events/transactions"
    assert qs == {"accountAddress": ["0xabc"], "networkId": ["eip155:1"], "limit": ["10"], "include": ["resolution"]}

    client.transactions(tx_hash="0xdead")
    qs = parse_qs(seen["url"].query.decode())
    assert qs == {"txHash": ["0xdead"]}  # no include when include_resolution is False


def test_connections_params():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = request.url
        return httpx.Response(200, json={"data": {"events": [], "nextCursor": None}})

    make_client(handler).connections(event_type="grant_created,grant_success", grant_id="g1", cursor="cur")
    qs = parse_qs(seen["url"].query.decode())
    assert seen["url"].path == f"{PREFIX}/events/connections"
    assert qs == {"eventType": ["grant_created,grant_success"], "grantId": ["g1"], "cursor": ["cur"]}


def test_missing_secret_raises(monkeypatch):
    monkeypatch.delenv("CONNECT_ANALYTICS_API_KEY", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request expected")

    with pytest.raises(RuntimeError, match="CONNECT_ANALYTICS_API_KEY"):
        make_client(handler).summary()


def test_http_error_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "nope"})

    with pytest.raises(httpx.HTTPStatusError):
        make_client(handler).filters()


def test_digest_aggregates_two_pages():
    tx_page1 = {
        "events": [
            {
                "clientId": "c1", "provider": "bitgo", "connectionId": "conn1", "accountAddress": "0xw1",
                "networkId": "eip155:1", "eventType": "tx_evaluated", "status": "success",
                "rpcMethod": "eth_sendTransaction", "toAddress": "0xuni", "txHash": None,
                "createdAt": "2026-08-20T10:00:00Z", "resolution": {"kind": "swap"}, "action": "swap", "whitelisted": True,
            }
        ],
        "nextCursor": "p2",
    }
    tx_page2 = {
        "events": [
            {
                "clientId": "c1", "provider": "bitgo", "connectionId": "conn1", "accountAddress": "0xw1",
                "networkId": "eip155:1", "eventType": "tx_completed", "status": "success",
                "rpcMethod": None, "toAddress": None, "txHash": "0xhash", "createdAt": "2026-08-20T10:05:00Z",
            },
            {
                "clientId": "c2", "provider": "bitgo", "connectionId": None, "accountAddress": None,
                "networkId": None, "eventType": "tx_failed", "status": "failed", "errorCode": "decode_failed",
                "createdAt": "2026-08-21T00:00:00Z",
            },
        ],
        "nextCursor": None,
    }
    conn_page = {
        "events": [
            {
                "clientId": "c1", "provider": "bitgo", "connectionId": "conn1", "grantId": "g1",
                "eventType": "grant_success", "status": "success", "walletCount": 2, "ipAddress": "1.2.3.4",
                "createdAt": "2026-08-19T09:00:00Z",
            }
        ],
        "nextCursor": None,
    }
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        qs = parse_qs(request.url.query.decode())
        if request.url.path.endswith("/summary"):
            return httpx.Response(200, json={"data": [{"clientId": "c1", "txEvaluated": 1}]})
        if request.url.path.endswith("/wallets"):
            return httpx.Response(200, json={"data": [{"accountAddress": "0xw1"}]})
        if request.url.path.endswith("/events/transactions"):
            assert qs["include"] == ["resolution"]
            assert qs["limit"] == ["500"]
            return httpx.Response(200, json={"data": tx_page2 if qs.get("cursor") == ["p2"] else tx_page1})
        if request.url.path.endswith("/events/connections"):
            return httpx.Response(200, json={"data": conn_page})
        raise AssertionError(request.url)

    digest = make_client(handler).digest(date_from="2026-08-01", client_id=None)

    assert calls.count(f"{PREFIX}/events/transactions") == 2  # followed nextCursor once
    assert digest["counts"] == {"transaction_events": 3, "connection_events": 1}
    assert digest["summary"] == [{"clientId": "c1", "txEvaluated": 1}]

    by_id = {c["client_id"]: c for c in digest["clients"]}
    c1 = by_id["c1"]
    assert c1["providers"] == ["bitgo"]
    conn1 = c1["connections"][0]
    assert conn1["connection_id"] == "conn1"
    assert conn1["connection_events"][0]["grant_id"] == "g1"
    assert conn1["connection_events"][0]["ip_address"] == "1.2.3.4"
    w1 = conn1["wallets"][0]
    assert w1["account_address"] == "0xw1"
    assert w1["networks"] == ["eip155:1"]
    assert [t["event_type"] for t in w1["transactions"]] == ["tx_evaluated", "tx_completed"]
    assert w1["transactions"][0]["resolution"] == {"kind": "swap"}
    assert w1["transactions"][0]["whitelisted"] is True
    assert w1["transactions"][1]["resolution"] is None  # absent on the API row -> null
    assert w1["transactions"][1]["tx_hash"] == "0xhash"

    c2 = by_id["c2"]
    assert c2["connections"][0]["connection_id"] is None
    assert c2["connections"][0]["wallets"][0]["account_address"] is None
    assert c2["connections"][0]["wallets"][0]["transactions"][0]["error_code"] == "decode_failed"

    json.dumps(digest)  # fully serialisable (no sets left)


def test_digest_respects_max_pages():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/events/transactions"):
            return httpx.Response(200, json={"data": {"events": [{"clientId": "c"}], "nextCursor": "more"}})
        if request.url.path.endswith("/events/connections"):
            return httpx.Response(200, json={"data": {"events": [], "nextCursor": None}})
        return httpx.Response(200, json={"data": []})

    digest = make_client(handler).digest(max_pages=2)
    assert digest["counts"]["transaction_events"] == 2
