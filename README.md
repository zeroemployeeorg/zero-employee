# zero-employee

Portable governance tooling for Statement-of-Work (SOW) corpora. Install the package, point it at a corpus, and use the `zeo` CLI (the `sow-lint` command is retained as a permanent alias).

## Install

```bash
uv tool install zero-employee
# or: pip install zero-employee
```

Requires Python 3.11+.

## Quick start

`zeo` discovers a corpus by walking up from the current directory looking for `claude-md/CLAUDE.md`. You can also set `ZEO_SOWS_ROOT` or pass a path.

```bash
# From inside a corpus (or with ZEO_SOWS_ROOT set):
zeo --board
zeo --triage
zeo --help

# From anywhere:
zeo --board /path/to/corpus
ZEO_SOWS_ROOT=/path/to/corpus zeo --triage
```

If no corpus is found, `zeo --board` exits non-zero with a clear message — it does not invent a board.

## Commands (selection)

| Command | Purpose |
| --- | --- |
| `zeo --board` | Regenerate the fleet board (`STATE.md`) |
| `zeo --triage` | Operator worklist |
| `zeo --digest` | Session digest |
| `zeo --repo-cost` / `--session-cost` | Token×USD cost proxies |
| `zeo --resync-check` / `--resync-apply` | Inherited doctrine sync |
| `zeo hooks install` | Install corpus hook templates |
| `zeo <path>` | Lint a SOW / ruling / skill file |

`sow-lint` accepts the same arguments as `zeo`.

## Documentation

- [Getting started](docs/getting-started.md) — from-scratch onboarding
- [Releasing](docs/releasing.md) — versioning, changelog, TestPyPI → PyPI
- [Contributing](CONTRIBUTING.md) — local development

## License

MIT
