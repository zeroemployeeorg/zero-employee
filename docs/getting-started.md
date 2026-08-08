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

Clone or create that corpus separately. This package does not ship a sample org tree.

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
