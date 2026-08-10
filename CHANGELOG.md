# Changelog

## [0.1.6] - 2026-08-10

### Added
- **Intake Capture (`zeo intake new` / `open` / `edit`):** Frictionless capture of intent before identity is known. Supports positional titles, CLI flags, `$EDITOR` templates, raw stdin, and JSON specs.
- **Grounded Promote (`zeo intake promote`):** High-assurance promotion of intake items into governed SOWs, grounded in validated repository evidence and proposals stored under `.zeo/intake-proposals/`.
- **Mission & Context Protocol (`zeo intake mission` / `context`):** Structured JSON retrieval protocol for coding agents to investigate codebase context before submitting grounded proposals.
- **Intake Schema & Status Normalization:** Lightweight intake grader with canonical write status enum (`OPEN`, `PROMOTED`, `DUPLICATE`, `REJECTED`, `PARKED`) and read normalization for legacy statuses (`CHARTERED`, `DECLINED`, `SUPERSEDED`).
- **Scaffold Doctrine Update:** Embedded core intake doctrine principles in `scaffold_templates/claude-md/CLAUDE.md`.


## [0.1.5] - 2026-08-09

### Added
- **SOW Authoring Ergonomics (`zeo sow new / set / draft`):** ZEO now owns Rev-17 frontmatter serialization, numbering, and transactional writes so agents only supply semantic values without hand-writing YAML.
- **`zeo doctor` CLI Command:** Added structural health checking and automatic repair filters for working trees and SOW drafts.
- **Transactional Frontmatter Validation:** Rejects improper frontmatter in body content prior to file creation or modification, leaving zero partial artifacts on failure.


## [Unreleased]

### Added
- **Intake capture + grounded promote:** `zeo intake new|open|doctor|context|mission|propose|promote`
  (and `zeo intake "title"`). Capture is frictionless; promotion requires evidence-backed
  proposals from a coding agent. ZEO validates receipts, allocates SOW identity, and writes
  Rev-17 frontmatter. Alias: `zeo sow from-intake`.
- **SOW authoring ergonomics:** `zeo sow new|set|add|remove|draft` and `zeo doctor[--changed]`.
  ZEO serializes Rev-17 YAML, allocates `n`/filenames, validates transactionally, and (for draft)
  runs an Ollama body-only peer loop. Agents supply semantic values; ZEO owns governance syntax.
- Shared `sow_authoring` write substrate + `ollama_client`; scaffold/mint reuse the serializer.
- `zeo init` scaffolds `intake/` and gitignores `.zeo/` proposal cache.

### Changed
- Canonical SOW filenames zero-pad `n` (`SOW-01`); `zeo scaffold` wraps `sow new`.
- Intake status vocabulary: `OPEN|PROMOTED|DUPLICATE|REJECTED|PARKED` (legacy
  `CHARTERED|DECLINED|SUPERSEDED` accepted as aliases on read).

## [0.1.4] - 2026-08-09

### Added
- **Zero-Friction Git Flow:** `zeo hooks install` now automatically configures a `zeo-auto` git merge driver to silently bypass `STATE.md` and `stream-index.md` conflicts.
- **Auto-Regeneration:** Pre-commit hooks now automatically rebuild and stage `STATE.md` and `stream-index.md` on every commit, ensuring the board is always accurate without manual intervention.

### Changed
- Refactored `pre-commit` into a thin wrapper pattern that delegates execution entirely to the `zeo` binary, ensuring git hooks update automatically when the Python package is upgraded.


## [0.1.3] - 2026-08-09

### Added

- Thin-wrapper corpus hooks: installed stubs only `exec zeo hooks <subcommand>`; gate and
  orientation logic live in the package so upgrades update students without reinstalling
  script bodies (`pre-commit`, `session-start`, `stop`, `pretooluse-git`).
- `zeo hooks pre-commit|session-start|stop|pretooluse-git` runners.
- Automatic `.gitignore` entries for `STATE.md` and `stream-index.md` from `zeo init` and
  `zeo hooks install` (boards are local views, not shared git artifacts).

### Changed

- Pre-commit unstages generated boards if staged, regenerates them locally (fail-open), and
  never `git add`s them — beginners no longer hit `STATE.md` merge conflicts.
- Docs: getting-started recommends hooks install; boards documented as gitignored local views.

### Migration (existing corpora that still track boards)

```bash
git rm --cached STATE.md stream-index.md
zeo hooks install
```

## [0.1.2] - 2026-08-09

### Added
- Parallel `ThreadPoolExecutor` pre-commit gate checking in `.git/hooks/pre-commit` to prevent timeouts on batch commits.
- Deterministic Rev 17 frontmatter injection support for pre-schema SOWs.
- Automatic `done_when` and `restaufwand` frontmatter enforcement for active working SOWs.

### Changed
- Improved `-RevN` suffix validation and stream identity resolution in `zeo --commit-check`.
- Canonical filename promotion support across active project workstreams.


All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] — 2026-08-09

### Added

- Document `zeo init`, `zeo scaffold`, and `zeo bridges` (corpus/project scaffolding with
  opt-in IDE bridges). These verbs shipped on the 0.1.0 surface but were omitted from the
  prior changelog notes.
- Local `@import "rel/path"` doctrine expansion via `read_doctrine()` (airgap-safe; no HTTP).
- Packaged scaffold templates and personas (`zeo-architect` / `zeo-claimant` / `zeo-verifier`).
- OIDC trusted-publishing workflow (`.github/workflows/publish.yml`) and release docs.

### Changed

- README rebrand with command reference for scaffold verbs.
- Richer PyPI metadata (authors, classifiers, project URLs).
- Release docs point at the `zeroemployeeorg/zero-employee` GitHub org.

## [0.1.0] — 2026-08-08

### Added

- First public release of `zero-employee` (CLI: `zeo`, alias: `sow-lint`).
- Import package renamed to `zero_employee` for a consistent public surface.
- Session/repo cost proxies (`--repo-cost`, `--session-cost`) with dated model rates.
- `--resync-apply` and `zeo hooks install` for doctrine re-derive and hook templates.
- Honest no-corpus failure for `--board` / discovery verbs.
- Packaged empty grandfather manifest; corpora may override via
  `tools/doctrine/grandfather_manifest.toml` or `ZEO_GRANDFATHER_MANIFEST`.

### Changed

- Public wheel sanitized: identity strings redacted; internal ruling/stream citations
  generalized for open-source distribution.

### Notes

- Dependencies: `pyyaml`, `pydantic`, `tiktoken` (intentional; required by shipped features).
