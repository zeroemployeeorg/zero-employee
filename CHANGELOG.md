# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
