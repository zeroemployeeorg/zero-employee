<div align="center">

Portable governance tooling for Statement-of-Work (SOW) corpora. Install the package, point it at a corpus, and use the `zeo` CLI (the `zeo` command is retained as a permanent alias).

**Portable, deterministic governance tooling and AI agent orchestration for Statement-of-Work (SOW) corpora.**

[![PyPI version](https://img.shields.io/pypi/v/zero-employee.svg?color=blue)](https://pypi.org/project/zero-employee/)
[![Python Version](https://img.shields.io/pypi/pyversions/zero-employee.svg)](https://pypi.org/project/zero-employee/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

[Website](https://zeroemployee.org) • [Documentation](https://zeroemployee.org/docs) • [Issues](https://github.com/zeroemployeeorg/zero-employee/issues)

</div>

---

## Overview

`zero-employee` (`zeo`) is the governance layer and linter for multi-agent software organizations. It enforces deterministic schema validation, cost tracking, state board generation, and IDE/agent bridge synchronization across your entire repository fleet.

```
              ┌─────────────────────────────────┐
              │       GOVERNANCE DOCTRINE       │
              │       (CLAUDE.md / Rulings)     │
              └────────────────┬────────────────┘
                               │
           RULINGS             │  ▲  SOWs
        (Top-to-Bottom)        │  │ (Bottom-to-Top)
        Mandates & Precedents  │  │ Status & Deliverables
                               ▼  │
              ┌────────────────┴────────────────┐
              │       PROJECT WORKSTREAMS       │
              │    (projects/<repo>/sow/...)    │
              └─────────────────────────────────┘
```

### Key Features
* **Deterministic SOW Linting:** Enforces strict frontmatter schemas (`sow:`, `n:`, `status:`, `restaufwand:`, `done_when:`).
* **Zero-Clutter Scaffolding:** Clean-by-default repository and workstream generation with opt-in IDE bridges (`--cursor`, `--gemini`, `--claude`, `--agents`).
* **Cost & Token Proxies:** Real-time token tracking (`--session-cost`, `--repo-cost`) with live rate cards.
* **Fleet State Board (`STATE.md`):** Local navigation board of active streams, open questions, and held workstreams (gitignored — regenerate with `zeo --board`, never commit).

---

## Installation

Install globally via [`uv`](https://github.com/astral-sh/uv) (recommended) or `pip`:

```bash
# Recommended (isolated global executable):
uv tool install zero-employee

# Standard pip install:
pip install zero-employee
```

> **Requirements:** Python 3.11 or higher.

---

## Quick Start

> **Want the real, worked walkthrough instead of a flag list?** See the [Tutorial](docs/tutorial.md) — every command in it was actually run and its real output is shown.

`zeo` discovers a corpus by walking up from the current directory looking for `claude-md/CLAUDE.md`. You can also set `ZEO_SOWS_ROOT` or pass an explicit path.

```bash
# From inside a corpus (or with ZEO_SOWS_ROOT set):
zeo                     # human orientation dashboard
zeo orient --json       # agent briefing (canonical first command)
zeo new                 # start intake / SOW / project
zeo work                # continue governed work
zeo triage              # what needs attention
zeo help                # progressive help
zeo help --all          # full command reference

# Target a specific corpus path from anywhere:
zeo board /path/to/corpus
ZEO_SOWS_ROOT=/path/to/corpus zeo triage
```

*If no corpus is found, `zeo` still orients you (suggests `zeo init`) and exits zero—it never hallucinates a board.*

---

## Command Reference

| Command / Flag | Purpose |
| --- | --- |
| `zeo init [path]` | Scaffold corpus marker + `CLAUDE.md` (`@import`). Bridges are opt-in. |
| `zeo sow new <project> <stream> --title "..."` | Create a valid Rev-17 SOW without writing YAML. |
| `zeo sow set` / `add` / `remove` | Mutate frontmatter fields safely (ZEO re-serializes YAML). |
| `zeo sow draft ...` | Ollama collaborative body draft; ZEO owns frontmatter. |
| `zeo intake "…"` / `new` | Frictionless intent capture (no YAML; status OPEN). |
| `zeo intake mission` / `propose` / `promote` | Coding-agent protocol: investigate → grounded proposal → SOW. |
| `zeo sow from-intake FILE` | Lower-level alias for `zeo intake promote`. |
| `zeo doctor PATH` / `--changed` | Actionable readiness check for one SOW (or git-changed files). |
| `zeo scaffold <project> <stream>` | Greenfield wrapper: project `CLAUDE.md` + `sow new`. |
| `zeo bridges [flags]` | Install/resync IDE and agent bridges into an existing repository. |
| `zeo --board` | Regenerate the local fleet state board (`STATE.md`, gitignored). |
| `zeo --stream-index` | Regenerate local `stream-index.md` (gitignored). |
| `zeo --triage` | Display operator worklist (open questions, held streams, unread rulings). |
| `zeo --priority [path]` | Nutzwertanalyse ranking of every OPEN/PAUSED/BLOCKED stream — see [Stream Priority](#stream-priority-nutzwertanalyse) below. |
| `zeo --digest` | Generate session commit digest and tree status. |
| `zeo --repo-cost` / `--session-cost` | Calculate USD cost proxies for LLM model token usage. |
| `zeo --kosten [stream]` | Corpus artifact token estimate (fixed tax, SOWs, rulings, waste) — feeds `--priority`'s Restaufwand criterion. |
| `zeo --resync-check` / `--resync-apply` | Check and apply inherited doctrine updates across projects. |
| `zeo hooks install` | Install thin git/session hook stubs + gitignore board files. |
| `zeo hooks pre-commit` | Pre-commit gate (unstage boards, regen locally, lint staged SOWs). |
| `zeo <path>` | Lint a single SOW, ruling, or skill file against strict schema rules. |

`zeo` accepts the same arguments as `zeo`.

---

## Stream Priority (Nutzwertanalyse)

`zeo --priority [path]` ranks every `OPEN`/`PAUSED`/`BLOCKED` stream so a Master
session has a stated, revisable reason for which stream gets the next session's
tokens, instead of `--triage`'s age-only ordering. It is a **separate verb from
`--triage` by design** — triage stays the fast, unopinionated worklist; priority
is the considered ranking you consult deliberately. It does not change
`--triage`'s own sort order.

Chartered by [`RULING-279`](../../ruling/RULING-279-nutzwertanalyse-stream-priority-in-tokens-not-currency.md)
("Nutzwertanalyse: ranking streams by token-denominated utility, not currency"),
built against [`PRIORITY-NWA-SOW-1`](../../projects/zero-employee/sow/priority-nwa/).
The method is Nutzwertanalyse (German: utility-value analysis) — a weighted
multi-criteria score, chosen over RICE (used elsewhere in this corpus, see
`RULING-278`) because stream prioritization is a recurring, live ranking over a
changing set of streams, not a one-shot scoring pass.

### The four criteria — **a first cut, explicitly flagged for revision (RULING-279 s5)**

| Criterion | German term | Weight | What it measures | Where the number comes from |
| --- | --- | --- | --- | --- |
| Urgency | Dringlichkeit | 0.30 | Age (days) of the oldest OPEN, unanswered/unresolved question on the stream | `awaiting_ruling()`'s own `updated:` field — the same data `--triage`'s NEEDS MASTER bucket reads. Reused, not recomputed. |
| Impact | Wesentlichkeit-gewichtetes Impact | 0.30 | How many OTHER streams cite this one via `requested_by:`, plus a bonus if `issue_first: true` | New: a corpus-wide citation-graph scan (`_nwa_citation_graph`) that extends the existing `requested_by` parsing rather than inventing a second citation grammar. |
| Cost | Restaufwand | 0.25 *(inverted — sits in the denominator)* | Remaining work in TOKENS, not percent-complete | The stream's own `restaufwand:` field (RULING-202 s3's own unit) converted to tokens via `kosten()`'s per-claim token average for that stream. |
| Risk | Risiko | 0.15 | How many of the citing streams (above) are THEMSELVES currently `RULING-REQUESTED` and trace back to this one | New: the same citation-graph scan, counting only open, blocked dependents. |

```
Nutzwert = (0.30 × Dringlichkeit_norm + 0.30 × Impact_norm + 0.15 × Risiko_norm)
           / Restaufwand_tokens
```

Dringlichkeit/Impact/Risiko are min-max normalized 0–1 **across the current live
stream set** (relative to what else is competing for tokens this round — the
Nutzwertanalyse convention, re-scored every run). Restaufwand sits directly in
the denominator (utility-per-cost, not utility-minus-cost) so the two are never
forced onto one invented exchange rate. **Tokens throughout, never currency** —
`--priority`'s own output never prints a `$` figure.

### When a stream declares no `restaufwand:` at all

A stream with no `restaufwand:` declaration and no `SHIPPED`/`FINDING` ledger
claims to derive a per-claim token average from still ranks — it never silently
drops out. Every row carries `restaufwand_estimate_kind`, one of:

- `PER-STREAM-CLAIM-AVG` — this stream's own tokens-per-claim figure.
- `CORPUS-CLAIM-AVG` — this stream declared `restaufwand:` but has no claims of
  its own yet; falls back to the corpus-wide average tokens-per-claim.
- `ESTIMATE-LOCAL-MEDIAN` — this stream has neither; falls back to the corpus
  median restaufwand-tokens as a last resort.

This mirrors `cost.py`'s own `tokenizer_label` discipline: a degraded estimate is
always visibly labeled, never a quiet number that looks as precise as a real one.

### Opportunity cost, stated not implied (RULING-279 s3)

Every `--priority` run prints the top-N **FUNDED** streams *and* the next-M
**OPPORTUNITÄTSKOSTEN** (opportunity cost) near-miss streams, each with its
Nutzwert delta to the last funded stream — so picking stream A is a visible,
stated decision not to fund stream B, C, D this round, not a hidden one.

```
zeo --priority                       # top 3 funded + next 3 near-miss, from cwd
zeo --priority --top 5 --near-miss 5 /path/to/corpus
zeo --priority --json                # machine-readable
```

**What this does NOT do** (`PRIORITY-NWA-SOW-1` s3): it never changes
`--triage`'s own sort order, never prints currency, and never runs a full
`ant`-CLI-equivalent credential resolution — a narrow, stated set of
remediation paths only.

**On the token credential (RULING-279 s4):** `--count-via anthropic` and
`--calibrate` (used by `--kosten`/`--repo-cost`, not by `--priority` itself)
call Anthropic's free `count_tokens` endpoint and need an API key. A live
Claude Code session's own credential is *not* exposed as an environment
variable by default — this is the tool's most common execution context, not
an edge case — so a missing key now fails loudly naming both remediation
paths (set `ANTHROPIC_API_KEY`, or install and authenticate the `ant` CLI),
and `--api-key-env <VARNAME>` lets a caller whose credential lives under a
different variable name use it, without a full credential-chain resolver.

---

## Modular IDE & Agent Scaffolding

Scaffolding commands stay **clean by default** to avoid polluting repositories with unused tool directories. You explicitly pass flags to generate tool-specific bridges:

```bash
# Clean SOW creation (no IDE clutter):
zeo sow new ducktyper render-pipeline --title "Render pipeline"

# Greenfield project+stream (also creates project CLAUDE.md):
zeo scaffold ducktyper render-pipeline

# Add Cursor MDC rules and .cursorrules symlink:
zeo scaffold ducktyper render-pipeline --cursor

# Add Gemini support:
zeo scaffold ducktyper render-pipeline --gemini

# Install the full agent & IDE bridge suite:
zeo scaffold ducktyper render-pipeline --all
```

Supported bridge flags: `--cursor`, `--gemini`, `--claude`, `--agents`, `--all`.

---

## Local Development & Testing

We use `uv` and `make` for deterministic, hermetic local builds:

```bash
# Clone repository
git clone https://github.com/zeroemployeeorg/zero-employee.git
cd zero-employee

# Setup virtualenv and install dependencies
make setup

# Run linting and test suite
make verify
```

---

## Documentation & Resources

* [Tutorial](docs/tutorial.md) — A real, verified walkthrough: idea → grounded proposal → SOW → a design fork ruled and delivered → `--priority`. Start here if you want to see *why*, not just *what*.
* [Getting Started Guide](docs/getting-started.md) — Step-by-step onboarding for new corpora.
* [Release Process](docs/releasing.md) — Versioning, changelogs, and PyPI publishing.
* [Contributing Guidelines](CONTRIBUTING.md) — Code style, test expectations, and PR rules.

---

## License & Community

Distributed under the terms of the [MIT License](LICENSE).

* **Maintainer Email:** [zeroemployeeorg@dreamhuggers.com](mailto:zeroemployeeorg@dreamhuggers.com)
* **Organization:** [Zero Employee Organizations](https://zeroemployee.org)
