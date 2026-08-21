"""Opt-in IDE/agent bridges — modular, idempotent for personas."""

from __future__ import annotations

import pathlib

from zero_employee.scaffold import init_corpus, install_bridges, normalize_tools


def test_normalize_tools_all():
    assert normalize_tools(["all"]) == {"cursor", "codex", "gemini", "claude", "agents"}
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
    assert not (root / "AGENTS.md").exists()


def test_bridges_codex_only(tmp_path):
    """AGENTS.md bridge (developers.openai.com/codex/guides/agents-md, read 2026-08-21):
    a flat symlink to CLAUDE.md at repo root, same shape as the GEMINI.md bridge --
    Codex has no directory-of-rules convention analogous to `.cursor/rules/`.

    CODEX-SWAP-UX-SOW-1: `--codex` also installs the `.codex/agents/*.toml`
    human-in-the-loop persona layer (RULING-351 approach C) alongside the AGENTS.md
    instructions-parity symlink -- both ship from one flag, no separate opt-in."""
    root = tmp_path / "r"
    root.mkdir()
    (root / "CLAUDE.md").write_text("# x\n", encoding="utf-8")
    info = install_bridges(root, tools=["codex"])
    agents_md = root / "AGENTS.md"
    assert agents_md.is_symlink()
    assert agents_md.resolve() == (root / "CLAUDE.md").resolve()
    assert (root / ".codex" / "agents" / "zeo-master.toml").is_file()
    assert (root / ".codex" / "agents" / "zeo-stream.toml").is_file()
    assert (root / ".codex" / "agents" / "zeo-sparring.toml").is_file()
    assert "codex" in info["tools"]


def test_bridges_codex_personas_are_human_in_the_loop_only():
    """RULING-351 s8 Amendment 2 / RULING-353: a `.codex/agents/*.toml` persona loads
    only under an interactive Codex TUI session invoking it by name (approach C) --
    NOT under `codex exec`/GitHub Action (approach B), which runs a plain prompt and
    never reads a persona file at all. Each shipped persona must carry that caveat
    in its own text, not rely on a human remembering it from a ruling nobody re-reads."""
    templates_root = (
        pathlib.Path(__file__).resolve().parents[1] / "src" / "zero_employee" / "scaffold_templates" / "codex-agents"
    )
    for stem in ("zeo-master", "zeo-stream", "zeo-sparring"):
        text = (templates_root / f"{stem}.toml").read_text(encoding="utf-8")
        assert "RULING-351" in text, f"{stem}.toml must cite RULING-351"
        assert "codex exec" in text, f"{stem}.toml must name the approach-B trigger class it does NOT cover"
        assert "does NOT load a persona file" in text or "does not load a persona file" in text.lower(), (
            f"{stem}.toml must carry the approach-B persona-does-not-load caveat"
        )


def test_bridges_codex_personas_not_overwritten(tmp_path):
    root = tmp_path / "r"
    codex_agents = root / ".codex" / "agents"
    codex_agents.mkdir(parents=True)
    custom = codex_agents / "zeo-stream.toml"
    custom.write_text("CUSTOM\n", encoding="utf-8")
    install_bridges(root, tools=["codex"])
    assert custom.read_text(encoding="utf-8") == "CUSTOM\n"
    assert (codex_agents / "zeo-master.toml").is_file()
    assert (codex_agents / "zeo-sparring.toml").is_file()


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
