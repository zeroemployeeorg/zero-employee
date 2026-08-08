"""zeo init — corpus skeleton without tool-bridge clutter by default."""

from __future__ import annotations

from zero_employee.scaffold import init_corpus


def test_init_corpus_core_only(tmp_path):
    root = tmp_path / "org"
    info = init_corpus(root)
    assert (root / "claude-md" / "CLAUDE.md").is_file()
    assert (root / "CLAUDE.md").is_file()
    assert (root / "projects").is_dir()
    assert (root / "ruling").is_dir()
    assert "@import" in (root / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Rev 17" in (root / "claude-md" / "CLAUDE.md").read_text(encoding="utf-8")
    assert not (root / ".cursor").exists()
    assert not (root / ".agents").exists()
    assert not (root / "GEMINI.md").exists()
    assert info["bridges"]["tools"] == []
    assert "claude-md/CLAUDE.md" in info["created"]


def test_init_idempotent(tmp_path):
    root = tmp_path / "org"
    init_corpus(root)
    again = init_corpus(root)
    assert again["created"] == []


def test_init_with_all_bridges(tmp_path):
    root = tmp_path / "org"
    init_corpus(root, tools={"all"})
    assert (root / ".cursor" / "rules" / "000-governance.mdc").is_file()
    assert (root / ".cursorrules").exists()
    assert (root / "GEMINI.md").exists()
    assert (root / ".claude" / "settings.json").is_file()
    assert (root / ".agents" / "zeo-architect.md").is_file()
    assert (root / ".agents" / "zeo-claimant.md").is_file()
    assert (root / ".agents" / "zeo-verifier.md").is_file()
