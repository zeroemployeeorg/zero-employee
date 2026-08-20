"""branch-gates (RULING-324, CHARTER-branch-gates): the five-state branch
classifier, the corpus trunk-only pre-commit refusal, and check-base-fresh.

Every case here constructs a REAL git repo (tmp_path git init + real commits,
real branches, real remotes where needed) and runs the REAL functions against
it -- never a mock of git's own output. This mirrors test_trunk_guard_hook.py's
own discipline (a real fixture repo, a real subprocess) for the same reason:
these are behavioral claims about what git state produces what classification,
and only running real git against a real repo proves that.
"""

from __future__ import annotations

import subprocess
import time

from zero_employee.core import (
    classify_branch,
    classify_all_branches,
    list_branches,
    check_base_fresh,
    LIVE_BEHIND_THRESHOLD,
    ORPHANED_AGE_DAYS,
)
from zero_employee.hooks import check_trunk_only, run_pre_commit
from zero_employee import cli


def _git(repo, *args, check=True):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _bare_remote(tmp_path, name="remote.git"):
    remote = tmp_path / name
    _git(tmp_path, "init", "--bare", "-b", "main", str(remote))
    return remote


def _repo_with_remote(tmp_path):
    """A local repo, `origin` pointed at a bare remote, one commit on main, pushed."""
    remote = _bare_remote(tmp_path)
    repo = tmp_path / "work"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "remote", "add", "origin", str(remote))
    (repo / "f.txt").write_text("root\n", encoding="utf-8")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-q", "-m", "root commit")
    _git(repo, "push", "-q", "origin", "main")
    return repo


def _advance_main(repo, n):
    for i in range(n):
        (repo / "f.txt").write_text(f"main-{i}\n", encoding="utf-8")
        _git(repo, "commit", "-q", "-am", f"main commit {i}")
    _git(repo, "push", "-q", "origin", "main")


def _branch_off(repo, name, back, content):
    _git(repo, "checkout", "-q", "-b", name, f"main~{back}" if back else "main")
    (repo / "f.txt").write_text(content, encoding="utf-8")
    _git(repo, "commit", "-q", "-am", f"{name} commit")
    _git(repo, "push", "-q", "origin", name)
    _git(repo, "checkout", "-q", "main")


def _backdated_commit(repo, name, back, content, days_ago):
    _git(repo, "checkout", "-q", "-b", name, f"main~{back}" if back else "main")
    (repo / "f.txt").write_text(content, encoding="utf-8")
    env_date = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - days_ago * 86400))
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-am", f"{name} commit"],
        env={
            **__import__("os").environ,
            "GIT_AUTHOR_DATE": env_date,
            "GIT_COMMITTER_DATE": env_date,
        },
        check=True,
        capture_output=True,
        text=True,
    )
    _git(repo, "push", "-q", "origin", name)
    _git(repo, "checkout", "-q", "main")


# ══════════════════════════════════════════════════════════════════════════
# The five-state classifier — one full adversarial fixture, all five states
# constructed deliberately, matching the charter's own DoD language ("inject
# each state, confirm each is named, restore").
# ══════════════════════════════════════════════════════════════════════════


