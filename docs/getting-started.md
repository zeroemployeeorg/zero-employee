# Getting started

## 1. Install

```bash
uv tool install zero-employee
zeo --help
sow-lint --help   # permanent alias
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
zeo scaffold ducktyper ui-refresh 1 "UI Framework Refresh"
```

`zeo init` creates:

- `claude-md/CLAUDE.md` — corpus marker / doctrine (Rev 17 scaffold)
- `CLAUDE.md` — IDE entrypoint with `@import "claude-md/CLAUDE.md"`
- `projects/`, `ruling/`

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
zeo --board

# or
ZEO_SOWS_ROOT=/path/to/corpus zeo --board

# or
zeo --board /path/to/corpus
```

## 4. First useful commands

```bash
zeo --triage          # what needs attention
zeo --progress        # streams not at rest
zeo --restaufwand     # distance to done
zeo path/to/a-SOW.md  # lint one file
```

## 5. Optional: install hooks into the corpus

```bash
cd /path/to/corpus
zeo hooks install
```

This writes `tools/hooks/` templates (pre-commit, SessionStart, Stop, PreToolUse) that call
`zeo` / `sow-lint`, and installs `.git/hooks/pre-commit`.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `couldn't find a corpus` | No `claude-md/CLAUDE.md` above cwd; set `ZEO_SOWS_ROOT` or pass a path |
| `sow-lint` not found after install | Ensure `~/.local/bin` (or uv tool bin) is on `PATH` |
| B2 / grandfather findings missing | Packaged manifest is empty; add corpus-local `tools/doctrine/grandfather_manifest.toml` |
| `scaffold: corpus marker missing` | Run `zeo init` first (needs `claude-md/CLAUDE.md`) |
