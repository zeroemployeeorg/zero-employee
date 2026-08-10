# Getting started

## 1. Install

```bash
uv tool install zero-employee
zeo                  # orientation dashboard
zeo help             # progressive help
zeo help --all       # full command reference
```

## 2. Obtain a corpus

`zeo` grades and boards a **corpus**: a git repo whose root contains `claude-md/CLAUDE.md`
(plus `roles/`, `authoring/`, `projects/`, … as your org defines).

### Option A — scaffold a new corpus

```bash
mkdir my-org && cd my-org
zeo init
# optional IDE/agent bridges (opt-in; default is clean):
zeo init --cursor --gemini          # or: zeo bridges --all

# Then:
zeo                 # where am I / what next?
zeo new             # start intake, SOW, or project
```

`zeo init` creates:

- `claude-md/CLAUDE.md` — corpus marker / doctrine (Rev 17 scaffold)
- `CLAUDE.md` — IDE entrypoint with `@import "claude-md/CLAUDE.md"`
- `projects/`, `ruling/`, `intake/`
- `.gitignore` entries for `STATE.md`, `stream-index.md`, and `.zeo/` (local views/cache — never commit)

Tool bridges are **opt-in** via `--cursor`, `--gemini`, `--claude`, `--agents`, or `--all`:

| Flag | Artifacts |
| --- | --- |
| `--cursor` | `.cursor/rules/000-governance.mdc`, `.cursorrules` → `CLAUDE.md` |
| `--gemini` | `GEMINI.md` → `CLAUDE.md` |
| `--claude` | `.claude/settings.json` |
| `--agents` | `.agents/zeo-{architect,claimant,verifier}.md` |

Persona mapping (scaffold templates; product seats unchanged): architect ↔ structural/master-like authority; claimant ↔ stream drafting; verifier ↔ gate check. Product seats `zeo-master` / `zeo-sparring` / `zeo-stream` are not renamed by these commands.

### Option B — clone an existing corpus

Clone your org corpus separately if you already have one.

## 3. Point `zeo` at it

Any one of:

```bash
cd /path/to/corpus
zeo

# or
ZEO_SOWS_ROOT=/path/to/corpus zeo

# or
zeo board /path/to/corpus
```

## 4. First useful commands

```bash
zeo                     # orientation: where am I, what next?
zeo orient --json       # same briefing for agents (canonical first command)
zeo new                 # start intake / SOW / project
zeo work                # what can I pick up?
zeo next                # single highest-priority action
zeo triage              # operator worklist (also: zeo --triage)
zeo path/to/a-SOW.md    # lint one file
```

## 5. Install hooks (recommended)

```bash
cd /path/to/corpus
zeo hooks install
```

SessionStart runs the shared orientation model (same truth as `zeo` / `zeo orient`).
