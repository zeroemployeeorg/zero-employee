"""Behavioral probes for the shipped trunk-guard hook template (REPO-EQUIP-SOW-1
s5 / SOW-4).

src/zero_employee/scaffold_templates/claude-hooks/check-trunk-guard.sh is
sourced, byte-for-byte in every executable line, from the real, already
17-probe-validated `zeroemployeeorg/ducktyper` `.claude/hooks/check-trunk-guard.sh`
at commit `ad62f582` (only comments and one user-facing deny-reason string were
reworded to remove repo-specific references, since this ships as a generic
template to arbitrary PyPI users -- see the SOW filing for the full diff).

The charter's own words (SOW-1 s5, closing paragraph): "every claim above is
behavioural, and the SOW must prove them by probe, not by reading the file."
This module reproduces that discipline against the SHIPPED TEMPLATE COPY
specifically (not the ducktyper original) -- the generalization pass is exactly
the kind of edit that could silently break a regex or a code path, and reading
the diff is not proof that it didn't.

Every probe below runs the real script, as a real subprocess, with `jq` doing
the real JSON parsing the hook depends on, against a REAL git fixture repo (a
tmp_path git init with actual commits and branches) -- never a mock of the
script's own logic. A probe passes if the hook's PreToolUse decision (allow =
exit 0, no stdout; deny = exit 0 with a `permissionDecision: deny` JSON
payload on stdout, matching Claude Code's own PreToolUse hook contract) has
the shape the case demands.

Case categories, matching SOW-1 s5's own 17-probe backlog:
  ALLOW: merge-to-trunk, push-to-trunk, tag push, own-branch push, own-branch
         rebase, checkout+rebase, switch+rebase, -b+rebase, merge --abort,
         rebase --continue, other-repo command (no standing to deny)
  DENY:  force-push (-f and --force), push --delete, push :branch (colon
         deletion spelling), rebase-on-trunk, checkout main && rebase (i.e.
         explicitly re-landing on trunk before rebasing)
"""

from __future__ import annotations

import json
import pathlib
import subprocess

import pytest

_HOOK_REL = pathlib.Path("src/zero_employee/scaffold_templates/claude-hooks/check-trunk-guard.sh")
_HOOK_PATH = pathlib.Path(__file__).resolve().parents[1] / _HOOK_REL


def _git(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture()
def own_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A real git repo with the hook deployed at .claude/hooks/, on trunk (main),
    with one commit and one feature branch already cut from it."""
    repo = tmp_path / "own-repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")

    hooks_dir = repo / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)
    dest = hooks_dir / "check-trunk-guard.sh"
    dest.write_text(_HOOK_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    dest.chmod(dest.stat().st_mode | 0o111)

    _git(repo, "branch", "feat/mine")
    return repo


@pytest.fixture()
def other_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A second, unrelated git repo -- the hook has no standing here."""
    repo = tmp_path / "other-repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    return repo


def _run_hook(repo: pathlib.Path, command: str) -> tuple[int, dict | None]:
    """Invoke the hook exactly as Claude Code's PreToolUse wiring would: JSON on
    stdin, `bash .claude/hooks/check-trunk-guard.sh` run with cwd=repo (the
    session's own working directory, standing in for the live session cwd)."""
    payload = json.dumps({"tool_input": {"command": command}})
    result = subprocess.run(
        ["bash", ".claude/hooks/check-trunk-guard.sh"],
        cwd=str(repo),
        input=payload,
        capture_output=True,
        text=True,
        env=_hook_env(),
    )
    stdout = result.stdout.strip()
    if not stdout:
        return result.returncode, None
    return result.returncode, json.loads(stdout)


def _hook_env() -> dict[str, str]:
    """Minimal env for the hook subprocess: PATH (for git/jq/bash) and HOME
    (the script's own `${dir/#\\~/$HOME}` tilde-expansion reads it under
    `set -u`, so an absent HOME is an unbound-variable crash - a test-harness
    artifact, not a hook behavior worth asserting on)."""
    import os

    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"),
        "HOME": os.environ.get("HOME", ""),
    }


def _is_deny(decision: dict | None) -> bool:
    if not decision:
        return False
    return decision.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def _deny_reason(decision: dict | None) -> str:
    assert decision is not None
    return decision["hookSpecificOutput"]["permissionDecisionReason"]


# ══════════════════════════════════════════════════════════════════════════
# ALLOW cases
# ══════════════════════════════════════════════════════════════════════════


def test_allow_merge_to_trunk(own_repo):
    """Merging a certified branch INTO trunk is the landing act - allowed."""
    rc, decision = _run_hook(own_repo, "git merge feat/mine")
    assert rc == 0
    assert not _is_deny(decision)


