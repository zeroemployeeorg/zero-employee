"""zeo scaffold — project workstream SOW + optional bridges."""

from __future__ import annotations

import pytest

from zero_employee.scaffold import init_corpus, scaffold_project_stream


def test_scaffold_requires_corpus_marker(tmp_path):
    with pytest.raises(FileNotFoundError):
        scaffold_project_stream(tmp_path / "empty", "ducktyper", "ui-refresh")


def test_scaffold_creates_project_claude_and_sow(tmp_path):
    root = tmp_path / "org"
    init_corpus(root)
    info = scaffold_project_stream(
        root, "ducktyper", "ui-refresh", sow_num=1, title="UI Framework Refresh"
    )
    proj = root / "projects" / "ducktyper"
    assert (proj / "CLAUDE.md").is_file()
    assert '@import "../../claude-md/CLAUDE.md"' in (proj / "CLAUDE.md").read_text(encoding="utf-8")
    sow = proj / "sow" / "ui-refresh" / "ui-refresh-SOW-01-ui-framework-refresh.md"
    assert sow.is_file()
    body = sow.read_text(encoding="utf-8")
    assert "schema_rev: 17" in body
    assert "project: ducktyper" in body
    assert "sow: ui-refresh" in body
    assert info["sow"] == str(sow.relative_to(root))
    assert not (proj / ".cursor").exists()


def test_scaffold_with_cursor_on_project(tmp_path):
    root = tmp_path / "org"
    init_corpus(root)
    scaffold_project_stream(root, "zeo", "ledger", tools=["cursor"])
    proj = root / "projects" / "zeo"
    assert (proj / ".cursor" / "rules" / "000-governance.mdc").is_file()
    assert (proj / ".cursorrules").exists()


def test_scaffold_idempotent_sow(tmp_path):
    root = tmp_path / "org"
    init_corpus(root)
    first = scaffold_project_stream(root, "p", "s", title="Once")
    second = scaffold_project_stream(root, "p", "s", title="Once")
    assert first["created"]
    assert second["created"] == []