def test_classify_all_five_states_in_one_fixture(tmp_path):
    repo = _repo_with_remote(tmp_path)
    _advance_main(repo, 25)  # main now has real distance to drift bases against

    # MERGED: fully absorbed, ahead == 0
    _git(repo, "branch", "merged-example", "main")
    _git(repo, "push", "-q", "origin", "merged-example")

    # RESCUE: naming convention wins regardless of git state
    _branch_off(repo, "rescue/test-fixture", 5, "rescue-content\n")

    # LIVE: fresh base (behind <= LIVE_BEHIND_THRESHOLD), real content
    _branch_off(repo, "live-example", 2, "live-content\n")

    # STALE-BASE: drifted base (behind > threshold), but RECENT last commit
    _branch_off(repo, "stale-base-example", 24, "stale-content\n")

    # ORPHANED: drifted base (behind > threshold) AND last commit older than
    # ORPHANED_AGE_DAYS -- the age signal that distinguishes it from STALE-BASE.
    _backdated_commit(repo, "orphaned-example", 24, "orphaned-content\n", days_ago=ORPHANED_AGE_DAYS + 15)

    rows = {r["branch"]: r for r in classify_all_branches(repo, trunk="main")}

    assert rows["merged-example"]["state"] == "MERGED"
    assert rows["merged-example"]["ahead"] == 0

    assert rows["rescue/test-fixture"]["state"] == "RESCUE"

    assert rows["live-example"]["state"] == "LIVE"
    assert rows["live-example"]["behind"] <= LIVE_BEHIND_THRESHOLD

    assert rows["stale-base-example"]["state"] == "STALE-BASE"
    assert rows["stale-base-example"]["behind"] > LIVE_BEHIND_THRESHOLD

    assert rows["orphaned-example"]["state"] == "ORPHANED"
    assert rows["orphaned-example"]["behind"] > LIVE_BEHIND_THRESHOLD

    # every branch got a DIFFERENT state -- proves the fixture actually
    # exercised all five buckets, not five branches collapsing into one.
    assert len({r["state"] for r in rows.values()}) == 5


def test_merged_precedence_ahead_zero(tmp_path):
    repo = _repo_with_remote(tmp_path)
    _advance_main(repo, 5)
    _git(repo, "branch", "fully-merged", "main")
    row = classify_branch(repo, "fully-merged", trunk="main")
    assert row["state"] == "MERGED"
    assert row["ahead"] == 0
    assert row["merged"] is True


def test_rescue_wins_even_when_also_ahead_zero(tmp_path):
    """RULING-324 §1: naming beats git state. A rescue/* branch identical to trunk
    (ahead==0, which would otherwise read MERGED) must still report RESCUE."""
    repo = _repo_with_remote(tmp_path)
    _advance_main(repo, 5)
    _git(repo, "branch", "rescue/identical-to-trunk", "main")
    row = classify_branch(repo, "rescue/identical-to-trunk", trunk="main")
    assert row["state"] == "RESCUE"


def test_stale_base_precedes_orphaned_on_recent_activity(tmp_path):
    """RULING-324 §2's own worked tie: real unmerged commits + recent activity ->
    STALE-BASE, not ORPHANED, even though the branch is also stale-by-commit-count."""
    repo = _repo_with_remote(tmp_path)
    _advance_main(repo, 25)
    _branch_off(repo, "active-but-stale", 24, "content\n")
    row = classify_branch(repo, "active-but-stale", trunk="main")
    assert row["state"] == "STALE-BASE"
    assert row["behind"] > LIVE_BEHIND_THRESHOLD


def test_unknown_when_no_trunk_ref(tmp_path):
    """No origin/<trunk> reachable -> UNKNOWN, never a guessed state (fail-closed
    on the classification, matching git_ref_state's own contained_in_trunk shape)."""
    repo = tmp_path / "no-remote"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-q", "-m", "root")
    _git(repo, "branch", "some-branch")
    row = classify_branch(repo, "some-branch", trunk="main")
    assert row["state"] == "UNKNOWN"
    assert row["ahead"] is None


def test_list_branches_excludes_trunk_and_origin_head_symbolic_ref(tmp_path):
    """MEASURED regression (branch-gates SOW-3 smoke test against a real repo):
    refs/remotes/origin/HEAD is a symbolic ref whose %(refname:short) prints as
    the bare 'origin', not 'origin/HEAD' -- an early implementation filtered on
    the short-form string and let a fake branch named 'origin' through, reported
    ahead=0/behind=0/MERGED. This must never reappear."""
    repo = _repo_with_remote(tmp_path)
    _advance_main(repo, 3)
    _git(repo, "branch", "second-branch", "main")
    _git(repo, "push", "-q", "origin", "second-branch")
    names = {b["name"] for b in list_branches(repo, trunk="main")}
    assert "origin" not in names
    assert "main" not in names
    assert "origin/main" not in names
    assert any(n.endswith("second-branch") for n in names)


