"""Optional Sandcastle evidence adapter.

Parses Sandcastle-shaped JSON fixtures into governed schemas. Does not invoke
Node, Docker, or the Sandcastle package. Session files are never crawled.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from zero_employee.schemas.execution_receipt import (
    ExecutionReceipt,
    ReceiptCommit,
    ReceiptUsage,
)
from zero_employee.schemas.executor import ExecutorCapabilities

_TERMINATION_ALIASES = {
    "success": "completed",
    "ok": "completed",
    "done": "completed",
}


def _as_dt(value: object, default: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    if default is not None:
        return default
    return datetime.now(timezone.utc)


class SandcastleEvidenceAdapter:
    """Maps a Sandcastle result/probe JSON object onto ZE contracts."""

    def __init__(self, payload: dict | None = None):
        self.payload = payload or {}

    def probe(self) -> ExecutorCapabilities:
        caps = self.payload.get("capabilities") or self.payload
        return ExecutorCapabilities.model_validate(caps)

    def import_receipt(self, source: Path) -> ExecutionReceipt:
        data = json.loads(Path(source).read_text(encoding="utf-8"))
        return self._receipt_from_result(data)

    def _receipt_from_result(self, data: dict) -> ExecutionReceipt:
        if data.get("schema_version") == 1 and data.get("execution_id"):
            return ExecutionReceipt.model_validate(data)
        result = data.get("result") or data
        commits = []
        for item in result.get("commits") or []:
            if isinstance(item, str):
                commits.append(ReceiptCommit(sha=item, remote_contains=False))
            elif isinstance(item, dict):
                commits.append(ReceiptCommit.model_validate(item))
        usage_raw = result.get("usage") or {}
        term = str(result.get("termination") or result.get("status") or "unknown")
        term = _TERMINATION_ALIASES.get(term, term)
        ended_raw = result.get("ended_at") or result.get("endedAt")
        source = usage_raw.get("source") or "provider"
        if source not in ("provider", "estimate", "unknown"):
            source = "unknown"
        return ExecutionReceipt(
            execution_id=str(result.get("execution_id") or result.get("id") or "exec_imported"),
            conversation_id=result.get("conversation_id"),
            seat_type=str(result.get("seat_type") or "unknown"),
            seat_instance=str(result.get("seat_instance") or "unknown"),
            runtime=str(result.get("runtime") or "sandcastle"),
            runtime_address=result.get("sessionId") or result.get("runtime_address"),
            agent_provider=str(result.get("agent_provider") or result.get("agent") or "unknown"),
            sandbox_provider=result.get("sandbox_provider") or result.get("sandbox"),
            sandbox_kind=result.get("sandbox_kind"),
            branch=result.get("branch"),
            base_commit=result.get("base_commit") or result.get("baseSha"),
            started_at=_as_dt(result.get("started_at") or result.get("startedAt")),
            ended_at=_as_dt(ended_raw) if ended_raw else None,
            termination=term,  # type: ignore[arg-type]
            completion_signal_seen=bool(result.get("completion_signal_seen", term == "completed")),
            structured_result_valid=bool(result.get("structured_result_valid", False)),
            commits=commits,
            usage=ReceiptUsage(
                input_tokens=int(usage_raw.get("input_tokens") or usage_raw.get("input") or 0),
                output_tokens=int(usage_raw.get("output_tokens") or usage_raw.get("output") or 0),
                source=source,
            ),
            capability_manifest_ref=result.get("capability_manifest_ref"),
            artifact_refs=list(result.get("artifact_refs") or []),
            log_ref=result.get("log_ref") or result.get("log"),
            warnings=list(result.get("warnings") or []),
        )
