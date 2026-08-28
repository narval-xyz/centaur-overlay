---
name: knowledge-base
description: "Read and search the Narval team knowledge base — an Obsidian-style vault of research notes on technologies, markets, companies, theses, problem-solutions, and design docs, mounted read-only in the sandbox. Use when a request asks what Narval knows or has written about a topic, company, protocol, or market; when answering would benefit from prior internal research; or when the user references a note, design doc, or thesis by name."
---

# Narval Knowledge Base

## Overview

The team knowledge base (`narval-xyz/knowledge`) is mounted in this sandbox at:

```text
/home/agent/github/narval-xyz/knowledge
```

It is a long-lived analytical resource — 90-odd markdown notes with YAML
frontmatter and `[[wikilinks]]`, PR-reviewed, maintained by the team. Consult it
before answering from general knowledge alone: a question about a company,
protocol, market structure, or in-flight design is often already covered there,
with the team's own framing and open questions.

If the directory does not exist, the overlay source is not configured on this
deployment. Say so rather than guessing at its contents.

## The mount is read-only in practice

repo-cache re-syncs the checkout on an interval and runs `git clean -fd`. Any
file you create or edit under that path is deleted on the next sync, usually
within a minute.

Never author notes there. If a request produces something worth keeping in the
vault, say so and hand back the note content — contributions go through a PR
against `narval-xyz/knowledge`, reviewed by Matt or Pierre.

## Layout

| Folder | Holds |
|--------|-------|
| `technology/` | Tech evaluations, protocols, tools, infrastructure |
| `market/` | Market structures, segments, dynamics, sizing |
| `company/` | Companies, projects, competitors |
| `thesis/` | Ideas, predictions, bets, hypotheses |
| `problem-solution/` | Problem definitions plus proposed solutions |
| `design-doc/<project>/` | Multi-document design proposals, grouped per project |
| `docs/` | Distillations of specific external documentation or SDKs |
| `_templates/` | Frontmatter schema per note type |

`CLAUDE.md` at the vault root is the canonical contributor guide. Read it when a
request touches vault conventions.

Filenames are `lowercase-kebab-case.md`. Every note carries `type`, `name`,
`category`, `created`, and `updated` in frontmatter.

## Searching

Prefer content search over directory listing — the folder is the note's type,
not its subject.

```bash
KB=/home/agent/github/narval-xyz/knowledge

# Full-text across the vault
rg -i -n 'durable nonce' "$KB" --glob '*.md'

# Restrict to a note type
rg -i -l 'perpetual' "$KB/market"

# Find a note by slug
find "$KB" -name '*bitgo*' -name '*.md'

# What links to a note (inbound wikilinks)
rg -n '\[\[agent-identity-and-auth\]\]' "$KB" --glob '*.md'

# Notes in a category
rg -n '^category:.*custody' "$KB" --glob '*.md'
```

Wikilinks are kebab-case slugs, so `[[agent-identity-and-auth]]` resolves to a
file named `agent-identity-and-auth.md` somewhere in the type folders. Follow
them — cross-links are where the vault's structure lives. An unresolved wikilink
is deliberate: it marks a gap the team has named but not yet written up.

## Using what you find

Cite the note by slug when you rely on it, so the reader can go look
(`per market/crypto-perpetual-futures.md`). Distinguish what the vault asserts
from what you are inferring.

Check `updated:` before treating a note as current. Anything over ~180 days is
considered stale by the team's own convention and may predate relevant changes.

Notes in `problem-solution/` and `design-doc/` are proposals written from
Narval's point of view, often co-authored with a counterparty. Notes in
`technology/`, `market/`, and `thesis/` are deliberately objective research and
carry no Narval framing — do not add one when summarizing them.
