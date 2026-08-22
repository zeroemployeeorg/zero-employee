<div align="center">

# zero-employee

**Deterministic governance tooling for multi-agent software organizations.**

Schema-validated Statements of Work, cost tracking in tokens (not currency), fleet-wide
state boards, and IDE/agent bridge synchronization — enforced by a linter, not a wiki page.

[![CI](https://github.com/zeroemployeeorg/zero-employee/actions/workflows/ci.yml/badge.svg)](https://github.com/zeroemployeeorg/zero-employee/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/zero-employee.svg?color=blue)](https://pypi.org/project/zero-employee/)
[![Python Version](https://img.shields.io/pypi/pyversions/zero-employee.svg)](https://pypi.org/project/zero-employee/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Typed](https://img.shields.io/badge/typing-typed-blue.svg)](https://peps.python.org/pep-0561/)

[Website](https://zeroemployee.org) • [Documentation](https://zeroemployee.org/docs) • [Tutorial](docs/tutorial.md) • [Issues](https://github.com/zeroemployeeorg/zero-employee/issues)

</div>

---

## Why this exists

Multi-agent development produces a lot of work fast, and almost no durable record of *why*
any of it happened. A chat transcript is not an audit trail. A README that says "we do code
review" is not enforcement. `zero-employee` (`zeo`) makes the governance layer a **linter**,
not a policy document — every claim a stream makes about its own status, cost, and
dependencies is schema-checked before it's trusted, the same way `mypy` doesn't trust a
docstring over the type it contradicts.

- **Deterministic SOW linting.** Strict frontmatter schemas (`sow:`, `n:`, `status:`,
  `restaufwand:`, `done_when:`) validated on every commit, not sampled after the fact.
- **Cost in tokens, not dollars.** `--session-cost` / `--repo-cost` / `--kosten` track LLM
  spend against live rate cards; `--priority` ranks work with a stated, revisable formula
  instead of "whatever's loudest."
- **A fleet state board**, regenerated locally on demand (`zeo --board`), never committed —
  the board is a view over the corpus, not a second source of truth to drift from the first.
- **Zero-clutter scaffolding.** IDE and agent bridges (`--cursor`, `--codex`, `--gemini`,
  `--claude`, `--agents`) are opt-in; a fresh `zeo init` doesn't litter a repo with tool
  config nobody asked for.

```
              ┌─────────────────────────────────┐
              │       GOVERNANCE DOCTRINE        │
              │       (CLAUDE.md / Rulings)      │
              └────────────────┬────────────────┘
                               │
           RULINGS             │  ▲  SOWs
        (Top-to-Bottom)        │  │ (Bottom-to-Top)
        Mandates & Precedents  │  │ Status & Deliverables
                               ▼  │
              ┌────────────────┴────────────────┐
              │       PROJECT WORKSTREAMS        │
              │    (projects/<repo>/sow/...)     │
              └─────────────────────────────────┘
```

## Table of contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [Command reference](#command-reference)
- [Stream priority (Nutzwertanalyse)](#stream-priority-nutzwertanalyse)
- [Modular IDE & agent scaffolding](#modular-ide-agent-scaffolding)
- [`zeo equip` — overriding the shipped templates](#zeo-equip-overriding-the-shipped-templates)
- [Local development & testing](#local-development-testing)
- [Documentation & resources](#documentation-resources)
- [Contributing](#contributing)
- [License & community](#license-community)

---

## Installation

Install globally via [`uv`](https://github.com/astral-sh/uv) (recommended) or `pip`:

```bash
# Recommended (isolated global executable):
uv tool install zero-employee

# Standard pip install:
pip install zero-employee
```

> **Requirements:** Python 3.11+. The only CLI entry point is `zeo`.

---

## Quick start

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
zeo --help              # every top-level verb, one line each

# Target a specific corpus path from anywhere:
zeo board /path/to/corpus
ZEO_SOWS_ROOT=/path/to/corpus zeo triage
```

*If no corpus is found, `zeo` still orients you (suggests `zeo init`) and exits zero — it never hallucinates a board.*

*`zeo --help` (bare, no verb) is Typer-rendered: every top-level verb with its one-line purpose.
A verb's own `--help`/`-h` (`zeo orient --help`) is NOT intercepted by Typer — it passes straight
through to that verb's normal handler, same as any other argument, so a verb's real flag surface
lives in `zeo help --all`, not behind its own `--help`.*

---

## Command reference

| Command / Flag | Purpose |
| --- | --- |
| `zeo init [path]` | Scaffold corpus marker + `CLAUDE.md` (`@import`). Bridges are opt-in. |
| `zeo sow new <project> <stream> --title "..."` | Create a valid Rev-17 SOW without writing YAML. |
| `zeo sow set` / `add` / `remove` | Mutate frontmatter fields safely (`zeo` re-serializes YAML). |
| `zeo sow draft ...` | Ollama collaborative body draft; `zeo` owns frontmatter. |
| `zeo intake "…"` / `new` | Frictionless intent capture (no YAML; status OPEN). |
| `zeo intake mission` / `propose` / `promote` | Coding-agent protocol: investigate → grounded proposal → SOW. |
| `zeo sow from-intake FILE` | Lower-level alias for `zeo intake promote`. |
| `zeo doctor PATH` / `--changed` | Actionable readiness check for one SOW (or git-changed files). |
| `zeo scaffold <project> <stream>` | Greenfield wrapper: project `CLAUDE.md` + `sow new`. |
| `zeo bridges [flags]` | Install/resync IDE and agent bridges into an existing repository. |
| `zeo equip <repo> [--force\|--diff]` | Install `.claude/` (settings, trunk-guard hook, agents) + `CLAUDE.md` into a work repo; never clobbers by default. |
| `zeo cold-start <repo> [--sows-root PATH]` | Bounded, mechanical Ist-Aufnahme survey for a freshly-equipped repo with no SOW/ruling history — writes one report, zero commits into the surveyed repo. |
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

Run `zeo help --all` for the full, current list with flags — this table tracks the most-used
verbs, not every one that exists.

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
| Impact | Wesentlichkeit-gewichtetes Impact | 0.30 | How many OTHER streams cite this one via rulings' `binds:` field | A corpus-wide citation-graph scan (`_nwa_citation_graph`) reading the structured `binds:` list on rulings a stream's own requests produced. |
| Cost | Restaufwand | 0.25 *(inverted — sits in the denominator)* | Remaining work in TOKENS, not percent-complete | The stream's own `restaufwand:` field (RULING-202 s3's own unit) converted to tokens via `kosten()`'s per-claim token average for that stream. |
| Risk | Risiko | 0.15 | How many of the citing streams (above) are THEMSELVES currently `RULING-REQUESTED` and trace back to this one | The same citation-graph scan, counting only open, blocked dependents. |

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

## Modular IDE & agent scaffolding

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

# Add OpenAI Codex support (AGENTS.md symlink + .codex/agents/*.toml personas):
zeo scaffold ducktyper render-pipeline --codex

# Install the full agent & IDE bridge suite:
zeo scaffold ducktyper render-pipeline --all
```

`--codex` installs two layers:

- An `AGENTS.md` symlink pointing at `CLAUDE.md` (a plain text fallback file if the
  filesystem can't symlink) — Codex CLI's real discovery convention is a flat
  `AGENTS.md` at the project root, walked from the Git root down to `cwd`, with no
  directory-of-rules convention the way Cursor's `.cursor/rules/` has. Same
  thin-bridge shape as the `GEMINI.md` bridge, not a content fork.
- `.codex/agents/{zeo-master,zeo-stream,zeo-sparring}.toml` — Codex-native
  human-in-the-loop persona equivalents of the `.claude/agents/*.md` seats,
  generalized from the real, behaviorally-verified `zeo-stream.toml` persona this
  org shipped (RULING-351, RULING-353). **These personas load only under an
  interactive Codex TUI session where a human explicitly invokes one by name** —
  they do *not* load under `codex exec`/GitHub Action (non-interactive) dispatch,
  which runs a plain prompt and never reads a persona file at all (RULING-351 §8
  Amendment 2). Each shipped file carries this caveat in its own text. Never
  clobbers an existing file of the same name, same as the `--agents` bridge.

Supported bridge flags: `--cursor`, `--codex`, `--gemini`, `--claude`, `--agents`, `--all`.

---

## `zeo equip` — overriding the shipped templates

`zeo equip <repo>` installs the ALWAYS-tier `.claude/` + `CLAUDE.md` files (see
[Command Reference](#command-reference)) into a work repo. `zero-employee` is
MIT-licensed and distributed on PyPI, so any file it writes can be adapted to your
own org's needs **without forking the package** — a forked template silently opts
you out of every future improvement, which is worse than the drift it was meant to
avoid.

For each file `zeo equip` is about to **write** (never for a file the repo already
has — see "never clobbers" below), it resolves the content to use through a 4-level
precedence chain, first match wins:

1. **The repo's own file, if it already exists.** Reported `kept`, never touched,
   never read from as a content source. This is `zeo equip`'s "never clobber by
   default" guarantee (`--force` overwrites; `--diff` previews without writing) — it
   is not itself an override *source*, just the reason overrides never apply to a
   file you've already customized in place.
2. **`$ZEO_TEMPLATES_DIR`** — an environment variable pointing at a directory shaped
   like `scaffold_templates/` (e.g. `$ZEO_TEMPLATES_DIR/CLAUDE.md`,
   `$ZEO_TEMPLATES_DIR/claude-settings.json`). Explicit and highest-precedence among
   the override levels — set it in CI or a wrapper script to pin a specific org-wide
   template set.
3. **`~/.config/zeo/templates/`** — the same directory shape, per-user, for a
   developer's own standing preferences without needing an env var in every shell.
4. **The packaged default** (`zero_employee/scaffold_templates/`) — what ships in
   the wheel, used when neither override level has the file.

Every file `zeo equip` actually **writes** (from any of levels 2–4) is stamped with
an `UPSTREAM-SHA: <sha256 hex>` line (`#`-, `//`-, or `<!-- -->`-commented, matching
the file's own syntax), hashing the **content that was actually written** — an
override's own bytes, not the packaged default's. This is deliberate: once a future
`zeo --resync-check` gains visibility into `.claude/`, a template you've
*deliberately* overridden must grade as current against itself, not show up as
permanently "stale" against a packaged default you already chose not to use.

`.claude/settings.json` is the one exception to the comment-syntax list above: it is
strict JSON, live-loaded by Claude Code itself, which has no tolerance for `//` or
`/* */` comments. Its stamp lives in a top-level `"_upstreamSha"` string field
instead — real, hashed the same way, greppable — but not yet machine-discoverable by
the shared `UPSTREAM-SHA:` regex the way the other files' stamps are.

---

## Local development & testing

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

`make verify` runs `ruff format --check`, `ruff check`, and the full pytest suite
(790+ tests). This is the same gate CI runs on every push and pull request — a green
`make verify` locally means CI will be green too, not a hopeful guess.

---

## Documentation & resources

* [Tutorial](docs/tutorial.md) — A real, verified walkthrough: idea → grounded proposal → SOW → a design fork ruled and delivered → `--priority`. Start here if you want to see *why*, not just *what*.
* [Getting Started Guide](docs/getting-started.md) — Step-by-step onboarding for new corpora.
* [Release Process](docs/releasing.md) — Versioning, changelogs, and PyPI publishing.
* [Swapping to Codex](docs/codex-swap.md) — How to move a session from Claude Code to OpenAI Codex and back, with verified commands, known gaps, and honest open items.
* [Seat Identities](docs/seats.md) — `zeo seat`: give each seat its own real GitHub account, so a branch-protection review requirement is a genuine second check, not the same identity approving its own PR.
* [Changelog](CHANGELOG.md) — What shipped, release by release.
* [Contributing Guidelines](CONTRIBUTING.md) — Code style, test expectations, and PR rules.
* [Security Policy](SECURITY.md) — How to report a vulnerability.
* [Code of Conduct](CODE_OF_CONDUCT.md) — Community standards for this project.

---

## Contributing

Contributions are welcome — bug reports, documentation fixes, and pull requests alike.
Start with [CONTRIBUTING.md](CONTRIBUTING.md) for the local setup, test conventions, and
PR checklist. Every change needs a green `make verify` before review; the same gate runs
in CI so there's no separate "it works on my machine" step.

---

## License & community

Distributed under the terms of the [MIT License](LICENSE).

* **Maintainer Email:** [zeroemployeeorg@dreamhuggers.com](mailto:zeroemployeeorg@dreamhuggers.com)
* **Organization:** [Zero Employee Organizations](https://zeroemployee.org)
* **Security issues:** see [SECURITY.md](SECURITY.md) — please do not open a public issue for a vulnerability.
