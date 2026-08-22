"""A2: versioned executor capability manifest (evidence, not invocation).

Describes what an external harness demonstrably supports. Does not run the
harness. `unknown` and `declared` must never be coerced into false safety or
true enforcement.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SandboxKind = Literal["isolated", "bind-mount", "none"]
NetworkPolicy = Literal["enforced", "declared", "unknown"]
BranchStrategy = Literal["head", "merge-to-head", "branch"]


class ExecutorCapabilities(BaseModel):
    """Serializable capability claim for an external executor."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    executor: str
    executor_version: str
    agent_provider: str
    agent_provider_version: str = "unknown"
    sandbox_kind: SandboxKind
    filesystem_isolation: bool
    network_policy: NetworkPolicy
    streaming_events: bool
    structured_output: bool
    session_capture: bool
    session_resume: bool
    session_fork: bool
    operation_abort: bool
    idle_timeout: bool
    completion_timeout: bool
    lifecycle_timeouts: bool
    branch_strategy: BranchStrategy
    exclusive_worktree_lock: bool
    credential_mode: str
    verified_at: datetime | None = None
    verification_receipt: str | None = Field(
        default=None,
        description="Path or id of a probe receipt. Absent => claims are declared, not enforced.",
    )

    @model_validator(mode="after")
    def _honesty(self) -> ExecutorCapabilities:
        if self.session_resume and not self.session_capture:
            raise ValueError("session_resume: true requires session_capture (storage evidence)")
        if self.session_fork and not self.session_capture:
            raise ValueError("session_fork: true requires session_capture (fork is session-only)")
        if self.filesystem_isolation and self.sandbox_kind == "none":
            raise ValueError("filesystem_isolation: true is incompatible with sandbox_kind: none")
        if self.network_policy == "enforced" and not (self.verification_receipt or "").strip():
            raise ValueError(
                "network_policy: enforced requires a verification_receipt; "
                "a self-description without a probe is declared, not enforced"
            )
        if self.sandbox_kind == "isolated" and not self.filesystem_isolation:
            raise ValueError("sandbox_kind: isolated requires filesystem_isolation: true")
        return self
