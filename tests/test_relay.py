"""Seat-instance relay ledger: addressing, ack, idempotency, no spawn-by-name."""

from __future__ import annotations

import pytest

from zero_employee import relay
from zero_employee.cli import main
from zero_employee.relay import MAX_DELIVERY_ATTEMPTS
from zero_employee.scaffold import init_corpus


def _corpus(tmp_path):
    root = tmp_path / "org"
    init_corpus(root)
    return root


def test_register_send_receive_ack(tmp_path):
    root = _corpus(tmp_path)
    relay.register(root, seat="master", instance_id="master-1", runtime="codex", thread_id="t-m")
    relay.register(root, seat="sparring", instance_id="sparring-1", runtime="codex", thread_id="t-s")
    msg = relay.send(
        root,
        from_instance="master-1",
        to_instance="sparring-1",
        kind="review-request",
        body="review this",
        artifact_refs=["ruling/RULING-351.md"],
        conversation_id="round_1",
        message_id="msg_fixed",
    )
    assert msg.state == "queued"
    again = relay.send(
        root,
        from_instance="master-1",
        to_instance="sparring-1",
        kind="review-request",
        body="review this AGAIN",
        message_id="msg_fixed",
    )
    assert again.body == "review this"
    pending = relay.receive(root, "sparring-1")
    assert [p.message_id for p in pending] == ["msg_fixed"]
    assert pending[0].artifact_refs == ["ruling/RULING-351.md"]
    acked = relay.ack(root, "msg_fixed")
    assert acked.state == "acked"
    assert relay.receive(root, "sparring-1") == []


def test_should_not_spawn_when_sparring_registered(tmp_path):
    root = _corpus(tmp_path)
    relay.register(root, seat="zeo-sparring", instance_id="sparring-1", runtime="codex", thread_id="t")
    found = relay.resolve(root, seat="sparring")
    assert found[0].instance_id == "sparring-1"
    assert relay.should_spawn("sparring", root) is False
    assert relay.should_spawn("master", root) is True


def test_exclusive_seat_refuses_second_active(tmp_path):
    root = _corpus(tmp_path)
    relay.register(root, seat="master", instance_id="master-1", runtime="codex")
    with pytest.raises(relay.RelayError, match="already registered"):
        relay.register(root, seat="master", instance_id="master-2", runtime="codex")


def test_dead_letter_after_retry_budget(tmp_path):
    root = _corpus(tmp_path)
    relay.register(root, seat="master", instance_id="m1", runtime="codex")
    relay.register(root, seat="sparring", instance_id="s1", runtime="codex")
    msg = relay.send(root, from_instance="m1", to_instance="s1", kind="canary", body="x")
    for _ in range(MAX_DELIVERY_ATTEMPTS):
        updated = relay.mark_delivery_failed(root, msg.message_id, "boom")
    assert updated.state == "dead"
    assert (root / "executions" / "relay" / "dead-letter" / f"{msg.message_id}.json").is_file()


def test_file_verdict_rejects_source_paths(tmp_path):
    root = _corpus(tmp_path)
    with pytest.raises(relay.RelayError):
        relay.file_verdict(root, dest_rel="src/foo.py", body="nope")
    path = relay.file_verdict(root, dest_rel="ruling/V.md", body="# v\n")
    assert path.read_text(encoding="utf-8") == "# v\n"


def test_cli_relay_roundtrip(tmp_path):
    root = _corpus(tmp_path)
    assert (
        main(
            [
                "relay",
                "register",
                "--seat",
                "master",
                "--instance",
                "m1",
                "--runtime",
                "codex",
                "--thread-id",
                "tm",
                "--root",
                str(root),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "relay",
                "register",
                "--seat",
                "sparring",
                "--instance",
                "s1",
                "--runtime",
                "codex",
                "--thread-id",
                "ts",
                "--root",
                str(root),
            ]
        )
        == 0
    )
    rc = main(
        [
            "relay",
            "send",
            "--from",
            "m1",
            "--to",
            "s1",
            "--kind",
            "canary",
            "--body",
            "hi",
            "--root",
            str(root),
            "--json",
        ]
    )
    assert rc == 0


def test_relay_is_not_sow_inbox(tmp_path):
    root = _corpus(tmp_path)
    relay.register(root, seat="stream", instance_id="stream-1", runtime="codex")
    status = relay.status_payload(root)
    assert status["queued"] == 0
    assert (root / "executions" / "relay" / "instances" / "stream-1.json").is_file()
    msgs_dir = root / "executions" / "relay" / "messages"
    assert not msgs_dir.exists() or not list(msgs_dir.glob("*.json"))
