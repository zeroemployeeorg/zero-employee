# Releasing zero-employee

## Versioning

- Public semver starts at **0.1.0**.
- **PATCH** — bugfixes, docs, leak-scan hardening.
- **MINOR** — features (new verbs, non-breaking CLI).
- **MAJOR** — breaking CLI or import changes (allowed in 0.x with a clear changelog note).
- Single source of truth: `version` in `pyproject.toml`. Sync tags as `vX.Y.Z`.

## Checklist (every release)

1. **Leak scan the wheel** (org-private instrument):
   ```bash
   uv build
   bash path/to/org/tools/stream-instruments/zeo-wheel-leak-scan.sh dist/zero_employee-*.whl
   ```
   Class-1 must be empty. Class-2/3 must meet the generalization bar.
2. Bump `version` in `pyproject.toml`.
3. Update `CHANGELOG.md`.
4. `make verify` (or `uv run python -m pytest` + ruff as configured).
5. Tag `vX.Y.Z` on the release commit.
6. **TestPyPI first** (operator credentials):
   ```bash
   uv publish --publish-url https://test.pypi.org/legacy/
   # clean machine:
   uv tool install --index-url https://test.pypi.org/simple/ \
     --extra-index-url https://pypi.org/simple/ zero-employee
   zeo --board          # must fail honestly without a corpus
   ZEO_SOWS_ROOT=... zeo --board
   sow-lint --help
   ```
7. **PyPI** (operator act; version numbers are permanent):
   ```bash
   uv publish
   ```
8. Clean-machine DoD from real PyPI (both halves + `sow-lint` alias).

## Credentials

Never commit tokens. Prefer Trusted Publishing or a short-lived API token in the
operator's environment. Agents must not hold or echo publish credentials.
