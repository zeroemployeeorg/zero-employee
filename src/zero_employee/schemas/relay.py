"""Seat-instance registry and relay message envelopes (not SOW inbox, not receipts)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SeatKind = Literal["master", "sparring", "stream"]
InstanceStatus = Literal["active", "faulted", "retired"]
WriteAuthority = Literal["none", "ruling-only", "workspace-write"]
MessageState = Literal["queued", "delivered", "acked", "dead"]
MessageKind = Literal[
    "review-request",
    "review-verdict",
    "follow-up",
    "undeliverable",
    "heartbeat",
    "canary",
]


class SeatInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    seat_type: SeatKind
    instance_id: str
    runtime: str
    runtime_address: str | None = None
    repository: str | None = None
    worktree: str | None = None
    branch: str | None = None
    base_sha: str | None = None
    stream: str | None = None
    current_sow: str | None = None
    conversation_id: str | None = None
    write_authority: WriteAuthority = "workspace-write"
    status: InstanceStatus = "active"
    last_heartbeat: datetime | None = None
    registered_at: datetime


class RelayMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    message_id: str
    conversation_id: str
    from_instance: str
    to_instance: str
    kind: MessageKind
    created_at: datetime
    reply_to: str | None = None
    requires_ack: bool = True
    artifact_refs: list[str] = Field(default_factory=list)
    body: str
    state: MessageState = "queued"
    delivery_attempts: int = 0
    last_error: str | None = None
    acked_at: datetime | None = None
    delivered_at: datetime | None = None
