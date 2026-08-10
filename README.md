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
| `zeo --digest` | Generate session commit digest and tree status. |
| `zeo --repo-cost` / `--session-cost` | Calculate USD cost proxies for LLM model token usage. |
| `zeo --resync-check` / `--resync-apply` | Check and apply inherited doctrine updates across projects. |
| `zeo hooks install` | Install thin git/session hook stubs + gitignore board files. |
| `zeo hooks pre-commit` | Pre-commit gate (unstage boards, regen locally, lint staged SOWs). |
| `zeo <path>` | Lint a single SOW, ruling, or skill file against strict schema rules. |

`zeo` accepts the same arguments as `zeo`.

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

* [Getting Started Guide](docs/getting-started.md) — Step-by-step onboarding for new corpora.
* [Release Process](docs/releasing.md) — Versioning, changelogs, and PyPI publishing.
* [Contributing Guidelines](CONTRIBUTING.md) — Code style, test expectations, and PR rules.

---

## License & Community

Distributed under the terms of the [MIT License](LICENSE).

* **Maintainer Email:** [zeroemployeeorg@dreamhuggers.com](mailto:zeroemployeeorg@dreamhuggers.com)
* **Organization:** [Zero Employee Organizations](https://zeroemployee.org)