def test_classify_all_branches_sorted_and_report_only(tmp_path):
    """The verb never mutates -- classify_all_branches is a pure read; assert no
    ref changed shape by re-listing branches before/after."""
    repo = _repo_with_remote(tmp_path)
    _advance_main(repo, 3)
    _git(repo, "branch", "z-branch", "main")
    _git(repo, "branch", "a-branch", "main")
    before = _git(repo, "for-each-ref", "--format=%(refname)", "refs/heads/").stdout
    rows = classify_all_branches(repo, trunk="main")
    after = _git(repo, "for-each-ref", "--format=%(refname)", "refs/heads/").stdout
    assert before == after  # untouched
    names = [r["branch"] for r in rows]
    assert names == sorted(names)


# ══════════════════════════════════════════════════════════════════════════
# CLI wiring: `zeo branches`
# ══════════════════════════════════════════════════════════════════════════


def test_cli_branches_dispatch(tmp_path, capsys):
    repo = _repo_with_remote(tmp_path)
    _advance_main(repo, 3)
    _git(repo, "branch", "cli-test-branch", "main")
    rc = cli.main(["branches", str(repo)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "cli-test-branch" in out
    assert "MERGED" in out


def test_cli_branches_json(tmp_path, capsys):
    repo = _repo_with_remote(tmp_path)
    _advance_main(repo, 3)
    _git(repo, "branch", "cli-test-branch", "main")
    rc = cli.main(["branches", str(repo), "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    import json

    data = json.loads(out)
    assert data["branches"]
    assert any(b["branch"] == "cli-test-branch" for b in data["branches"])


# ══════════════════════════════════════════════════════════════════════════
# check-base-fresh
# ══════════════════════════════════════════════════════════════════════════


def test_check_base_fresh_true_on_trunk(tmp_path):
    repo = _repo_with_remote(tmp_path)
    _advance_main(repo, 3)
    result = check_base_fresh(repo, trunk="main")
    assert result["fresh"] is True


def test_check_base_fresh_false_on_stale_branch(tmp_path):
    repo = _repo_with_remote(tmp_path)
    _advance_main(repo, 5)
    _git(repo, "checkout", "-q", "-b", "behind-branch", "main~5")
    result = check_base_fresh(repo, trunk="main")
    assert result["fresh"] is False
    assert result["behind"] == 5


def test_check_base_fresh_true_after_rebase(tmp_path):
    """The DoD's own required proof: fails stale, passes after a rebase."""
    repo = _repo_with_remote(tmp_path)
    _advance_main(repo, 5)
    _git(repo, "checkout", "-q", "-b", "behind-branch", "main~5")
    assert check_base_fresh(repo, trunk="main")["fresh"] is False
    _git(repo, "rebase", "origin/main")
    assert check_base_fresh(repo, trunk="main")["fresh"] is True


def test_check_base_fresh_unknown_without_origin(tmp_path):
    repo = tmp_path / "no-remote"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-q", "-m", "root")
    result = check_base_fresh(repo, trunk="main")
    assert result["fresh"] is None


def test_cli_check_base_fresh_exit_codes(tmp_path):
    repo = _repo_with_remote(tmp_path)
    _advance_main(repo, 5)
    assert cli.main(["check-base-fresh", str(repo)]) == 0
    _git(repo, "checkout", "-q", "-b", "behind-branch", "main~5")
    assert cli.main(["check-base-fresh", str(repo)]) == 1
    _git(repo, "rebase", "origin/main")
    assert cli.main(["check-base-fresh", str(repo)]) == 0


# ══════════════════════════════════════════════════════════════════════════
# Trunk-only corpus pre-commit refusal
# ══════════════════════════════════════════════════════════════════════════


def _corpus(tmp_path):
    root = tmp_path / "org"
    (root / "claude-md").mkdir(parents=True)
    (root / "claude-md" / "CLAUDE.md").write_text("# CLAUDE\n", encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "test")
    _git(root, "add", "claude-md")
    _git(root, "commit", "-q", "-m", "init")
    return root


def test_check_trunk_only_none_on_trunk(tmp_path):
    root = _corpus(tmp_path)
    assert check_trunk_only(root, trunk="main") is None


def test_check_trunk_only_refuses_non_trunk(tmp_path):
    root = _corpus(tmp_path)
    _git(root, "checkout", "-q", "-b", "feat/some-work")
    reason = check_trunk_only(root, trunk="main")
    assert reason is not None
    assert "feat/some-work" in reason
    assert "main" in reason


def test_check_trunk_only_none_on_detached_head(tmp_path):
    """Fail-open on undeterminable branch state -- a detached HEAD has no branch
    to be 'non-trunk' on, so this check must not fire (doctrine: fail-closed on
    the REFUSAL, fail-open on the UNKNOWN)."""
    root = _corpus(tmp_path)
    sha = _git(root, "rev-parse", "HEAD").stdout.strip()
    _git(root, "checkout", "-q", sha)
    assert check_trunk_only(root, trunk="main") is None


def test_run_pre_commit_refuses_on_non_trunk_branch(tmp_path):
    """The real gate: run_pre_commit (what `zeo hooks pre-commit` actually calls)
    refuses on a non-trunk branch before it does anything else."""
    root = _corpus(tmp_path)
    _git(root, "checkout", "-q", "-b", "feat/some-work")
    (root / "test.md").write_text("content\n", encoding="utf-8")
    _git(root, "add", "test.md")
    rc = run_pre_commit(root)
    assert rc == 1


def test_run_pre_commit_permits_on_trunk(tmp_path):
    root = _corpus(tmp_path)
    (root / "test.md").write_text("content\n", encoding="utf-8")
    _git(root, "add", "test.md")
    rc = run_pre_commit(root)
    assert rc == 0


def test_run_pre_commit_end_to_end_real_commit_refused_then_permitted(tmp_path):
    """DoD-shaped proof at the git-commit layer, not just the function layer:
    a REAL `git commit` on a non-trunk branch is refused (the hook exits non-zero
    and git aborts the commit -- no new commit object is created), and the SAME
    content on trunk lands."""
    root = _corpus(tmp_path)
    hooks_dir = root / ".git" / "hooks"
    hook_path = hooks_dir / "pre-commit"
    hook_path.write_text(
        "#!/usr/bin/env bash\nset -uo pipefail\n"
        f'exec "{__import__("sys").executable}" -c '
        '"from zero_employee.hooks import run_pre_commit; '
        "import sys; sys.exit(run_pre_commit('" + str(root) + "'))\"\n",
        encoding="utf-8",
    )
    hook_path.chmod(0o755)

    before_count = int(_git(root, "rev-list", "--count", "HEAD").stdout.strip())

    _git(root, "checkout", "-q", "-b", "feat/non-trunk-attempt")
    (root / "off-trunk.md").write_text("should not land\n", encoding="utf-8")
    _git(root, "add", "off-trunk.md")
    result = subprocess.run(
        ["git", "-C", str(root), "commit", "-m", "non-trunk attempt"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "COMMIT BLOCKED" in result.stdout or "COMMIT BLOCKED" in result.stderr
    after_refused_count = int(_git(root, "rev-list", "--count", "HEAD").stdout.strip())
    assert after_refused_count == before_count  # no commit landed

    _git(root, "checkout", "-q", "main")
    (root / "on-trunk.md").write_text("should land\n", encoding="utf-8")
    _git(root, "add", "on-trunk.md")
    result2 = subprocess.run(
        ["git", "-C", str(root), "commit", "-m", "trunk attempt"],
        capture_output=True,
        text=True,
    )
    assert result2.returncode == 0
    after_permitted_count = int(_git(root, "rev-list", "--count", "HEAD").stdout.strip())
    assert after_permitted_count == before_count + 1
