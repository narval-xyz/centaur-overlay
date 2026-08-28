from dotenv import load_dotenv

load_dotenv()

import json  # noqa: E402
from typing import Optional  # noqa: E402

import typer  # noqa: E402

from .client import _client  # noqa: E402

app = typer.Typer(name="connect-analytics", help="Narval Connect analytics, read from the production Armory API.")


def _out(data) -> None:
    print(json.dumps(data, indent=2, default=str))


@app.command()
def summary(
    date_from: Optional[str] = typer.Option(None, "--date-from", help="ISO 8601"),
    date_to: Optional[str] = typer.Option(None, "--date-to", help="ISO 8601"),
    client_id: Optional[str] = typer.Option(None, "--client-id"),
    provider: Optional[str] = typer.Option(None, "--provider"),
) -> None:
    """Per client/provider counters for the window."""
    _out(_client().summary(date_from, date_to, client_id, provider))


@app.command()
def wallets(
    date_from: Optional[str] = typer.Option(None, "--date-from"),
    date_to: Optional[str] = typer.Option(None, "--date-to"),
    client_id: Optional[str] = typer.Option(None, "--client-id"),
    provider: Optional[str] = typer.Option(None, "--provider"),
) -> None:
    """Per wallet activity for the window."""
    _out(_client().wallets(date_from, date_to, client_id, provider))


@app.command()
def connections(
    date_from: Optional[str] = typer.Option(None, "--date-from"),
    date_to: Optional[str] = typer.Option(None, "--date-to"),
    client_id: Optional[str] = typer.Option(None, "--client-id"),
    provider: Optional[str] = typer.Option(None, "--provider"),
    event_type: Optional[str] = typer.Option(None, "--event-type", help="comma-separated"),
    status: Optional[str] = typer.Option(None, "--status"),
    grant_id: Optional[str] = typer.Option(None, "--grant-id"),
    connection_id: Optional[str] = typer.Option(None, "--connection-id"),
    limit: Optional[int] = typer.Option(None, "--limit"),
    cursor: Optional[str] = typer.Option(None, "--cursor"),
) -> None:
    """Connection events (grants, sub-grants, rotations, revocations)."""
    _out(
        _client().connections(
            date_from, date_to, client_id, provider, event_type, status, grant_id, connection_id, limit, cursor
        )
    )


@app.command()
def transactions(
    date_from: Optional[str] = typer.Option(None, "--date-from"),
    date_to: Optional[str] = typer.Option(None, "--date-to"),
    client_id: Optional[str] = typer.Option(None, "--client-id"),
    provider: Optional[str] = typer.Option(None, "--provider"),
    event_type: Optional[str] = typer.Option(None, "--event-type", help="comma-separated"),
    status: Optional[str] = typer.Option(None, "--status"),
    account_address: Optional[str] = typer.Option(None, "--account-address"),
    external_id: Optional[str] = typer.Option(None, "--external-id"),
    network_id: Optional[str] = typer.Option(None, "--network-id"),
    tx_hash: Optional[str] = typer.Option(None, "--tx-hash"),
    limit: Optional[int] = typer.Option(None, "--limit"),
    cursor: Optional[str] = typer.Option(None, "--cursor"),
    include_resolution: bool = typer.Option(False, "--include-resolution", help="Add decoded intent per row (needs the Armory PR deployed)"),
) -> None:
    """Transaction events (evaluated, submitted, observed, completed, failed)."""
    _out(
        _client().transactions(
            date_from,
            date_to,
            client_id,
            provider,
            event_type,
            status,
            account_address,
            external_id,
            network_id,
            tx_hash,
            limit,
            cursor,
            include_resolution,
        )
    )


@app.command()
def filters(
    date_from: Optional[str] = typer.Option(None, "--date-from"),
    date_to: Optional[str] = typer.Option(None, "--date-to"),
    client_id: Optional[str] = typer.Option(None, "--client-id"),
    provider: Optional[str] = typer.Option(None, "--provider"),
) -> None:
    """Distinct filter values in the window."""
    _out(_client().filters(date_from, date_to, client_id, provider))


@app.command()
def digest(
    date_from: Optional[str] = typer.Option(None, "--date-from"),
    date_to: Optional[str] = typer.Option(None, "--date-to"),
    client_id: Optional[str] = typer.Option(None, "--client-id"),
    provider: Optional[str] = typer.Option(None, "--provider"),
    max_pages: int = typer.Option(5, "--max-pages", help="pages of 500 events per stream"),
) -> None:
    """Structured digest: client -> connection -> wallet -> transactions, plus connection events."""
    _out(_client().digest(date_from, date_to, client_id, provider, max_pages))


if __name__ == "__main__":
    app()
