"""A3: execution receipts — round-trip, termination classes, delivery honesty."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from zero_employee.cli import main
from zero_employee.execution import iter_execution_receipts, validate_receipt_path, write_canonical_receipt
from zero_employee.schemas.execution_receipt import (
    TERMINATION_CLASSES,
    dump_canonical,
    load_receipt,
)

_NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


def _receipt(**over):
    data = {
        "schema_version": 1,
        "execution_id": "exec_1",
        "conversation_id": "round_1",
        "seat_type": "zeo-stream",
        "seat_instance": "stream-1",
        "runtime": "sandcastle",
        "runtime_address": "session-abc",
        "agent_provider": "codex",
        "sandbox_provider": "docker",
        "sandbox_kind": "bind-mount",
        "branch": "agent/exec_1",
        "base_commit": "abc123",
        "started_at": _NOW,
        "ended_at": _NOW,
        "termination": "completed",
        "completion_signal_seen": True,
        "structured_result_valid": True,
        "commits": [],
        "usage": {"input_tokens": 1, "output_tokens": 2, "source": "provider"},
        "capability_manifest_ref": "caps/sandcastle.json",
        "artifact_refs": ["projects/p/sow/s/S-SOW-1.md"],
        "log_ref": ".sandcastle/logs/exec_1.log",
        "warnings": [],
    }
    data.update(over)
    return data


@pytest.mark.parametrize("term", TERMINATION_CLASSES)
def test_every_termination_class_round_trips(term, tmp_path):
    payload = _receipt(
        termination=term,
        completion_signal_seen=term == "completed" or term == "completed_process_hanging",
        structured_result_valid=term != "invalid_structured_output",
        execution_id=f"exec_{term}",
    )
    if term == "completed":
        payload["completion_signal_seen"] = True
    rec = load_receipt(payload)
    text = dump_canonical(rec)
    dest = tmp_path / f"{term}.execution.json"
    dest.write_text(text, encoding="utf-8")
    again, errors = validate_receipt_path(dest)
    assert errors == []
    assert again.termination == term
    assert again.model_dump(mode="json") == rec.model_dump(mode="json")


def test_completion_does_not_imply_valid_structured_result():
    rec = load_receipt(_receipt(completion_signal_seen=True, structured_result_valid=False, termination="completed"))
    assert rec.completion_signal_seen is True
    assert rec.structured_result_valid is False


def test_delivered_commit_without_remote_is_rejected():
    with pytest.raises(ValidationError, match="named remote"):
        load_receipt(_receipt(commits=[{"sha": "deadbeef", "remote_contains": True}]))


def test_delivered_commit_without_verification_time_is_rejected():
    with pytest.raises(ValidationError, match="containment_verified_at"):
        load_receipt(_receipt(commits=[{"sha": "deadbeef", "remote_contains": True, "remote": "origin"}]))


def test_delivered_commit_with_evidence_is_accepted():
    rec = load_receipt(
        _receipt(
            commits=[
                {
                    "sha": "deadbeef",
                    "remote_contains": True,
                    "remote": "origin",
                    "containment_verified_at": _NOW,
                }
            ]
        )
    )
    assert rec.commits[0].remote_contains is True


def test_walker_finds_execution_json_not_markdown(tmp_path):
    (tmp_path / "executions").mkdir()
    p = tmp_path / "executions" / "a.execution.json"
    write_canonical_receipt(load_receipt(_receipt()), p)
    (tmp_path / "executions" / "note.md").write_text("# not a receipt\n", encoding="utf-8")
    found = iter_execution_receipts(tmp_path)
    assert found == [p]


def test_cli_validate_and_import(tmp_path):
    rec = load_receipt(_receipt())
    src = tmp_path / "in.execution.json"
    src.write_text(dump_canonical(rec), encoding="utf-8")
    assert main(["execution", "validate", str(src)]) == 0
    out = tmp_path / "out.execution.json"
    assert main(["execution", "import", str(src), "--out", str(out)]) == 0
    assert out.is_file()


def test_commit_check_corpus_validates_receipts_when_present(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    (tmp_path / "executions").mkdir()
    bad = tmp_path / "executions" / "bad.execution.json"
    bad.write_text('{"schema_version": 1, "execution_id": "x"}\n', encoding="utf-8")
    assert main(["--commit-check-corpus", str(tmp_path)]) == 1


def test_commit_check_corpus_quiet_without_receipts(tmp_path, capsys):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    rc = main(["--commit-check-corpus", str(tmp_path)])
    assert rc == 0
    assert "execution receipt" not in capsys.readouterr().out
