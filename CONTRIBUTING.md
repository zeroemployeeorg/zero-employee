# Contributing to zero-employee

Thanks for considering a contribution. This project is pre-1.0 and moving fast, so a
few conventions keep changes easy to review and merge.

## Before you start

- **Bug reports and small fixes:** just open a PR, or an issue if you're not sure how
  to fix it yourself.
- **New features or behavior changes:** open an issue first describing what you want
  to do and why. This avoids the disappointment of a large PR built against a design
  the maintainers would have steered differently.
- **Security issues:** do not open a public issue — see [`SECURITY.md`](SECURITY.md).

## Local setup

```bash
git clone https://github.com/zeroemployeeorg/zero-employee.git
cd zero-employee

make setup      # creates a venv, installs the package + dev dependency group
```

This also installs the tracked git hooks (`.githooks/pre-commit`, `.githooks/pre-push`)
via `core.hooksPath` — `pre-commit` runs `ruff format`/`ruff check` on staged files
(fast, ~0.15s); `pre-push` runs the full test suite before anything leaves your
machine. Both mirror what CI checks, so a clean local push is a strong signal CI will
be clean too.

## Running the gate

```bash
make verify     # format-check + lint + full pytest suite -- the same gate as CI
```

Run this before opening a PR. If `make verify` is red, CI will be red on the same PR —
there's no advantage to pushing and hoping.

Individual pieces, if you want faster iteration while working:

```bash
make lint       # ruff check only
make test       # pytest only
make format     # auto-format + fix (not just check)
uv run python -m pytest tests/test_x.py -v   # one file, verbose
```

## Code style

- Formatting and linting are enforced by [`ruff`](https://github.com/astral-sh/ruff) —
  run `uv run ruff format .` before committing rather than hand-formatting.
- Type hints are expected on new code (the package ships `py.typed`). Prefer precise
  types over `Any` where the shape is genuinely known.
- Match the surrounding module's style for docstrings and comments — this codebase
  favors dense, incident-grounded comments ("measured: X happened, here's why the code
  guards against it") over generic restatement of what a line does.

## Tests

- New behavior needs a new test. A bug fix needs a regression test that fails against
  the old code and passes against the fix — don't just assert the new behavior exists,
  prove the old behavior was wrong.
- Tests live in `tests/`, one file per module or feature area (`test_cost.py`,
  `test_design_genre.py`, etc.) — follow the existing naming pattern rather than
  starting a new convention.
- Prefer real fixtures (a real `tmp_path` git repo, real file I/O) over mocks where the
  behavior under test is filesystem or git interaction — this codebase has repeatedly
  found real bugs that a mock would have hidden (see `CHANGELOG.md` for examples).

## Commit messages

- Keep the subject line under ~70 characters, in the imperative mood ("fix X", not
  "fixed X" or "fixes X").
- Explain *why*, not just *what*, in the body when the change isn't self-evident from
  the diff alone.
- Reference the issue number if one exists (`Fixes #123`).

## Pull request checklist

- [ ] `make verify` passes locally.
- [ ] New behavior has a test; bug fixes have a regression test.
- [ ] For a user-facing change, note it in your PR description so the maintainer can
      fold it into the next `CHANGELOG.md` entry at release time — see
      [`docs/releasing.md`](docs/releasing.md) for the format existing entries follow.
- [ ] No secrets, tokens, or credentials in the diff.
- [ ] Docs (`README.md`, `docs/`) updated if you changed a command's behavior or added
      a new one.

## Releasing

Only maintainers cut releases. If you're curious how it works — versioning policy, the
wheel leak-scan step, trusted publishing to PyPI — see
[`docs/releasing.md`](docs/releasing.md).

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating,
you're agreeing to uphold it.
