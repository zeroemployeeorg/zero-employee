# Releasing zero-employee

## Versioning

- Public semver starts at **0.1.0**.
- **PATCH** — bugfixes, docs, leak-scan hardening.
- **MINOR** — features (new verbs, non-breaking CLI).
- **MAJOR** — breaking CLI or import changes (allowed in 0.x with a clear changelog note).
- Single source of truth: `version` in `pyproject.toml`. Sync tags as `vX.Y.Z`.

## Trusted publishing (OIDC — no API tokens in the repo)

Publishing uses GitHub Actions OpenID Connect against pending/trusted publishers on
TestPyPI and PyPI. Workflow: [`.github/workflows/publish.yml`](../.github/workflows/publish.yml).
Environments on the GitHub repo must be named exactly **`testpypi`** and **`pypi`**.

### Pending publisher form values (register once on each index)

| Field | TestPyPI | PyPI (production) |
| --- | --- | --- |
| Project Name | `zero-employee` | `zero-employee` |
| Owner | `sovereignagents` | `sovereignagents` |
| Repository | `zero-employee` | `zero-employee` |
| Workflow name | `publish.yml` | `publish.yml` |
| Environment | `testpypi` | `pypi` |

- TestPyPI: https://test.pypi.org/manage/account/publishing/
- PyPI: https://pypi.org/manage/account/publishing/

### GitHub Environments

Create under **Repo → Settings → Environments** (or `gh api`):

- `testpypi` — no required reviewers (rehearsal)
- `pypi` — required reviewer recommended; restrict deploys to tags / `main`

## Checklist (every release)

1. **Leak scan the wheel** (org-private instrument):
   ```bash
   uv build
   bash path/to/org/tools/stream-instruments/zeo-wheel-leak-scan.sh dist/zero_employee-*.whl
   ```
2. Bump `version` in `pyproject.toml`.
3. Update `CHANGELOG.md`.
4. Ensure CI is green (`make verify` / pytest).
5. Commit and push to `sovereignagents/zero-employee` `main`.

### TestPyPI first

6. Actions → **Publish** → Run workflow → target **`testpypi`**.
7. Clean-machine DoD:
   ```bash
   uv tool uninstall zero-employee 2>/dev/null || true
   uv tool install --index-url https://test.pypi.org/simple/ \
     --extra-index-url https://pypi.org/simple/ zero-employee
   zeo --board          # expect exit 2 + "couldn't find a corpus"
   ZEO_SOWS_ROOT=/path/to/corpus zeo --board
   sow-lint --help
   ```

### Production PyPI

8. Tag and push (triggers production publish), **or** Run workflow → target **`pypi`**:
   ```bash
   git tag -a vX.Y.Z -m "zero-employee X.Y.Z"
   git push origin vX.Y.Z
   ```
9. Clean-machine DoD from real PyPI:
   ```bash
   uv tool install zero-employee
   zeo --board
   ZEO_SOWS_ROOT=/path/to/corpus zeo --board
   sow-lint --help
   ```

Version numbers are permanent on each index — a bad upload cannot be un-shipped.

## Credentials

Never commit tokens. Prefer Trusted Publishing (this workflow). Agents must not hold or echo publish credentials.
