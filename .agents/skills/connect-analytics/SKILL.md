---
name: connect-analytics
description: Answer "what happened on Narval Connect" questions (activity, wallets, transactions, who did what) with the connect-analytics tool.
---

# connect-analytics

Use this tool when someone asks what happened on Narval Connect in production: activity in a period, which wallets moved, which transactions were evaluated, submitted, completed or failed, which dApps (clients) and connections were involved, denials, revocations.

The tool reads the Armory production reporting API. It is read only. It never needs a key from you: the sandbox holds a placeholder and the proxy injects the real one.

## Commands

`connect-analytics --help` lists them. All take `--date-from` / `--date-to` (ISO 8601, default window: last 30 days), `--client-id`, `--provider`.

| Question | Command |
|---|---|
| How much happened, per dApp | `connect-analytics summary --date-from 2026-08-01` |
| Which wallets were active | `connect-analytics wallets --client-id <id>` |
| Who connected, who was denied, who revoked | `connect-analytics connections --event-type sub_grant_denied,connection_revoked` |
| Which transactions, with the decoded intent | `connect-analytics transactions --include-resolution --limit 200` |
| Follow one wallet | `connect-analytics transactions --account-address 0x... --include-resolution` |
| Follow one on-chain tx | `connect-analytics transactions --tx-hash 0x...` |
| Everything, structured for a narrative | `connect-analytics digest --date-from 2026-08-20 --date-to 2026-08-28` |

Start with `digest` for a "what happened" question. It returns client -> connection -> wallet -> transactions, plus connection events. Write the story from it; the tool never writes prose.

Pagination: `connections` and `transactions` return `{events, nextCursor}`. Pass `--cursor` to continue. `digest` follows up to `--max-pages` pages of 500 per stream.

## Reading the data

Identity is structural, not human. "Who" means: which client (dApp), which connection (a user's grant to their custodial account), which wallet, from which IP. There are no names.

Transaction lifecycle: `tx_evaluated` (intent decoded and policy checked) -> `tx_submitted` (sent to the custodian) -> `tx_status_observed` -> `tx_completed` or `tx_failed`. A `tx_evaluated` with `status=failed` and `errorCode=decode_failed` means the calldata could not be understood.

`resolution`, `action`, `whitelisted` on a transaction row are the decoded intent from Gatekeeper. They appear only when the Armory API supports `include=resolution` (pending PR). Until that is deployed the fields are `null`; say so instead of guessing what a transaction did. `hexSignature` (4 bytes) and `toAddress` are always there and let you name the function and the contract.
