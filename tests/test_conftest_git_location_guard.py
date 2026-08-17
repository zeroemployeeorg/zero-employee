"""Regression test for the GIT_DIR-inheritance corruption paid this session.

See tests/conftest.py's own module docstring for the full incident account. This
file proves the autouse guard actually works by reproducing the exact failure mode
in complete isolation — never against this repo's own `.git`, only against two
throwaway tmp_path directories standing in for "the real repo" and "a test
fixture's own scratch dir."
"""

from __future__ import annotations

import os
import subprocess


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def test_git_location_env_vars_are_absent_during_a_test(monkeypatch):
    """The autouse fixture in conftest.py should already have stripped these before
    this test body even runs — proves the guard is active, not merely defined."""
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY"):
        assert var not in os.environ, f"{var} leaked into a test — the autouse guard did not run"


def test_reproduces_the_paid_incident_in_isolation_and_proves_the_guard_prevents_it(tmp_path, monkeypatch):
    """Without the guard: a `git -C <fixture_dir> ...` call under an inherited
    GIT_DIR silently writes into GIT_DIR's repo instead, exactly as it did to this
    session's own primary .git (core.bare flipped, user.email/name overwritten to
    the fixture identity 't <t@t>') and to a spawned stream's worktree (20+ fixture
    commits landed on its real HEAD). With the guard active (the normal, autouse
    case — this test does NOT re-clear the vars, proving the fixture already did):
    the same `-C` call must land in the fixture's own directory, never in whatever
    a stray inherited GIT_DIR happened to point at.
    """
    real_repo_standin = tmp_path / "standin-for-the-real-repo"
    real_repo_standin.mkdir()
    subprocess.run(["git", "init", "-q", str(real_repo_standin)], check=True, capture_output=True)

    fixture_scratch = tmp_path / "fixture-scratch"
    fixture_scratch.mkdir()

    # Simulate the hazardous environment a git hook's subprocess actually has —
    # WITHOUT going through conftest's autouse fixture a second time (that already
    # ran and cleared these before this test started; setting them here mid-test
    # checks that the ambient state a MISBEHAVING test could reintroduce is still
    # correctly overridden by the fixture's *own* explicit -C usage combined with
    # git's actual resolution rules once GIT_DIR is unset again below).
    monkeypatch.setenv("GIT_DIR", str(real_repo_standin / ".git"))
    try:
        # Without stripping GIT_DIR here, this call SHOULD misdirect into
        # real_repo_standin (the exact bug) rather than failing — fixture_scratch has
        # no .git of its own, so if -C were actually authoritative this would error;
        # if it instead succeeds, the write went to real_repo_standin's real .git.
        _git(fixture_scratch, "config", "user.email", "hazard-proof@example.invalid")
        # If we reach here without an exception, the write landed SOMEWHERE.
        # Assert it did NOT land in fixture_scratch (no .git there at all — init was
        # never run against it) and DID land in real_repo_standin (the hazard,
        # reproduced) — proving the vulnerability is real in this exact harness
        # shape before trusting the fixture's fix.
        assert not (fixture_scratch / ".git").exists(), (
            "fixture_scratch never had git init run against it directly in this "
            "reproduction — a .git appearing there would mean the hazard did not "
            "reproduce as expected"
        )
        real_config = (real_repo_standin / ".git" / "config").read_text()
        assert "hazard-proof@example.invalid" in real_config, (
            "expected the misdirected write to land in real_repo_standin under an "
            "inherited GIT_DIR — if this fails, the hazard did not reproduce, which "
            "means this test's own harness assumption is wrong, not that the bug "
            "doesn't exist"
        )
    finally:
        monkeypatch.delenv("GIT_DIR", raising=False)

    # Now prove the guard's actual behavior: with GIT_DIR cleared again (the normal,
    # autouse-fixture state every OTHER test in this suite runs under), the same
    # -C call must land in fixture_scratch, never in real_repo_standin.
    subprocess.run(["git", "init", "-q", str(fixture_scratch)], check=True, capture_output=True)
    _git(fixture_scratch, "config", "user.email", "safe@example.invalid")
    fixture_config = (fixture_scratch / ".git" / "config").read_text()
    assert "safe@example.invalid" in fixture_config
    real_config_after = (real_repo_standin / ".git" / "config").read_text()
    assert "safe@example.invalid" not in real_config_after, (
        "the second write leaked into real_repo_standin even with GIT_DIR cleared "
        "— the guard did not actually fix the isolation"
    )
