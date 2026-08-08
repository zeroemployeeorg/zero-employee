"""sow-lint hooks install — templates into tools/hooks + git pre-commit."""

from __future__ import annotations

import json
import subprocess

from zero_employee import cli
from zero_employee.hooks import hooks_install
from zero_employee.cost import parse_transcript_usage, append_session_cost_log, session_cost_report


def _corpus(tmp_path):
    root = tmp_path / "org"
    (root / "claude-md").mkdir(parents=True)
    (root / "claude-md" / "CLAUDE.md").write_text("# CLAUDE\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    return root


def test_hooks_install_writes_templates_and_git_hook(tmp_path):
    root = _corpus(tmp_path)
    info = hooks_install(root)
    assert (root / "tools" / "hooks" / "pre-commit").is_file()
    assert (root / "tools" / "hooks" / "cc-stop.sh").is_file()
    stop = (root / "tools" / "hooks" / "cc-stop.sh").read_text(encoding="utf-8")
    assert "--session-cost" in stop
    assert "RATE_TABLE" not in stop
    assert info["git_hook"]
    assert (root / ".git" / "hooks" / "pre-commit").is_file()


def test_cli_hooks_install(tmp_path, capsys):
    root = _corpus(tmp_path)
    rc = cli.main(["hooks", "install", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "HOOKS-INSTALL" in out
    assert (root / "tools" / "hooks" / "cc-session-start.sh").is_file()


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
