# Contributing

## Setup

```bash
make setup          # uv venv + editable install + check-env
make verify         # format-check + lint + tests (when configured)
# or:
uv sync --group dev
uv run python -m pytest
```

## Layout

- Package import: `zero_employee` under `src/zero_employee/`
- CLIs: `zeo` and `sow-lint` (both entry points retained)
- Tests: `tests/`

## Rules of thumb

- Do not commit secrets or PyPI tokens.
- Prefer honest fail-closed messages when a corpus cannot be discovered.
- Run the org-private wheel leak scan before any public upload (see `docs/releasing.md`).
