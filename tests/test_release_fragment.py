"""A6: public-surface changes require a release fragment."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "check_release_fragment.py"


def _mod():
    spec = importlib.util.spec_from_file_location("check_release_fragment", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_cli_and_schemas_are_public():
    m = _mod()
    assert m.is_public("src/zero_employee/relay.py")
    assert m.is_public("src/zero_employee/runtimes/codex.py")
    assert m.is_public("src/zero_employee/schemas/executor.py")
    assert m.is_public("src/zero_employee/scaffold_templates/agents/zeo-stream.md")
    assert not m.is_public("tests/test_cli.py")
    assert not m.is_public("docs/tutorial.md")


def test_missing_fragment_fails(tmp_path):
    m = _mod()
    empty = tmp_path / "release"
    empty.mkdir()
    assert m.check(["src/zero_employee/cli.py"], empty) == 1


def test_fragment_allows_public_change(tmp_path):
    m = _mod()
    d = tmp_path / "release"
    d.mkdir()
    (d / "x.md").write_text("kind: minor\n\nnew verb\n", encoding="utf-8")
    assert m.check(["src/zero_employee/cli.py"], d) == 0
    assert m.fragment_kind(d) == "minor"


def test_no_user_change_marker(tmp_path):
    m = _mod()
    d = tmp_path / "release"
    d.mkdir()
    (d / "x.md").write_text("kind: no-user-change\n", encoding="utf-8")
    assert m.check(["src/zero_employee/hooks.py"], d) == 0


def test_internal_only_diff_does_not_need_fragment(tmp_path):
    m = _mod()
    empty = tmp_path / "release"
    empty.mkdir()
    assert m.check(["tests/test_foo.py", "docs/tutorial.md"], empty) == 0


def test_repo_fragment_is_minor():
    m = _mod()
    assert m.fragment_kind(_ROOT / ".release") == "minor"