def test_allow_push_to_trunk(own_repo):
    """Plain push while on trunk is allowed - gated by the repo's own pre-push, not this hook."""
    rc, decision = _run_hook(own_repo, "git push origin main")
    assert rc == 0
    assert not _is_deny(decision)


def test_allow_tag_push(own_repo):
    """Pushing a tag is not a branch push at all - never denied."""
    rc, decision = _run_hook(own_repo, "git push origin v1.0.0")
    assert rc == 0
    assert not _is_deny(decision)


def test_allow_own_branch_push(own_repo):
    rc, decision = _run_hook(own_repo, "git checkout feat/mine && git push origin feat/mine")
    assert rc == 0
    assert not _is_deny(decision)


def test_allow_own_branch_rebase(own_repo):
    """Rebase while already on a non-trunk branch is unrestricted."""
    _git(own_repo, "checkout", "feat/mine")
    rc, decision = _run_hook(own_repo, "git rebase main")
    assert rc == 0
    assert not _is_deny(decision)


def test_allow_checkout_then_rebase(own_repo):
    """The standard own-branch update: checkout off trunk, then rebase, in one command."""
    rc, decision = _run_hook(own_repo, "git checkout feat/mine && git rebase origin/main")
    assert rc == 0
    assert not _is_deny(decision)


def test_allow_switch_then_rebase(own_repo):
    """Same as checkout+rebase but with `git switch`."""
    rc, decision = _run_hook(own_repo, "git switch feat/mine && git rebase origin/main")
    assert rc == 0
    assert not _is_deny(decision)


def test_allow_checkout_dash_b_then_rebase(own_repo):
    """`checkout -b <new-branch>` earlier in the command also counts as leaving trunk."""
    rc, decision = _run_hook(own_repo, "git checkout -b feat/newone && git rebase origin/main")
    assert rc == 0
    assert not _is_deny(decision)


def test_allow_merge_abort(own_repo):
    """--abort never lands new history - exempt unconditionally, even on trunk."""
    rc, decision = _run_hook(own_repo, "git merge --abort")
    assert rc == 0
    assert not _is_deny(decision)


def test_allow_rebase_continue(own_repo):
    """--continue resolves a stuck rebase - exempt unconditionally, even on trunk."""
    rc, decision = _run_hook(own_repo, "git rebase --continue")
    assert rc == 0
    assert not _is_deny(decision)


def test_allow_rebase_skip_and_quit(own_repo):
    for flag in ("--skip", "--quit"):
        rc, decision = _run_hook(own_repo, f"git rebase {flag}")
        assert rc == 0
        assert not _is_deny(decision), f"--{flag} should be exempt"


def test_allow_command_in_other_repo(own_repo, other_repo):
    """A command whose target is a DIFFERENT repo - this hook has no standing to deny it,
    even though the command text (force-push on trunk) would be denied in own_repo."""
    rc, decision = _run_hook(own_repo, f"git -C {other_repo} push --force origin main")
    assert rc == 0
    assert not _is_deny(decision)


# ══════════════════════════════════════════════════════════════════════════
# DENY cases
# ══════════════════════════════════════════════════════════════════════════


def test_deny_force_push_dash_f(own_repo):
    rc, decision = _run_hook(own_repo, "git push -f origin main")
    assert rc == 0
    assert _is_deny(decision)
    assert "force" in _deny_reason(decision).lower()


def test_deny_force_push_long_flag(own_repo):
    rc, decision = _run_hook(own_repo, "git push --force origin main")
    assert rc == 0
    assert _is_deny(decision)
    assert "force" in _deny_reason(decision).lower()


def test_deny_push_delete_flag(own_repo):
    rc, decision = _run_hook(own_repo, "git push origin --delete feat/mine")
    assert rc == 0
    assert _is_deny(decision)
    assert "delet" in _deny_reason(decision).lower()


def test_deny_push_colon_refspec_deletion(own_repo):
    """The second deletion spelling: `git push origin :branch`."""
    rc, decision = _run_hook(own_repo, "git push origin :feat/mine")
    assert rc == 0
    assert _is_deny(decision)
    assert "delet" in _deny_reason(decision).lower()


def test_deny_rebase_on_trunk(own_repo):
    """Rebase while checked out on trunk itself - denied, unlike merge."""
    rc, decision = _run_hook(own_repo, "git rebase origin/main")
    assert rc == 0
    assert _is_deny(decision)
    assert "rebase" in _deny_reason(decision).lower()


