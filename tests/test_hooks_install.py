"""zeo hooks install — thin stubs + gitignore boards + Python runners."""

from __future__ import annotations

import json
import subprocess

from zero_employee import cli
from zero_employee.hooks import (
    ensure_board_gitignore,
    hooks_install,
    run_pre_commit,
    run_pretooluse_git,
    run_session_start,
    run_stop,
)
from zero_employee.cost import parse_transcript_usage, append_session_cost_log, session_cost_report
from zero_employee.scaffold import init_corpus


def _corpus(tmp_path):
    root = tmp_path / "org"
    (root / "claude-md").mkdir(parents=True)
    (root / "claude-md" / "CLAUDE.md").write_text("# CLAUDE\n", encoding="utf-8")
    # branch-gates (RULING-324): every real corpus repo in this org uses `main` as
    # trunk (org, zero-employee, ducktyper all confirmed) and the pre-commit gate's
    # trunk-only refusal (hooks.check_trunk_only) checks against it by default.
    # `-b main` here matches that real convention -- an unqualified `git init` picks
    # up whatever `init.defaultBranch` the RUNNING MACHINE happens to have configured
    # (this test runner's default is `master`), which is not representative of any
    # real corpus and would spuriously trip the trunk-only refusal on every fixture
    # commit below.
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "test"],
        check=True,
        capture_output=True,
    )
    return root


def test_hooks_install_writes_thin_stubs_and_git_hook(tmp_path):
    root = _corpus(tmp_path)
    info = hooks_install(root)
    pre = (root / "tools" / "hooks" / "pre-commit").read_text(encoding="utf-8")
    stop = (root / "tools" / "hooks" / "cc-stop.sh").read_text(encoding="utf-8")
    assert "hooks pre-commit" in pre
    assert "--commit-check" not in pre
    assert "hooks stop" in stop
    assert "RATE_TABLE" not in stop
    assert info["git_hook"]
    assert (root / ".git" / "hooks" / "pre-commit").is_file()
    git_pre = (root / ".git" / "hooks" / "pre-commit").read_text(encoding="utf-8")
    assert "hooks pre-commit" in git_pre


def test_hooks_install_writes_board_gitignore(tmp_path):
    root = _corpus(tmp_path)
    info = hooks_install(root)
    assert info["gitignore_updated"] is True
    gi = (root / ".gitignore").read_text(encoding="utf-8")
    assert "STATE.md" in gi
    assert "stream-index.md" in gi
    # idempotent
    assert ensure_board_gitignore(root) is False
    info2 = hooks_install(root)
    assert info2["gitignore_updated"] is False


def test_init_corpus_writes_board_gitignore(tmp_path):
    root = tmp_path / "org"
    info = init_corpus(root)
    assert ".gitignore" in info["created"]
    gi = (root / ".gitignore").read_text(encoding="utf-8")
    assert "STATE.md" in gi and "stream-index.md" in gi


