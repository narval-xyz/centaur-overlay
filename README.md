# centaur-overlay

Narval's organization overlay for [Centaur](https://github.com/paradigmxyz/centaur).

Org-specific tools, workflows, skills, and sandbox guidance live here so the
base platform stays a clean upstream. Nothing in this repo is forked from
`paradigmxyz/centaur` — it is layered on top of it at runtime.

## How it is delivered

repo-cache, not an overlay image. A DaemonSet in the cluster keeps every source
repo checked out on each node; the API and sandbox pods read those checkouts
directly. A merge to `main` reaches new sandboxes on the next sync (30s), with
no image build and no redeploy.

```text
narval-xyz/centaur-overlay (main)
    |
    v  repo-cache DaemonSet
    |
    +-- /var/lib/centaur/repos/narval-xyz/centaur-overlay   (API: tool + workflow discovery)
    +-- /home/agent/github/narval-xyz/centaur-overlay       (sandbox: skills, prompts, workflow-host)
```

The deprecated `overlay.image.*` path is not used here.

## Layout

```text
.
├── .agents/skills/          # skills copied into every sandbox workspace
│   └── knowledge-base/      # how agents read the narval-xyz/knowledge vault
├── services/sandbox/
│   └── SYSTEM_PROMPT.md     # appended to the base sandbox system prompt
├── tools/                   # API-discovered tools (one dir per tool, each with pyproject.toml)
├── workflows/               # durable workflows (one .py per workflow)
└── tests/
```

Directories this repo does not contain are skipped at runtime, so an empty
`tools/` or `workflows/` costs nothing.

## Helm wiring

Configured on the deployment in `contrib/chart/values.local.yaml`:

```yaml
overlays:
  sources:
    - repo: paradigmxyz/centaur
      ref: ""
    - repo: narval-xyz/centaur-overlay
      ref: main
    - repo: narval-xyz/knowledge
      ref: main
      toolsSubdir: ""
      workflowsSubdir: ""
      skillsSubdir: ""
```

Order matters: later sources shadow earlier ones when a tool, workflow, or skill
name collides. `paradigmxyz/centaur` must stay listed first — the chart only
falls back to `toolServer.repo` when `overlays.sources` is empty, so omitting it
silently drops the base tool set.

`narval-xyz/knowledge` is a content-only source. All three subdirs are disabled
so its `.claude/skills/` (written for Claude Code, where the vault is the
working directory) do not leak into sandboxes; the `knowledge-base` skill here
points agents at the mount instead.

## Adding a tool

One directory under `tools/`, with a `pyproject.toml` declaring its secrets:

```toml
[tool.centaur]
secrets = ["EXAMPLE_API_KEY"]
```

Then grant it to a principal on the deployment:

```bash
centaur-perms --source-policy onepassword --op-vault centaur \
  principals grant <foreign-id> --tool <name>
```

Keep credentials out of this repository. Tools request secrets through Centaur's
secret system; the sandbox only ever sees a placeholder that iron-proxy
substitutes on the wire.

## Tools

### connect-analytics

Reads the Connect analytics reporting endpoints on the production Armory API
(`api.narval.xyz`, `GET /v1/management/connect-analytics/*`): summary per dApp,
active wallets, connection events (grants, denials, revocations), transaction
events, and a `digest` that structures a period as client -> connection ->
wallet -> transactions for the agent to narrate. Skill:
`.agents/skills/connect-analytics/SKILL.md`.

Secret: `CONNECT_ANALYTICS_API_KEY`, sent as `x-api-key`, injected by iron-proxy
only towards `api.narval.xyz`. It is the Armory admin API key and opens every
`/v1/management/*` route, not only analytics. The grant must carry a request
rule restricting it to method `GET` and path `/v1/management/connect-analytics/*`.
Do not grant it without that rule.

`transactions --include-resolution` and `digest` return the decoded intent per
transaction (`resolution`, `action`, `whitelisted`) once
narval-xyz/armory-internal#1060 is deployed. Until then the API ignores the
parameter and the fields come back `null`; the skill tells the agent to say so.

## Verify a change landed

From the API pod — tool and workflow discovery:

```bash
kubectl exec -n centaur deploy/centaur-centaur-api-rs -- sh -lc '
  echo "$TOOL_DIRS"; echo "$WORKFLOW_DIRS"'
```

From a sandbox — skills and prompt:

```bash
kubectl exec -n centaur <asbx-pod> -c agent -- sh -lc '
  echo "$CENTAUR_SKILL_DIRS"
  find /workspace/.agents/skills -maxdepth 2 -name SKILL.md | sort'
```

If a tool or workflow is missing, check `/var/lib/centaur/repos/...` in the API
container. If a skill or prompt is missing, check `/home/agent/github/...` in
the sandbox. The two mounts are different surfaces of the same cache.

## Local checks

```bash
uv run pytest
```