def test_deny_checkout_main_then_rebase(own_repo):
    """A redundant `checkout main` before rebasing while ALREADY on trunk is still a
    trunk rebase - denied. The hook's own co_target logic only OVERRIDES the live
    current-branch reading when the checkout target is non-trunk (i.e. "leaving
    trunk"); a checkout that names trunk itself is not treated as an override, so
    this falls through to the real on-disk HEAD, which here is still trunk. own_repo
    starts checked out on main (its default state), matching that precondition -
    distinguishes from checkout-OFF-trunk (test_allow_checkout_then_rebase above),
    which IS an override and is allowed."""
    assert _git(own_repo, "branch", "--show-current").stdout.strip() == "main"
    rc, decision = _run_hook(own_repo, "git checkout main && git rebase origin/feat/mine")
    assert rc == 0
    assert _is_deny(decision)


def test_deny_merge_on_trunk_is_actually_allowed_not_a_deny_case(own_repo):
    """Sanity cross-check: merge-on-trunk must NOT be caught by the same deny path as
    rebase-on-trunk - the asymmetry (s5 item 4) is the point, not an oversight."""
    rc, decision = _run_hook(own_repo, "git merge feat/mine")
    assert rc == 0
    assert not _is_deny(decision)


# ══════════════════════════════════════════════════════════════════════════
# Repo-identity resolution (s5 item 3): the guard must resolve ITS OWN repo
# from the script's location, not the session's launch cwd.
# ══════════════════════════════════════════════════════════════════════════


def test_repo_identity_resolved_from_script_location_not_cwd(own_repo, other_repo, tmp_path):
    """Run the hook with cwd = other_repo (simulating a session that `cd`'d into an
    unrelated repo) but invoke it BY PATH into own_repo's .claude/hooks/ - the
    force-push-on-trunk command has no -C/cd redirect, so it targets whatever the
    process cwd is (other_repo), which the hook has no standing over -> allow.
    This is the direct behavioral proof of s5 item 3's incident: a session-cwd-scoped
    guard would have used SCRIPT's invocation location and wrongly fired here."""
    hook_path = own_repo / ".claude" / "hooks" / "check-trunk-guard.sh"
    payload = json.dumps({"tool_input": {"command": "git push --force origin main"}})
    result = subprocess.run(
        ["bash", str(hook_path)],
        cwd=str(other_repo),
        input=payload,
        capture_output=True,
        text=True,
        env=_hook_env(),
    )
    stdout = result.stdout.strip()
    decision = json.loads(stdout) if stdout else None
    assert not _is_deny(decision), (
        "hook fired on a force-push whose target (session cwd) is a different repo "
        "than the one it's deployed to - this is exactly the s5 item 3 incident shape"
    )


# ══════════════════════════════════════════════════════════════════════════
# git stash denial (s5 item 7/8): handled by the SEPARATE stash-deny hook
# wired in claude-settings.json (not check-trunk-guard.sh itself), but the
# settings.json template's own text is proven here since it's the artifact
# s5 describes.
# ══════════════════════════════════════════════════════════════════════════


def test_settings_json_stash_hook_denies_git_stash():
    """The stash-deny hook is a jq/grep one-liner embedded directly in
    claude-settings.json's PreToolUse wiring, not a separate script file. Extract
    and run it exactly as PreToolUse would to prove it actually denies `git stash`
    and points at `git worktree add` as the alternative."""
    settings_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "src"
        / "zero_employee"
        / "scaffold_templates"
        / "claude-settings.json"
    )
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    stash_hook_cmd = data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]

    payload = json.dumps({"tool_input": {"command": "git stash"}})
    result = subprocess.run(
        ["bash", "-c", stash_hook_cmd],
        input=payload,
        capture_output=True,
        text=True,
        env=_hook_env(),
    )
    stdout = result.stdout.strip()
    assert stdout, "stash hook produced no output for `git stash` - expected a deny payload"
    decision = json.loads(stdout)
    assert _is_deny(decision)
    assert "worktree" in _deny_reason(decision).lower()


def test_settings_json_stash_hook_silent_on_non_stash_commands():
    settings_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "src"
        / "zero_employee"
        / "scaffold_templates"
        / "claude-settings.json"
    )
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    stash_hook_cmd = data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]

    payload = json.dumps({"tool_input": {"command": "git status"}})
    result = subprocess.run(
        ["bash", "-c", stash_hook_cmd],
        input=payload,
        capture_output=True,
        text=True,
        env=_hook_env(),
    )
    assert result.stdout.strip() == ""


def test_settings_json_has_no_stale_allow_entry_for_git_stash():
    """s5 item 8: no `Bash(git stash:*)` in `allow` when the stash hook is present -
    a stale allow entry would be a lie that misleads the next reader even though the
    hook wins on precedence either way."""
    settings_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "src"
        / "zero_employee"
        / "scaffold_templates"
        / "claude-settings.json"
    )
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    allow = data.get("permissions", {}).get("allow", [])
    assert not any("stash" in entry for entry in allow)
