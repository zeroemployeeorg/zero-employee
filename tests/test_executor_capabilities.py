"""A2: ExecutorCapabilities honesty rules."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from zero_employee.schemas.executor import ExecutorCapabilities

_NOW = datetime(2026, 8, 22, tzinfo=timezone.utc)


def _caps(**over):
    data = {
        "schema_version": 1,
        "executor": "sandcastle",
        "executor_version": "0.12.0",
        "agent_provider": "codex",
        "agent_provider_version": "unknown",
        "sandbox_kind": "isolated",
        "filesystem_isolation": True,
        "network_policy": "declared",
        "streaming_events": True,
        "structured_output": True,
        "session_capture": True,
        "session_resume": True,
        "session_fork": True,
        "operation_abort": True,
        "idle_timeout": True,
        "completion_timeout": True,
        "lifecycle_timeouts": True,
        "branch_strategy": "branch",
        "exclusive_worktree_lock": True,
        "credential_mode": "environment",
        "verified_at": _NOW,
        "verification_receipt": None,
    }
    data.update(over)
    return data


def test_valid_declared_manifest_round_trips():
    m = ExecutorCapabilities.model_validate(_caps())
    assert m.session_resume is True
    assert m.network_policy == "declared"
    again = ExecutorCapabilities.model_validate(m.model_dump(mode="json"))
    assert again.executor == "sandcastle"


def test_session_resume_without_capture_is_rejected():
    with pytest.raises(ValidationError, match="session_resume"):
        ExecutorCapabilities.model_validate(_caps(session_capture=False, session_resume=True, session_fork=False))


def test_session_fork_without_capture_is_rejected():
    with pytest.raises(ValidationError, match="session_fork"):
        ExecutorCapabilities.model_validate(_caps(session_capture=False, session_resume=False, session_fork=True))


def test_filesystem_isolation_with_sandbox_none_is_rejected():
    with pytest.raises(ValidationError, match="filesystem_isolation"):
        ExecutorCapabilities.model_validate(_caps(sandbox_kind="none", filesystem_isolation=True))


def test_enforced_network_without_probe_receipt_is_rejected():
    with pytest.raises(ValidationError, match="verification_receipt"):
        ExecutorCapabilities.model_validate(_caps(network_policy="enforced", verification_receipt=None))


def test_enforced_network_with_probe_receipt_is_accepted():
    m = ExecutorCapabilities.model_validate(
        _caps(network_policy="enforced", verification_receipt="executions/probe.execution.json")
    )
    assert m.network_policy == "enforced"


def test_unknown_network_policy_is_not_coerced():
    m = ExecutorCapabilities.model_validate(_caps(network_policy="unknown"))
    assert m.network_policy == "unknown"


def test_isolated_sandbox_requires_filesystem_isolation():
    with pytest.raises(ValidationError, match="isolated"):
        ExecutorCapabilities.model_validate(_caps(sandbox_kind="isolated", filesystem_isolation=False))