def test_cli_hooks_install(tmp_path, capsys):
    root = _corpus(tmp_path)
    rc = cli.main(["hooks", "install", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "HOOKS-INSTALL" in out
    assert "gitignore" in out.lower() or ".gitignore" in out
    assert (root / "tools" / "hooks" / "cc-session-start.sh").is_file()


def test_pre_commit_unstages_state_md_and_passes_empty(tmp_path):
    root = _corpus(tmp_path)
    # commit corpus marker so git has a HEAD for resets
    subprocess.run(["git", "-C", str(root), "add", "claude-md"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )
    (root / "STATE.md").write_text("# board\n", encoding="utf-8")
    (root / "stream-index.md").write_text("# index\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(root), "add", "-f", "STATE.md", "stream-index.md"],
        check=True,
        capture_output=True,
    )
    staged = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "STATE.md" in staged

    rc = run_pre_commit(root)
    assert rc == 0
    staged_after = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "STATE.md" not in staged_after
    assert "stream-index.md" not in staged_after


def test_pre_commit_blocks_bad_staged_sow(tmp_path):
    root = _corpus(tmp_path)
    subprocess.run(["git", "-C", str(root), "add", "claude-md"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )
    sow_dir = root / "projects" / "demo" / "sow" / "demo-stream"
    sow_dir.mkdir(parents=True)
    bad = sow_dir / "01-demo.md"
    bad.write_text("---\ngenre: charter\nsow: demo-stream\nstatus: ACTIVE\n---\n\nbody\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", str(bad)], check=True, capture_output=True)

    rc = run_pre_commit(root)
    assert rc == 1


def test_pre_commit_catches_a_sow_n_collision_with_an_already_committed_sow(tmp_path):
    """Paid live in TWO corpora (profrodai/org's MOTION-ELEMENTS-SOW-1, zeroemployeeorg/
    org's quackverse-coverage-90 SOW-10) before this test existed: _commit_check_corpus
    was built to catch a cross-file collision the per-file --commit-check structurally
    cannot see (one staged file's files_fm has one entry, nothing to collide with) - but
    it only ever scanned ruling/ homes and only ever ran when a RULING file was staged.
    A staged SOW colliding with an ALREADY-COMMITTED SOW's n/rev was invisible to every
    commit, forever, regardless of what else was staged. This is the exact shape,
    reproduced end to end through the real git hook path, not just the linter function."""
    root = _corpus(tmp_path)
    # schema_rev:17 on the staged SOWs needs a canonical Rev to compare against, or the
    # per-file --commit-check fails closed on an unrelated schema-nocanon finding before
    # the collision check ever gets a chance to matter for this test's assertion.
    (root / "claude-md" / "CLAUDE.md").write_text(
        "# CLAUDE.md\n<!-- DOC-DATE: 2026-08-16 (Rev 17) -->\n", encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(root), "add", "claude-md"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "init"], check=True, capture_output=True)

    sow_dir = root / "projects" / "demo" / "sow" / "teststream"
    sow_dir.mkdir(parents=True)
    frontmatter = (
        "---\nsow: teststream\nproject: demo\nn: 1\nrev: a\nschema_rev: 17\n"
        "created: 2026-08-16\nupdated: 2026-08-16\nstatus: SHIPPED\n"
        "lifecycle: CLOSEOUT-RECORD\nissue_first: true\nledger: []\n---\n\nbody\n"
    )
    first = sow_dir / "TESTSTREAM-SOW-1-first.md"
    first.write_text(frontmatter, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", str(first)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "first"], check=True, capture_output=True)

    # A second SOW sharing the exact same (n, rev) - a real collision, no ruling file
    # anywhere in this commit, which is precisely the case the old ruling-gated trigger
    # would have missed entirely.
    second = sow_dir / "TESTSTREAM-SOW-1-second.md"
    second.write_text(frontmatter.replace("body", "body 2"), encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", str(second)], check=True, capture_output=True)

    rc = run_pre_commit(root)
    assert rc == 1, "an n-collision with an already-committed SOW must block the commit"


def test_pre_commit_allows_a_collision_reconciled_by_a_later_supersedes(tmp_path):
    """Paid live in zeroemployeeorg/org (quackverse-coverage-90 SOW-10/SOW-10, 2026-08-16):
    two SOWs independently minted the same (n, rev) - a real collision - and a prior
    Master reconciled it forward by minting the NEXT sow (n+1, `supersedes: <the
    colliding n>`) naming both filenames in its own prose, rather than editing either
    colliding file's own status. That is correct per this corpus's own append-only-SOW
    doctrine (a colliding file is never rewritten after the fact to silence the
    collision it was part of) - but the commit-check-corpus gate did not know a later
    file's `supersedes:` could resolve an EARLIER n-collision, and blocked every future
    unrelated commit to the whole corpus forever, with no doctrine-legal way through.
    Fixed: a live SOW whose own `supersedes:` names a colliding n reconciles it -
    WARN (visible), not ERROR (commit-blocking). Neither colliding file is touched."""
    root = _corpus(tmp_path)
    (root / "claude-md" / "CLAUDE.md").write_text(
        "# CLAUDE.md\n<!-- DOC-DATE: 2026-08-16 (Rev 17) -->\n", encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(root), "add", "claude-md"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "init"], check=True, capture_output=True)

    sow_dir = root / "projects" / "demo" / "sow" / "teststream"
    sow_dir.mkdir(parents=True)
    frontmatter = (
        "---\nsow: teststream\nproject: demo\nn: 10\nrev: 9\nschema_rev: 17\n"
        "created: 2026-08-16\nupdated: 2026-08-16\nstatus: RULING-REQUESTED\n"
        "lifecycle: ESCALATION\nissue_first: true\nledger: []\n---\n\nbody\n"
    )
    first = sow_dir / "TESTSTREAM-SOW-10-first.md"
    first.write_text(frontmatter, encoding="utf-8")
    second = sow_dir / "TESTSTREAM-SOW-10-second.md"
    second.write_text(frontmatter.replace("body", "body 2"), encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", str(first), str(second)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "both n:10"], check=True, capture_output=True)

    # The successor: n:11, supersedes:10, still RULING-REQUESTED originals untouched.
    successor_fm = (
        "---\nsow: teststream\nproject: demo\nn: 11\nrev: 10\nsupersedes: 10\n"
        "schema_rev: 17\ncreated: 2026-08-16\nupdated: 2026-08-16\nstatus: HANDOVER\n"
        "lifecycle: RESTING\nissue_first: true\nrequested_by: teststream#10\nledger: []\n---\n\n"
        "supersedes both TESTSTREAM-SOW-10-first.md and TESTSTREAM-SOW-10-second.md\n"
    )
    successor = sow_dir / "TESTSTREAM-SOW-11-reconciled.md"
    successor.write_text(successor_fm, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", str(successor)], check=True, capture_output=True)

    rc = run_pre_commit(root)
    assert rc == 0, "a collision already reconciled by a later supersedes: must not block"
    # and neither original file was touched to get there
    assert first.read_text(encoding="utf-8") == frontmatter
    assert second.read_text(encoding="utf-8") == frontmatter.replace("body", "body 2")


def test_pre_commit_allows_a_legitimate_rev_chain_no_collision(tmp_path):
    """The fix must not blind the gate the other way: two files sharing n but with
    DIFFERENT rev values are a legitimate rev-chain (doctrine B), not a collision, and
    must not be blocked."""
    root = _corpus(tmp_path)
    (root / "claude-md" / "CLAUDE.md").write_text(
        "# CLAUDE.md\n<!-- DOC-DATE: 2026-08-16 (Rev 17) -->\n", encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(root), "add", "claude-md"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "init"], check=True, capture_output=True)

    sow_dir = root / "projects" / "demo" / "sow" / "teststream"
    sow_dir.mkdir(parents=True)
    fm_a = (
        "---\nsow: teststream\nproject: demo\nn: 1\nrev: a\nschema_rev: 17\n"
        "created: 2026-08-16\nupdated: 2026-08-16\nstatus: SHIPPED\n"
        "lifecycle: CLOSEOUT-RECORD\nissue_first: true\nledger: []\n---\n\nrev a\n"
    )
    first = sow_dir / "TESTSTREAM-SOW-1-a.md"
    first.write_text(fm_a, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", str(first)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "rev a"], check=True, capture_output=True)

    fm_b = fm_a.replace("rev: a", "rev: b\nrequested_by: teststream#1").replace("rev a", "rev b")
    second = sow_dir / "TESTSTREAM-SOW-1-b.md"
    second.write_text(fm_b, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", str(second)], check=True, capture_output=True)

    rc = run_pre_commit(root)
    assert rc == 0, "distinct rev values on shared n are a rev-chain, not a collision"


def test_session_start_and_stop_smoke(tmp_path):
    root = _corpus(tmp_path)
    assert run_session_start(root) == 0
    assert run_stop(root, stdin_text="{}") == 0
    assert run_pretooluse_git(stdin_text='{"tool_input":{"command":"ls"}}') == 0


def test_cli_hooks_pre_commit_dispatch(tmp_path):
    root = _corpus(tmp_path)
    subprocess.run(["git", "-C", str(root), "add", "claude-md"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )
    rc = cli.main(["hooks", "pre-commit", str(root)])
    assert rc == 0


def test_transcript_dedupes_by_message_id(tmp_path):
    p = tmp_path / "t.jsonl"
    # same message id twice (streaming duplicate) must count once
    lines = [
        {
            "type": "assistant",
            "message": {
                "id": "msg_1",
                "model": "claude-haiku-4-5",
                "usage": {"input_tokens": 100, "output_tokens": 10},
            },
        },
        {
            "type": "assistant",
            "message": {
                "id": "msg_1",
                "model": "claude-haiku-4-5",
                "usage": {"input_tokens": 100, "output_tokens": 10},
            },
        },
        {
            "type": "assistant",
            "message": {
                "id": "msg_2",
                "model": "claude-haiku-4-5",
                "usage": {"input_tokens": 50, "output_tokens": 5},
            },
        },
    ]
    p.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    u = parse_transcript_usage(p)
    assert u["events"] == 2
    assert u["input_tokens"] == 150
    assert u["output_tokens"] == 15


def test_append_cost_log_and_cli(tmp_path, capsys):
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "message": {
                    "id": "m1",
                    "model": "claude-haiku-4-5",
                    "usage": {"input_tokens": 1000, "output_tokens": 100},
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    log = tmp_path / "session-costs.jsonl"
    report = session_cost_report(transcript=transcript, model="claude-haiku-4-5")
    append_session_cost_log(log, report)
    assert log.is_file()
    row = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert row["input_tokens"] == 1000
    assert row["usd"] > 0

    rc = cli.main(
        [
            "--session-cost",
            "--transcript",
            str(transcript),
            "--model",
            "claude-haiku-4-5",
            "--append-cost-log",
            str(log),
            "--json",
        ]
    )
    assert rc == 0
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2


def _governance_repo(tmp_path, monkeypatch):
    """A plain (non-corpus) work repo -- RULING-277's incident happened inside
    ordinary work repos (quackverse/ducktyper), not the org sows corpus, so
    this fixture deliberately does NOT build a claude-md/CLAUDE.md corpus
    marker the way `_corpus()` does."""
    root = tmp_path / "work-repo"
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "seat@example.com"], check=True, capture_output=True
    )
    subprocess.run(["git", "-C", str(root), "config", "user.name", "seat"], check=True, capture_output=True)
    (root / "README.md").write_text("# repo\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "init"], check=True, capture_output=True)
    monkeypatch.chdir(root)
    return root


def _stage(root, relpath, content="x\n"):
    p = root / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", relpath], check=True, capture_output=True)


def _payload(command, session_id="sess-1"):
    return json.dumps({"session_id": session_id, "tool_input": {"command": command}})


def test_pretooluse_git_allows_source_only_commit(tmp_path, monkeypatch, capsys):
    root = _governance_repo(tmp_path, monkeypatch)
    _stage(root, "src/foo.py", "print(1)\n")
    rc = run_pretooluse_git(stdin_text=_payload('git commit -m "add foo" -- src/foo.py'))
    assert rc == 0
    err = capsys.readouterr().err
    assert "WARN" not in err
    assert "ESCALATE" not in err


def test_pretooluse_git_allows_governance_path_with_sow_citation(tmp_path, monkeypatch, capsys):
    root = _governance_repo(tmp_path, monkeypatch)
    _stage(root, ".claude/settings.json", "{}\n")
    rc = run_pretooluse_git(
        stdin_text=_payload('git commit -m "fix(claude): settings per REPO-EQUIP-SOW-2" -- .claude/settings.json')
    )
    assert rc == 0
    err = capsys.readouterr().err
    assert "WARN" not in err
    assert "ESCALATE" not in err


def test_pretooluse_git_allows_governance_path_with_sow_path_citation(tmp_path, monkeypatch, capsys):
    root = _governance_repo(tmp_path, monkeypatch)
    _stage(root, "CLAUDE.md", "# doc\n")
    rc = run_pretooluse_git(
        stdin_text=_payload('git commit -m "docs: update CLAUDE.md, see sow/repo-equip/foo.md" -- CLAUDE.md')
    )
    assert rc == 0
    err = capsys.readouterr().err
    assert "WARN" not in err


def test_pretooluse_git_warns_on_uncited_settings_json_ruling_277_regression(tmp_path, monkeypatch, capsys):
    """Direct regression for RULING-277 s0: the real incident commit touched
    exactly .claude/settings.json, message 'chore(claude): standardize
    .claude/settings.json across the three seat repos', no SOW filed, landed
    straight to trunk in two verified repos. This reproduces that exact shape
    and must now WARN."""
    root = _governance_repo(tmp_path, monkeypatch)
    _stage(root, ".claude/settings.json", "{}\n")
    rc = run_pretooluse_git(
        stdin_text=_payload(
            'git commit -m "chore(claude): standardize .claude/settings.json across the three seat repos" '
            "-- .claude/settings.json"
        )
    )
    assert rc == 0  # WARN only, never blocks
    err = capsys.readouterr().err
    assert "WARN [RULING-277]" in err
    assert ".claude/settings.json" in err


def test_pretooluse_git_warns_on_uncited_claude_md(tmp_path, monkeypatch, capsys):
    root = _governance_repo(tmp_path, monkeypatch)
    _stage(root, "CLAUDE.md", "# doc change\n")
    rc = run_pretooluse_git(stdin_text=_payload('git commit -m "docs: tweak CLAUDE.md" -- CLAUDE.md'))
    assert rc == 0
    err = capsys.readouterr().err
    assert "WARN [RULING-277]" in err
    assert "CLAUDE.md" in err


def test_pretooluse_git_warns_on_uncited_tools_hooks(tmp_path, monkeypatch, capsys):
    root = _governance_repo(tmp_path, monkeypatch)
    _stage(root, "tools/hooks/pre-commit", "#!/bin/sh\n")
    rc = run_pretooluse_git(stdin_text=_payload('git commit -m "fix hook" -- tools/hooks/pre-commit'))
    assert rc == 0
    err = capsys.readouterr().err
    assert "WARN [RULING-277]" in err
    assert "tools/hooks/pre-commit" in err


def test_pretooluse_git_warns_on_mixed_governance_and_source_paths(tmp_path, monkeypatch, capsys):
    """A commit spanning BOTH a governance path and an ordinary source file must
    still warn -- the mix does not exempt it (done_when item 3, explicit)."""
    root = _governance_repo(tmp_path, monkeypatch)
    _stage(root, ".claude/settings.json", "{}\n")
    _stage(root, "src/foo.py", "print(1)\n")
    rc = run_pretooluse_git(stdin_text=_payload('git commit -m "mixed change" -- .claude/settings.json src/foo.py'))
    assert rc == 0
    err = capsys.readouterr().err
    assert "WARN [RULING-277]" in err
    assert ".claude/settings.json" in err


def test_pretooluse_git_escalates_on_third_uncited_commit_same_author_same_session(tmp_path, monkeypatch, capsys):
    root = _governance_repo(tmp_path, monkeypatch)
    session = "sess-escalate"
    for i in range(2):
        _stage(root, ".claude/settings.json", f"{{'n': {i}}}\n")
        rc = run_pretooluse_git(
            stdin_text=_payload('git commit -m "tweak settings" -- .claude/settings.json', session_id=session)
        )
        assert rc == 0
        err = capsys.readouterr().err
        assert "WARN [RULING-277]" in err
        assert "ESCALATE" not in err, f"must not escalate before the 3rd warning (warning #{i + 1})"

    _stage(root, ".claude/settings.json", "{'n': 2}\n")
    rc = run_pretooluse_git(
        stdin_text=_payload('git commit -m "tweak settings again" -- .claude/settings.json', session_id=session)
    )
    assert rc == 0
    err = capsys.readouterr().err
    assert "WARN [RULING-277]" in err
    assert "ESCALATE [RULING-277]" in err
    assert "RULING-277" in err


def test_pretooluse_git_escalation_counter_is_scoped_per_session(tmp_path, monkeypatch, capsys):
    """A DIFFERENT session_id must not inherit another session's warn count --
    keying by session_id is the whole point of the chosen persistence mechanism
    (SOW-2 s2): a new Claude Code session starts at zero."""
    root = _governance_repo(tmp_path, monkeypatch)
    for i in range(3):
        _stage(root, ".claude/settings.json", f"{{'n': {i}}}\n")
        run_pretooluse_git(
            stdin_text=_payload('git commit -m "tweak settings" -- .claude/settings.json', session_id="sess-A")
        )
        capsys.readouterr()

    _stage(root, "CLAUDE.md", "# change\n")
    rc = run_pretooluse_git(stdin_text=_payload('git commit -m "docs tweak" -- CLAUDE.md', session_id="sess-B"))
    assert rc == 0
    err = capsys.readouterr().err
    assert "WARN [RULING-277]" in err
    assert "ESCALATE" not in err, "a fresh session_id must not carry over sess-A's warn count"


def test_pretooluse_git_bypass_command_still_short_circuits(tmp_path, monkeypatch, capsys):
    """Pre-existing behavior (not touched by this change): a non-git-commit/push
    tool call is a fast no-op."""
    root = _governance_repo(tmp_path, monkeypatch)
    rc = run_pretooluse_git(stdin_text='{"tool_input":{"command":"ls"}}')
    assert rc == 0
    err = capsys.readouterr().err
    assert err == ""


def test_unstage_generated_boards_lets_a_deletion_through(tmp_path):
    """Paid live in zeroemployeeorg/org (2026-08-16): STATE.md and stream-index.md were
    BOTH listed in .gitignore ('zeo generated boards - do not commit') AND tracked by
    git. .gitignore has no effect on already-tracked files, so they sat permanently
    dirty in every seat's working tree, and every attempt to commit them produced an
    EMPTY commit because this function unstaged them first. STATE.md's last real
    content commit was a week stale while the on-disk board showed today - which reads
    as lost work to anyone comparing the two.

    The fix is `git rm --cached`, i.e. a staged DELETION. But this function unstaged
    that too, so the hook blocked its own intended end state and the cleanup could
    only land with --no-verify. A deletion is the untracking act, not an attempt to
    commit board content: it must pass through."""
    from zero_employee.hooks import unstage_generated_boards

    root = _corpus(tmp_path)
    board = root / "STATE.md"
    board.write_text("# board\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "STATE.md"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "track board"], check=True, capture_output=True)

    # Staged CONTENT change: still unstaged (the original, still-wanted behaviour).
    board.write_text("# board changed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "STATE.md"], check=True, capture_output=True)
    assert "STATE.md" in unstage_generated_boards(root)
    staged_now = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
    ).stdout
    assert "STATE.md" not in staged_now, "a staged content change must still be unstaged"

    # Staged DELETION (`git rm --cached`): must survive, or untracking is impossible.
    subprocess.run(["git", "-C", str(root), "rm", "--cached", "STATE.md"], check=True, capture_output=True)
    unstage_generated_boards(root)
    still_staged = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--name-status"],
        capture_output=True,
        text=True,
    ).stdout
    assert still_staged.strip().startswith("D"), (
        "a staged deletion is the untracking act and must pass through the hook"
    )
    assert board.is_file(), "git rm --cached must leave the file on disk"
