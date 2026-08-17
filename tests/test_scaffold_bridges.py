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
    assert (root / ".claude" / "hooks" / "check-trunk-guard.sh").is_file()
    assert (root / ".agents" / "zeo-verifier.md").is_file()
    assert not (root / ".cursor").exists()


def test_bridges_claude_settings_is_not_the_empty_stub(tmp_path):
    """REPO-EQUIP-SOW-1 s4/s5 regression: `zeo init --claude` must hand out the
    real deny list + trunk-guard wiring, not `{"permissions": {}}`."""
    root = tmp_path / "r"
    root.mkdir()
    (root / "CLAUDE.md").write_text("# x\n", encoding="utf-8")
    install_bridges(root, tools=["claude"])
    settings_text = (root / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert settings_text.strip() != '{\n  "permissions": {}\n}'
    assert "git reset --hard" in settings_text
    assert "check-trunk-guard.sh" in settings_text


def test_bridges_claude_trunk_guard_hook_is_executable(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    (root / "CLAUDE.md").write_text("# x\n", encoding="utf-8")
    install_bridges(root, tools=["claude"])
    guard = root / ".claude" / "hooks" / "check-trunk-guard.sh"
    assert guard.is_file()
    assert guard.stat().st_mode & 0o111, "trunk-guard hook must be installed executable"


def test_bridges_claude_trunk_guard_never_clobbers_existing(tmp_path):
    """s3's never-clobber-by-default rule applies to the hook file too, not just settings.json."""
    root = tmp_path / "r"
    root.mkdir()
    (root / "CLAUDE.md").write_text("# x\n", encoding="utf-8")
    hooks_dir = root / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)
    custom = hooks_dir / "check-trunk-guard.sh"
    custom.write_text("#!/usr/bin/env bash\n# CUSTOM\nexit 0\n", encoding="utf-8")
    install_bridges(root, tools=["claude"])
    assert custom.read_text(encoding="utf-8") == "#!/usr/bin/env bash\n# CUSTOM\nexit 0\n"


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
