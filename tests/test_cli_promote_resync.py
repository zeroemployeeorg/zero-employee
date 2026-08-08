"""The CLI PATH for --promote and --resync-check.

WHY THESE EXIST: both flags shipped with their dispatch wired and their imports missing.
178 tests were green because every test called the CORE functions directly and none ever
invoked main(). A flag that raises NameError on its first real use is not shipped.
"""

import subprocess
import pytest
from zero_employee import cli


def _git(d, *a):
    subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n")
    d = tmp_path / "sow" / "seam"
    d.mkdir(parents=True)
    for name in ("SEAM-first.md", "SEAM-second.md"):
        (d / name).write_text(f"# {name}\nunique {name}\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "seed")
    return tmp_path


def test_promote_via_main_does_not_NameError_and_prints_a_plan(repo, capsys):
    rc = cli.main(["--promote", str(repo / "sow" / "seam")])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "PROMOTE-PLAN" in out and "DRY-RUN ONLY" in out


def test_promote_via_main_writes_NOTHING(repo, capsys):
    before = sorted(p.name for p in (repo / "sow" / "seam").iterdir())
    cli.main(["--promote", str(repo / "sow" / "seam")])
    capsys.readouterr()
    assert sorted(p.name for p in (repo / "sow" / "seam").iterdir()) == before


def test_resync_check_via_main_does_not_NameError(tmp_path, capsys):
    up = tmp_path / "up"
    dn = tmp_path / "dn"
    (up / "authoring").mkdir(parents=True)
    (dn / "authoring").mkdir(parents=True)
    (up / "authoring" / "a-SKILL.md").write_text("body\n", encoding="utf-8")
    import hashlib

    sha = hashlib.sha256((up / "authoring" / "a-SKILL.md").read_bytes()).hexdigest()
    (dn / "authoring" / "a-SKILL.md").write_text(f"UPSTREAM-SHA: {sha}\nbody\n", encoding="utf-8")
    rc = cli.main(["--resync-check", str(up), str(dn)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "RESYNC-CHECK" in out and "CURRENT" in out


def test_resync_check_exits_1_when_STALE(tmp_path, capsys):
    up = tmp_path / "up"
    dn = tmp_path / "dn"
    (up / "authoring").mkdir(parents=True)
    (dn / "authoring").mkdir(parents=True)
    (up / "authoring" / "a-SKILL.md").write_text("MOVED\n", encoding="utf-8")
    (dn / "authoring" / "a-SKILL.md").write_text("UPSTREAM-SHA: " + "0" * 64 + "\nbody\n", encoding="utf-8")
    rc = cli.main(["--resync-check", str(up), str(dn)])
    assert rc == 1, capsys.readouterr().out
