"""RULING-216 s0/s1: check_ruling_corpus existed, was unit-tested, and was never reachable
from any real invocation - not `--commit-check` (expected: a single staged file's files_fm
can never hold two files), and not an ordinary full-corpus `zeo <dir>` run either,
because nothing called it. Wiring it into the corpus-level pass alongside check_corpus
surfaced a SECOND bug: its return dict was keyed by bare filename while the merge target
(per_file) is keyed by full path, so a naive wire-in silently dropped every finding into a
disconnected key nothing ever read. Both are pinned here at the CLI level, not just the
function level - a flag/wire-in that only passes a direct-call unit test is not shipped,
the same lesson test_cli_promote_resync.py exists to teach.
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
    return tmp_path


def _ruling(d, num, letter, scope="org"):
    d.mkdir(parents=True, exist_ok=True)
    (d / f"RULING-{num}-{letter}.md").write_text(
        f'---\nruling: "{num}"\ngenre: ruling\nstatus: ACTIVE\nlanding_commit: self\n'
        f"scope: {scope}\n"
        "requested_by: operator directive 2026-08-07 (test)\n---\n\nbody\n",
        encoding="utf-8",
    )


def test_a_full_corpus_run_catches_a_real_collision_end_to_end(repo, capsys):
    """The exact regression: before both fixes, this printed '2 passed - 0 failed'."""
    rd = repo / "ruling"
    _ruling(rd, "999", "a")
    _ruling(rd, "999", "b")
    rc = cli.main([str(repo)])
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "ruling-collision" in out
    assert "0 passed · 2 failed" in out or "2 failed" in out


def test_distinct_numbers_do_not_collide_via_the_real_cli(repo, capsys):
    rd = repo / "ruling"
    _ruling(rd, "997", "a")
    _ruling(rd, "998", "a")
    rc = cli.main([str(repo)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "ruling-collision" not in out


def test_same_number_across_project_scopes_is_legal_via_the_real_cli(repo, capsys):
    """RULING-200 s2, reproduced end to end through the real CLI, not just the function:
    the exact 93/95/96/97-shaped case that made an UNSCOPED version of this fix flood 28
    false positives against the real org corpus before this test existed."""
    org_rd = repo / "ruling"
    proj_rd = repo / "projects" / "ducktyper" / "ruling"
    _ruling(org_rd, "995", "org", scope="org")
    _ruling(proj_rd, "995", "dt", scope="project:ducktyper")
    rc = cli.main([str(repo)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "ruling-collision" not in out


def test_a_single_file_commit_check_target_cannot_see_the_collision(repo, capsys):
    """The bound RULING-216 s3(1) requires stating: a single staged file's files_fm has
    ONE entry, so check_ruling_corpus mathematically cannot fire here - this is the
    exact per-file blindness --commit-check-corpus exists to close from outside."""
    rd = repo / "ruling"
    _ruling(rd, "996", "a")
    _ruling(rd, "996", "b")
    rc = cli.main(["--commit-check", str(rd / "RULING-996-a.md")])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "ruling-collision" not in out
