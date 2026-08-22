"""A3: append-only execution receipt (JSON evidence, not a board or transcript)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Termination = Literal[
    "completed",
    "completed_process_hanging",
    "idle_timeout",
    "lifecycle_timeout",
    "aborted",
    "provider_error",
    "sandbox_error",
    "invalid_structured_output",
    "unknown",
]

TERMINATION_CLASSES: tuple[str, ...] = (
    "completed",
    "completed_process_hanging",
    "idle_timeout",
    "lifecycle_timeout",
    "aborted",
    "provider_error",
    "sandbox_error",
    "invalid_structured_output",
    "unknown",
)


class ReceiptCommit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sha: str
    remote_contains: bool = False
    remote: str | None = None
    containment_verified_at: datetime | None = None

    @model_validator(mode="after")
    def _delivery_evidence(self) -> ReceiptCommit:
        if self.remote_contains:
            if not (self.remote or "").strip():
                raise ValueError("remote_contains: true requires a named remote")
            if self.containment_verified_at is None:
                raise ValueError("remote_contains: true requires containment_verified_at (delivery evidence)")
        return self


class ReceiptUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int = 0
    output_tokens: int = 0
    source: Literal["provider", "estimate", "unknown"] = "provider"


class ExecutionReceipt(BaseModel):
    """Governed envelope for one harness execution. Not a transcript."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    execution_id: str
    conversation_id: str | None = None
    seat_type: str
    seat_instance: str
    runtime: str
    runtime_address: str | None = None
    agent_provider: str
    sandbox_provider: str | None = None
    sandbox_kind: Literal["isolated", "bind-mount", "none"] | None = None
    branch: str | None = None
    base_commit: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    termination: Termination
    completion_signal_seen: bool
    structured_result_valid: bool
    commits: list[ReceiptCommit] = Field(default_factory=list)
    usage: ReceiptUsage = Field(default_factory=ReceiptUsage)
    capability_manifest_ref: str | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    log_ref: str | None = None
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _completion_independent_of_payload(self) -> ExecutionReceipt:
        if self.termination == "invalid_structured_output" and self.structured_result_valid:
            raise ValueError("termination invalid_structured_output cannot pair with structured_result_valid: true")
        if self.termination == "completed" and not self.completion_signal_seen:
            raise ValueError("termination completed requires completion_signal_seen: true")
        return self


def dump_canonical(model: BaseModel) -> str:
    """Stable JSON for append-only receipts (sorted keys, JSON mode)."""
    data: Any = model.model_dump(mode="json")
    return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def load_receipt(data: dict[str, Any]) -> ExecutionReceipt:
    return ExecutionReceipt.model_validate(data)
