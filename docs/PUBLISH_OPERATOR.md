# Operator publish steps (credentials never in git)

Public source: https://github.com/sovereignagents/zero-employee

## TestPyPI

```bash
cd $(mktemp -d) && git clone git@github.com:sovereignagents/zero-employee.git && cd zero-employee
uv build
# leak-scan the wheel with the org instrument first
uv publish --publish-url https://test.pypi.org/legacy/ --token "$TEST_PYPI_TOKEN"

# Clean machine DoD
uv tool uninstall zero-employee 2>/dev/null || true
uv tool install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ zero-employee
zeo --board            # expect exit 2 + "couldn't find a corpus"
ZEO_SOWS_ROOT=/path/to/corpus zeo --board
sow-lint --help
```

## PyPI (after TestPyPI green)

```bash
uv publish --token "$PYPI_TOKEN"
# same clean-machine DoD from https://pypi.org
uv tool install zero-employee
```

Version `0.1.0` can only be uploaded once per index.
