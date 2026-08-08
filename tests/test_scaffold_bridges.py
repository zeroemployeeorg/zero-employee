"""Opt-in IDE/agent bridges — modular, idempotent for personas."""

from __future__ import annotations

from zero_employee.scaffold import init_corpus, install_bridges, normalize_tools


def test_normalize_tools_all():
    assert normalize_tools(["all"]) == {"cursor", "gemini", "claude", "agents"}
    assert normalize_tools(["cursor", "gemini"]) == {"cursor", "gemini"}
    assert normalize_tools(None) == set()
    assert normalize_tools(["nope"]) == set()


def test_bridges_noop_without_tools(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    info = install_bridges(root, tools=[])
    assert info["actions"] == []
    assert not (root / ".cursor").exists()


def test_bridges_cursor_only(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    (root / "CLAUDE.md").write_text("# x\n", encoding="utf-8")
    info = install_bridges(root, tools=["cursor"])
    assert (root / ".cursor" / "rules" / "000-governance.mdc").is_file()
    assert (root / ".cursorrules").exists()
    assert not (root / "GEMINI.md").exists()
    assert not (root / ".agents").exists()
    assert "cursor" in info["tools"]


def test_bridges_gemini_claude_agents(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    (root / "CLAUDE.md").write_text("# x\n", encoding="utf-8")
    install_bridges(root, tools=["gemini", "claude", "agents"])
    assert (root / "GEMINI.md").exists()
    assert (root / ".claude" / "settings.json").is_file()
    assert (root / ".agents" / "zeo-verifier.md").is_file()
    assert not (root / ".cursor").exists()


def test_bridges_personas_not_overwritten(tmp_path):
    root = tmp_path / "r"
    agents = root / ".agents"
    agents.mkdir(parents=True)
    custom = agents / "zeo-architect.md"
    custom.write_text("CUSTOM\n", encoding="utf-8")
    install_bridges(root, tools=["agents"])
    assert custom.read_text(encoding="utf-8") == "CUSTOM\n"
    assert (agents / "zeo-claimant.md").is_file()


def test_init_then_bridges_cursor(tmp_path):
    root = tmp_path / "org"
    init_corpus(root)
    install_bridges(root, tools=["cursor"])
    assert (root / ".cursor" / "rules" / "000-governance.mdc").is_file()
    text = (root / ".cursor" / "rules" / "000-governance.mdc").read_text(encoding="utf-8")
    assert "alwaysApply: true" in text
    assert "@CLAUDE.md" in text
