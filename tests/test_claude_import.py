"""Local CLAUDE.md @import resolution (airgap-safe)."""

from __future__ import annotations

from zero_employee.core import parse_current_rev
from zero_employee.scaffold import init_corpus, read_doctrine, resolve_imports


def test_resolve_relative_import(tmp_path):
    base = tmp_path / "claude-md"
    base.mkdir()
    (base / "CLAUDE.md").write_text("DOC-DATE: (Rev 17, test)\nBODY\n", encoding="utf-8")
    entry = tmp_path / "CLAUDE.md"
    entry.write_text('@import "claude-md/CLAUDE.md"\n\nLOCAL\n', encoding="utf-8")
    text = resolve_imports(entry)
    assert "DOC-DATE: (Rev 17, test)" in text
    assert "BODY" in text
    assert "LOCAL" in text
    assert "@import" not in text
    assert parse_current_rev(read_doctrine(entry)) == 17


def test_resolve_missing_file(tmp_path):
    entry = tmp_path / "CLAUDE.md"
    entry.write_text('@import "missing.md"\n', encoding="utf-8")
    text = resolve_imports(entry)
    assert "missing" in text
    assert "<!--" in text


def test_resolve_cycle(tmp_path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text('@import "b.md"\nA\n', encoding="utf-8")
    b.write_text('@import "a.md"\nB\n', encoding="utf-8")
    text = resolve_imports(a)
    assert "cycle" in text
    assert "A" in text or "B" in text


def test_resolve_depth_cap(tmp_path):
    # Chain longer than max_depth
    prev = None
    for i in range(20):
        p = tmp_path / f"f{i}.md"
        if prev is None:
            p.write_text("LEAF\n", encoding="utf-8")
        else:
            p.write_text(f'@import "{prev.name}"\nN{i}\n', encoding="utf-8")
        prev = p
    text = resolve_imports(prev, max_depth=3)
    assert "depth exceeded" in text


def test_remote_import_skipped(tmp_path):
    entry = tmp_path / "CLAUDE.md"
    entry.write_text('@import "https://example.com/x.md"\nOK\n', encoding="utf-8")
    text = resolve_imports(entry)
    assert "remote not allowed" in text
    assert "OK" in text


def test_init_entrypoint_expands_to_rev(tmp_path):
    root = tmp_path / "org"
    init_corpus(root)
    rev = parse_current_rev(read_doctrine(root / "CLAUDE.md"))
    assert rev == 17
    rev2 = parse_current_rev(read_doctrine(root / "claude-md" / "CLAUDE.md"))
    assert rev2 == 17
