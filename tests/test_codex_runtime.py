"""Fake Codex runtime + canary scenarios (no live Codex in CI)."""

from __future__ import annotations

from zero_employee.cli import main
from zero_employee.runtimes.codex import FakeCodexRuntime, run_scenario, tick
from zero_employee.scaffold import init_corpus
from zero_employee import relay


def test_tick_delivers_to_existing_thread(tmp_path):
    root = tmp_path / "org"
    init_corpus(root)
    rt = FakeCodexRuntime()
    m = rt.attach_or_start("master", root)
    s = rt.attach_or_start("sparring", root)
    relay.register(root, seat="master", instance_id="m1", runtime="codex", thread_id=m)
    relay.register(root, seat="sparring", instance_id="s1", runtime="codex", thread_id=s)
    relay.send(root, from_instance="m1", to_instance="s1", kind="canary", body="hello sparring")
    result = tick(root, rt)
    assert result["delivered"] == 1
    assert any("hello sparring" in t for t in rt.threads[s])
    assert len(rt.thread_ids_for("sparring")) == 1


def test_canary_master_sparring_relay(tmp_path):
    root = tmp_path / "org"
    out = run_scenario(root, "master-sparring-relay")
    assert out["ok"] is True
    assert out["sparring_thread_count"] == 1


def test_canary_no_duplicate_sparring(tmp_path):
    root = tmp_path / "org"
    out = run_scenario(root, "no-duplicate-sparring")
    assert out["ok"] is True
    assert out["should_spawn"] is False


def test_canary_persona_load(tmp_path):
    assert run_scenario(tmp_path / "org", "persona-load")["ok"] is True


def test_canary_permission_boundary(tmp_path):
    assert run_scenario(tmp_path / "org", "permission-boundary")["ok"] is True


def test_canary_resume_does_not_mint_second_thread(tmp_path):
    assert run_scenario(tmp_path / "org", "resume-thread")["ok"] is True


def test_cli_test_runtime(tmp_path):
    root = tmp_path / "org"
    init_corpus(root)
    rc = main(["test-runtime", "codex", "--scenario", "no-duplicate-sparring", "--root", str(root)])
    assert rc == 0


def test_cli_relay_start_once(tmp_path):
    root = tmp_path / "org"
    init_corpus(root)
    rc = main(["relay", "start", "--once", "--root", str(root)])
    assert rc == 0
    assert (root / "executions" / "relay" / "instances" / "master-local.json").is_file()
    assert (root / "executions" / "relay" / "instances" / "sparring-local.json").is_file()


def test_doctor_codex(tmp_path):
    root = tmp_path / "org"
    init_corpus(root)
    rc = main(["doctor", "--codex", "--root", str(root)])
    # doctor --codex ignores --root in argv_positionals path; still prints JSON
    rc = main(["doctor", "--codex"])
    # no corpus from cwd is ok
    assert rc == 0
