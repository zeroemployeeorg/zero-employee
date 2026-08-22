# Releasing zero-employee

## Versioning

- Public semver starts at **0.1.0**.
- **PATCH** — bugfixes, docs, leak-scan hardening.
- **MINOR** — features (new verbs, non-breaking CLI).
- **MAJOR** — breaking CLI or import changes (allowed in 0.x with a clear changelog note).
  A 0.x break is still **breaking**, not silently `minor`.
- Single source of truth: `version` in `pyproject.toml`. Sync tags as `vX.Y.Z`.

## Release fragments (PR gate)

User-visible CLI, schema, scaffold template, hook, or exported Python API changes
must land with a file under [`.release/`](../.release/) that declares `kind:` as one of
`patch`, `minor`, `breaking`, or `no-user-change`. CI runs
`python scripts/check_release_fragment.py`. This is the PR-time declaration;
[`CHANGELOG.md`](../CHANGELOG.md) remains the human release note at version bump.

Public paths: `src/zero_employee/cli.py`, `schemas/`, `scaffold_templates/`,
`hooks.py`, `hooks_templates/`, `execution.py`, `dispatch.py`, `relay.py`,
`workspace.py`, `mcp_server.py`, `runtimes/`, `adapters/`,
and `__init__.py`.

## Trusted publishing (OIDC — no API tokens in the repo)

Publishing uses GitHub Actions OpenID Connect against pending/trusted publishers on
TestPyPI and PyPI. Workflow: [`.github/workflows/publish.yml`](../.github/workflows/publish.yml).
Environments on the GitHub repo must be named exactly **`testpypi`** and **`pypi`**.

### Pending publisher form values (register once on each index)

| Field | TestPyPI | PyPI (production) |
| --- | --- | --- |
| Project Name | `zero-employee` | `zero-employee` |
| Owner | `zeroemployeeorg` | `zeroemployeeorg` |
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
5. Commit the version bump + changelog on a branch, open a PR against
   `zeroemployeeorg/zero-employee` `main`, and merge it once `zeo`/`test`
   (the required status checks) pass and it's approved. **A direct push to
   `main` is rejected** — branch protection requires a PR (required PR
   review + required status checks, `enforce_admins: true`). This is a real
   change from earlier releases, made deliberately after `codex-concurrent-
   seating` found that neither Codex's sandbox nor this repo's own local
   config mechanically stopped a force-push to `main` for either tool.

### TestPyPI first

6. Actions → **Publish** → Run workflow → target **`testpypi`**.
7. Clean-machine DoD:
   ```bash
   uv tool uninstall zero-employee 2>/dev/null || true
   uv tool install --index-url https://test.pypi.org/simple/ \
     --extra-index-url https://pypi.org/simple/ zero-employee
   zeo --board          # expect exit 2 + "couldn't find a corpus"
   ZEO_SOWS_ROOT=/path/to/corpus zeo --board
   zeo --help           # confirm the console-script resolves cleanly, exit 0
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
   zeo --help           # confirm the console-script resolves cleanly, exit 0
   ```

Version numbers are permanent on each index — a bad upload cannot be un-shipped.

## Credentials

Never commit tokens. Prefer Trusted Publishing (this workflow). Agents must not hold or echo publish credentials.
