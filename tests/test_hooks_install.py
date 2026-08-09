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
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
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
