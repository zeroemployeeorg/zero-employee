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
zeo sow new ducktyper ui-refresh --title "UI Framework Refresh"
# or greenfield wrapper (also writes project CLAUDE.md):
zeo scaffold ducktyper ui-refresh 1 "UI Framework Refresh"
```

`zeo init` creates:

- `claude-md/CLAUDE.md` — corpus marker / doctrine (Rev 17 scaffold)
- `CLAUDE.md` — IDE entrypoint with `@import "claude-md/CLAUDE.md"`
- `projects/`, `ruling/`
- `.gitignore` entries for `STATE.md` and `stream-index.md` (local views — never commit)

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

## 5. Install hooks (recommended)

```bash
cd /path/to/corpus
zeo hooks install
```

This:

- Writes **thin** stubs under `tools/hooks/` (and `.git/hooks/pre-commit`) that call
  `zeo hooks <subcommand>` — gate logic lives in the package, so upgrading
  `zero-employee` updates hook behavior without re-copying scripts
- Ensures `.gitignore` ignores `STATE.md` and `stream-index.md`

Generated boards are **local views**. Run `zeo --board` / `zeo --stream-index` (or let
SessionStart / pre-commit refresh them). Do not commit them — that is what used to cause
merge conflicts for beginners.

If an older corpus still tracks those files:

```bash
git rm --cached STATE.md stream-index.md
```

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `couldn't find a corpus` | No `claude-md/CLAUDE.md` above cwd; set `ZEO_SOWS_ROOT` or pass a path |
| `sow-lint` not found after install | Ensure `~/.local/bin` (or uv tool bin) is on `PATH` |
| B2 / grandfather findings missing | Packaged manifest is empty; add corpus-local `tools/doctrine/grandfather_manifest.toml` |
| `scaffold: corpus marker missing` | Run `zeo init` first (needs `claude-md/CLAUDE.md`) |
