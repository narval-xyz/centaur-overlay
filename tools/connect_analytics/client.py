"""Connect Analytics client.

Reads the Narval Connect analytics reporting endpoints on the production Armory
API. Public methods of ConnectAnalyticsClient become Centaur tool methods.

The credential is never a real value inside the sandbox. `secret()` returns a
placeholder that iron-proxy swaps for the real key, only on requests to
api.narval.xyz and only in the x-api-key header (see pyproject.toml).
"""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Any

import httpx

try:
    from centaur_sdk.tool_sdk import secret
except ImportError:  # pragma: no cover
    # Outside a Centaur sandbox (unit tests, local development) the SDK is not
    # installed. Fall back to the environment so the client stays runnable; the
    # placeholder/injection semantics only exist behind iron-proxy anyway.
    def secret(name: str, default: str = "") -> str:
        return os.environ.get(name, default)


BASE_URL = "https://api.narval.xyz"
PREFIX = "/v1/management/connect-analytics"
SECRET_NAME = "CONNECT_ANALYTICS_API_KEY"
DEFAULT_TIMEOUT = 30.0


class ConnectAnalyticsClient:
    """Thin, typed client over the five Connect analytics reporting endpoints."""

    BASE_URL = BASE_URL

    def __init__(self, transport: httpx.BaseTransport | None = None, base_url: str | None = None) -> None:
        self._base_url = base_url or self.BASE_URL
        self._http = httpx.Client(base_url=self._base_url, timeout=DEFAULT_TIMEOUT, transport=transport)

    # ------------------------------------------------------------------ public

    def summary(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        client_id: str | None = None,
        provider: str | None = None,
    ) -> Any:
        """Per (clientId, provider) counters: grants, sub-grants, token rotations, revocations, tx evaluated/submitted/completed/failed. Default window: last 30 days."""
        return self._get(
            "/summary",
            self._params(dateFrom=date_from, dateTo=date_to, clientId=client_id, provider=provider),
        )

    def wallets(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        client_id: str | None = None,
        provider: str | None = None,
    ) -> Any:
        """Per wallet (account address): networks touched, tx counters, first and last activity."""
        return self._get(
            "/wallets",
            self._params(dateFrom=date_from, dateTo=date_to, clientId=client_id, provider=provider),
        )

    def connections(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        client_id: str | None = None,
        provider: str | None = None,
        event_type: str | None = None,
        status: str | None = None,
        grant_id: str | None = None,
        connection_id: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Any:
        """Connection events (grant_created, sub_grant_started|success|denied, grant_success, token_rotated, connection_revoked). Paginated: returns {events, nextCursor}. event_type accepts a comma-separated list."""
        return self._get(
            "/events/connections",
            self._params(
                dateFrom=date_from,
                dateTo=date_to,
                clientId=client_id,
                provider=provider,
                eventType=event_type,
                status=status,
                grantId=grant_id,
                connectionId=connection_id,
                limit=limit,
                cursor=cursor,
            ),
        )

    def transactions(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        client_id: str | None = None,
        provider: str | None = None,
        event_type: str | None = None,
        status: str | None = None,
        account_address: str | None = None,
        external_id: str | None = None,
        network_id: str | None = None,
        tx_hash: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        include_resolution: bool = False,
    ) -> Any:
        """Transaction events (tx_evaluated, tx_submitted, tx_status_observed, tx_completed, tx_failed). Paginated: returns {events, nextCursor}. include_resolution adds the decoded intent (resolution, action, whitelisted) per row; the API only honours it once the Armory PR exposing `include=resolution` is deployed, older APIs ignore the param."""
        return self._get(
            "/events/transactions",
            self._params(
                dateFrom=date_from,
                dateTo=date_to,
                clientId=client_id,
                provider=provider,
                eventType=event_type,
                status=status,
                accountAddress=account_address,
                externalId=external_id,
                networkId=network_id,
                txHash=tx_hash,
                limit=limit,
                cursor=cursor,
                include="resolution" if include_resolution else None,
            ),
        )

    def filters(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        client_id: str | None = None,
        provider: str | None = None,
    ) -> Any:
        """Distinct values available for filtering in the window: clientIds, providers, connectionEventTypes, transactionEventTypes."""
        return self._get(
            "/filters",
            self._params(dateFrom=date_from, dateTo=date_to, clientId=client_id, provider=provider),
        )

    def digest(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        client_id: str | None = None,
        provider: str | None = None,
        max_pages: int = 5,
    ) -> dict[str, Any]:
        """Everything that happened in the window, structured client -> connection -> wallet -> transactions, plus connection events. No prose: the model writes the story. Each transaction carries resolution/action/whitelisted when the API returns them, null otherwise."""
        base = dict(date_from=date_from, date_to=date_to, client_id=client_id, provider=provider)

        summary = self.summary(**base)
        wallets = self.wallets(**base)
        tx_events = self._paginate(
            lambda cursor: self.transactions(**base, include_resolution=True, cursor=cursor, limit=500),
            max_pages,
        )
        conn_events = self._paginate(
            lambda cursor: self.connections(**base, cursor=cursor, limit=500),
            max_pages,
        )

        clients: dict[str, dict[str, Any]] = {}

        def client_node(cid: str, prov: str) -> dict[str, Any]:
            node = clients.get(cid)
            if node is None:
                node = {"client_id": cid, "providers": set(), "connections": {}}
                clients[cid] = node
            if prov:
                node["providers"].add(prov)
            return node

        def connection_node(cid: str, prov: str, conn_id: str | None) -> dict[str, Any]:
            cnode = client_node(cid, prov)
            key = conn_id or "(no connection)"
            node = cnode["connections"].get(key)
            if node is None:
                node = {"connection_id": conn_id, "wallets": {}, "connection_events": []}
                cnode["connections"][key] = node
            return node

        for row in tx_events:
            conn = connection_node(row.get("clientId", ""), row.get("provider", ""), row.get("connectionId"))
            addr = row.get("accountAddress") or "(unknown wallet)"
            wallet = conn["wallets"].get(addr)
            if wallet is None:
                wallet = {"account_address": row.get("accountAddress"), "networks": set(), "transactions": []}
                conn["wallets"][addr] = wallet
            if row.get("networkId"):
                wallet["networks"].add(row["networkId"])
            wallet["transactions"].append(
                {
                    "at": row.get("createdAt"),
                    "event_type": row.get("eventType"),
                    "status": row.get("status"),
                    "sub_status": row.get("subStatus"),
                    "rpc_method": row.get("rpcMethod"),
                    "to": row.get("toAddress"),
                    "hex_signature": row.get("hexSignature"),
                    "tx_hash": row.get("txHash"),
                    "external_id": row.get("externalId"),
                    "network": row.get("networkId"),
                    "error_code": row.get("errorCode"),
                    "error_message": row.get("errorMessage"),
                    "resolution": row.get("resolution"),
                    "action": row.get("action"),
                    "whitelisted": row.get("whitelisted"),
                }
            )

        for row in conn_events:
            conn = connection_node(row.get("clientId", ""), row.get("provider", ""), row.get("connectionId"))
            conn["connection_events"].append(
                {
                    "at": row.get("createdAt"),
                    "event_type": row.get("eventType"),
                    "status": row.get("status"),
                    "grant_id": row.get("grantId"),
                    "sub_grant_id": row.get("subGrantId"),
                    "wallet_count": row.get("walletCount"),
                    "ip_address": row.get("ipAddress"),
                    "error_code": row.get("errorCode"),
                    "error_message": row.get("errorMessage"),
                }
            )

        # Sets are not JSON; freeze them. Sort transactions and events by time.
        out_clients = []
        for cnode in clients.values():
            conns = []
            for conn in cnode["connections"].values():
                ws = []
                for w in conn["wallets"].values():
                    w["networks"] = sorted(w["networks"])
                    w["transactions"].sort(key=lambda t: t["at"] or "")
                    ws.append(w)
                conn["wallets"] = ws
                conn["connection_events"].sort(key=lambda e: e["at"] or "")
                conns.append(conn)
            cnode["providers"] = sorted(cnode["providers"])
            cnode["connections"] = conns
            out_clients.append(cnode)

        return {
            "window": {"date_from": date_from, "date_to": date_to, "client_id": client_id, "provider": provider},
            "summary": summary,
            "wallets": wallets,
            "clients": out_clients,
            "counts": {"transaction_events": len(tx_events), "connection_events": len(conn_events)},
        }

    # ----------------------------------------------------------------- private

    def _headers(self) -> dict[str, str]:
        key = secret(SECRET_NAME, "")
        if not key:
            raise RuntimeError(f"{SECRET_NAME} is unavailable")
        return {"x-api-key": key}

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        response = self._http.get(f"{PREFIX}{path}", params=params, headers=self._headers())
        response.raise_for_status()
        body = response.json()
        return body.get("data", body) if isinstance(body, dict) else body

    @staticmethod
    def _params(**kwargs: Any) -> dict[str, Any]:
        return {k: v for k, v in kwargs.items() if v is not None}

    @staticmethod
    def _paginate(fetch_page, max_pages: int) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        cursor: str | None = None
        for _ in range(max(1, max_pages)):
            page = fetch_page(cursor) or {}
            events.extend(page.get("events") or [])
            cursor = page.get("nextCursor")
            if not cursor:
                break
        return events


def _client() -> ConnectAnalyticsClient:
    return ConnectAnalyticsClient()
