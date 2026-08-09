# Changelog

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
