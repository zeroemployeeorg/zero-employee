"""CLI smoke for zeo init / scaffold / bridges (imports must be wired)."""

from __future__ import annotations

from zero_employee import cli


def test_cli_init(tmp_path, capsys):
    root = tmp_path / "org"
    rc = cli.main(["init", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "INIT:" in out
    assert (root / "claude-md" / "CLAUDE.md").is_file()
    assert (root / "CLAUDE.md").is_file()
    assert "bridges: (none" in out


def test_cli_init_help_does_not_scaffold(tmp_path, capsys, monkeypatch):
    """RULING-329: `zeo init --help` in a directory with no existing corpus used to
    silently run the real scaffold instead of printing usage — `init` accepts ZERO
    required positionals (bare `zeo init` legitimately means "scaffold cwd"), so
    `--help` alone left `positionals` empty, indistinguishable from "no target,
    use cwd." Measured live: a real corpus got written to disk by `zeo init --help`
    in an empty directory. Pins both halves: rc==0 (help is not an error) and NO
    file/directory created anywhere under the target."""
    root = tmp_path / "org"
    root.mkdir()
    monkeypatch.chdir(root)
    rc = cli.main(["init", "--help"])
    out = capsys.readouterr()
    assert rc == 0
    assert "Usage: zeo init" in (out.out + out.err)
    assert list(root.iterdir()) == [], "‑‑help must never write to disk"


def test_cli_equip_help_does_not_write(tmp_path, capsys):
    """RULING-329's sibling case: `zeo equip --help` has the identical vulnerability
    shape (zero required positionals, bare `zeo equip` legitimately means "equip
    cwd") and used to fall through to the real installation the same way `init`
    did."""
    root = tmp_path / "work-repo"
    root.mkdir()
    before = set(root.iterdir())
    rc = cli.main(["equip", str(root), "--help"])
    out = capsys.readouterr()
    assert rc == 0
    assert "Usage: zeo equip" in (out.out + out.err)
    assert set(root.iterdir()) == before, "‑‑help must never write to disk"


def test_cli_init_all(tmp_path, capsys):
    root = tmp_path / "org"
    rc = cli.main(["init", str(root), "--all"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "cursor" in out
    assert (root / ".agents" / "zeo-architect.md").is_file()


def test_cli_scaffold(tmp_path, capsys):
    root = tmp_path / "org"
    assert cli.main(["init", str(root)]) == 0
    # Run scaffold with cwd = corpus
    import os

    old = os.getcwd()
    try:
        os.chdir(root)
        rc = cli.main(["scaffold", "ducktyper", "ui-refresh", "1", "UI Framework Refresh"])
    finally:
        os.chdir(old)
    out = capsys.readouterr().out
    assert rc == 0
    assert "SCAFFOLD:" in out
    sow = root / "projects" / "ducktyper" / "sow" / "ui-refresh"
    assert any(sow.glob("*.md"))


def test_cli_scaffold_usage(capsys):
    rc = cli.main(["scaffold", "only-one"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "Usage:" in err


def test_cli_bridges_requires_flags(tmp_path, capsys):
    root = tmp_path / "r"
    root.mkdir()
    rc = cli.main(["bridges", str(root)])
    assert rc == 2
    assert "Usage:" in capsys.readouterr().err


def test_cli_bridges_cursor(tmp_path, capsys):
    root = tmp_path / "r"
    root.mkdir()
    (root / "CLAUDE.md").write_text("#\n", encoding="utf-8")
    rc = cli.main(["bridges", str(root), "--cursor"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "BRIDGES:" in out
    assert (root / ".cursor" / "rules" / "000-governance.mdc").is_file()
