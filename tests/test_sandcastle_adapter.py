"""A4: Sandcastle adapter is optional, fixture-only, never a Node subprocess."""

from __future__ import annotations

import json
import pathlib

import pytest

from zero_employee.adapters.sandcastle import SandcastleEvidenceAdapter
from zero_employee.cli import main

_FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "sandcastle"

pytestmark = pytest.mark.adapter


def test_probe_fixture_is_honest_capabilities():
    payload = json.loads((_FIXTURES / "probe.json").read_text(encoding="utf-8"))
    caps = SandcastleEvidenceAdapter(payload).probe()
    assert caps.executor == "sandcastle"
    assert caps.session_resume is True
    assert caps.sandbox_kind == "isolated"


def test_import_sandcastle_shaped_result():
    rec = SandcastleEvidenceAdapter().import_receipt(_FIXTURES / "result.json")
    assert rec.runtime == "sandcastle"
    assert rec.runtime_address == "codex-session-xyz"
    assert rec.termination == "completed"
    assert rec.commits[0].sha == "aaa111"
    assert rec.commits[0].remote_contains is False


def test_cli_import_sandcastle_shaped_result(tmp_path):
    dest = tmp_path / "out.execution.json"
    assert main(["execution", "import", str(_FIXTURES / "result.json"), "--out", str(dest)]) == 0
    text = dest.read_text(encoding="utf-8")
    assert "sc_run_1" in text


def test_adapter_does_not_search_session_directories(monkeypatch):
    """R4: no filesystem crawl for provider sessions."""

    def boom(self, *args, **kwargs):
        raise AssertionError("adapter must not rglob session stores")

    monkeypatch.setattr(pathlib.Path, "rglob", boom)
    SandcastleEvidenceAdapter().import_receipt(_FIXTURES / "result.json")
