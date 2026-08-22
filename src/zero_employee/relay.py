"""Durable seat-instance registry and message ledger.

Coordinates live agents. Does not replace `zeo --inbox` (artifact relay) or
`zeo seat` (GitHub identity).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .schemas.execution_receipt import dump_canonical
from .schemas.relay import RelayMessage, SeatInstance, SeatKind, WriteAuthority

MAX_DELIVERY_ATTEMPTS = 5
EXCLUSIVE_SEATS: frozenset[SeatKind] = frozenset({"master", "sparring"})
_SEAT_ALIASES: dict[str, SeatKind] = {
    "master": "master",
    "zeo-master": "master",
    "sparring": "sparring",
    "zeo-sparring": "sparring",
    "stream": "stream",
    "zeo-stream": "stream",
}
_INSTANCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,80}$")


class RelayError(Exception):
    """Operator-visible relay failure."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_seat_type(raw: str) -> SeatKind:
    key = (raw or "").strip().lower()
    if key in _SEAT_ALIASES:
        return _SEAT_ALIASES[key]
    raise RelayError(f"unknown seat type {raw!r} (use master, sparring, or stream)")


def new_message_id() -> str:
    return f"msg_{uuid.uuid4().hex[:16]}"


def relay_root(corpus: Path) -> Path:
    return Path(corpus) / "executions" / "relay"


def instances_dir(corpus: Path) -> Path:
    return relay_root(corpus) / "instances"


def messages_dir(corpus: Path) -> Path:
    return relay_root(corpus) / "messages"


def dead_letter_dir(corpus: Path) -> Path:
    return relay_root(corpus) / "dead-letter"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        with Path(tmp_name) as tmp:
            if tmp.exists():
                tmp.unlink()
        raise


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def instance_path(corpus: Path, instance_id: str) -> Path:
    return instances_dir(corpus) / f"{instance_id}.json"


def message_path(corpus: Path, message_id: str, *, dead: bool = False) -> Path:
    folder = dead_letter_dir(corpus) if dead else messages_dir(corpus)
    return folder / f"{message_id}.json"


def load_instance(corpus: Path, instance_id: str) -> SeatInstance:
    path = instance_path(corpus, instance_id)
    if not path.is_file():
        raise RelayError(f"no registered instance {instance_id!r}")
    return SeatInstance.model_validate(_load_json(path))


def save_instance(corpus: Path, instance: SeatInstance) -> Path:
    path = instance_path(corpus, instance.instance_id)
    _atomic_write(path, dump_canonical(instance))
    return path


def load_message(corpus: Path, message_id: str) -> RelayMessage:
    live = message_path(corpus, message_id)
    dead = message_path(corpus, message_id, dead=True)
    if live.is_file():
        return RelayMessage.model_validate(_load_json(live))
    if dead.is_file():
        return RelayMessage.model_validate(_load_json(dead))
    raise RelayError(f"no relay message {message_id!r}")


def save_message(corpus: Path, message: RelayMessage) -> Path:
    dead = message.state == "dead"
    dest = message_path(corpus, message.message_id, dead=dead)
    other = message_path(corpus, message.message_id, dead=not dead)
    _atomic_write(dest, dump_canonical(message))
    if other.exists() and other != dest:
        other.unlink()
    return dest


def list_instances(corpus: Path) -> list[SeatInstance]:
    folder = instances_dir(corpus)
    if not folder.is_dir():
        return []
    out: list[SeatInstance] = []
    for path in sorted(folder.glob("*.json")):
        out.append(SeatInstance.model_validate(_load_json(path)))
    return out


def list_messages(corpus: Path, *, include_dead: bool = True) -> list[RelayMessage]:
    out: list[RelayMessage] = []
    for folder, dead in ((messages_dir(corpus), False), (dead_letter_dir(corpus), True)):
        if not include_dead and dead:
            continue
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            out.append(RelayMessage.model_validate(_load_json(path)))
    return out


def register(
    corpus: Path,
    *,
    seat: str,
    instance_id: str,
    runtime: str,
    thread_id: str | None = None,
    worktree: str | None = None,
    branch: str | None = None,
    repository: str | None = None,
    stream: str | None = None,
    write_authority: WriteAuthority | None = None,
    conversation_id: str | None = None,
    current_sow: str | None = None,
    base_sha: str | None = None,
) -> SeatInstance:
    if not _INSTANCE_RE.match(instance_id):
        raise RelayError(f"invalid instance id {instance_id!r}")
    seat_type = normalize_seat_type(seat)
    existing = None
    path = instance_path(corpus, instance_id)
    if path.is_file():
        existing = load_instance(corpus, instance_id)
    if seat_type in EXCLUSIVE_SEATS:
        peers = [
            inst
            for inst in list_instances(corpus)
            if inst.seat_type == seat_type and inst.status == "active" and inst.instance_id != instance_id
        ]
        if peers:
            raise RelayError(
                f"active {seat_type} instance already registered: {peers[0].instance_id} "
                "(retire it before registering another)"
            )
    authority: WriteAuthority = write_authority or ("ruling-only" if seat_type == "sparring" else "workspace-write")
    now = utcnow()
    inst = SeatInstance(
        seat_type=seat_type,
        instance_id=instance_id,
        runtime=runtime,
        runtime_address=thread_id if thread_id else (existing.runtime_address if existing else None),
        repository=repository if repository is not None else (existing.repository if existing else None),
        worktree=worktree if worktree is not None else (existing.worktree if existing else None),
        branch=branch if branch is not None else (existing.branch if existing else None),
        base_sha=base_sha if base_sha is not None else (existing.base_sha if existing else None),
        stream=stream if stream is not None else (existing.stream if existing else None),
        current_sow=current_sow if current_sow is not None else (existing.current_sow if existing else None),
        conversation_id=conversation_id
        if conversation_id is not None
        else (existing.conversation_id if existing else None),
        write_authority=authority,
        status="active",
        last_heartbeat=now,
        registered_at=existing.registered_at if existing else now,
    )
    save_instance(corpus, inst)
    return inst


def heartbeat(corpus: Path, instance_id: str) -> SeatInstance:
    inst = load_instance(corpus, instance_id)
    inst.last_heartbeat = utcnow()
    save_instance(corpus, inst)
    return inst


def retire(corpus: Path, instance_id: str) -> SeatInstance:
    inst = load_instance(corpus, instance_id)
    inst.status = "retired"
    inst.last_heartbeat = utcnow()
    save_instance(corpus, inst)
    return inst


def mark_faulted(corpus: Path, instance_id: str) -> SeatInstance:
    inst = load_instance(corpus, instance_id)
    inst.status = "faulted"
    inst.last_heartbeat = utcnow()
    save_instance(corpus, inst)
    return inst


def resolve(
    corpus: Path,
    *,
    seat: str | None = None,
    instance_id: str | None = None,
) -> list[SeatInstance]:
    if instance_id:
        inst = load_instance(corpus, instance_id)
        return [inst]
    if not seat:
        raise RelayError("resolve requires --seat or --instance")
    seat_type = normalize_seat_type(seat)
    active = [inst for inst in list_instances(corpus) if inst.seat_type == seat_type and inst.status == "active"]
    if seat_type in EXCLUSIVE_SEATS and len(active) > 1:
        ids = ", ".join(i.instance_id for i in active)
        raise RelayError(f"multiple active {seat_type} instances (fail closed): {ids}")
    return active


def should_spawn(seat: str, corpus: Path) -> bool:
    """False when an active instance of an exclusive seat already exists."""
    seat_type = normalize_seat_type(seat)
    if seat_type not in EXCLUSIVE_SEATS:
        return True
    return not resolve(corpus, seat=seat_type)


def whoami(corpus: Path, instance_id: str | None = None) -> SeatInstance:
    ident = instance_id or os.environ.get("ZEO_INSTANCE_ID")
    if not ident:
        raise RelayError("ZEO_INSTANCE_ID is unset and --instance was not given")
    return load_instance(corpus, ident)


def send(
    corpus: Path,
    *,
    from_instance: str,
    to_instance: str,
    kind: str,
    body: str,
    conversation_id: str | None = None,
    reply_to: str | None = None,
    artifact_refs: list[str] | None = None,
    message_id: str | None = None,
    requires_ack: bool = True,
) -> RelayMessage:
    load_instance(corpus, from_instance)
    dest = load_instance(corpus, to_instance)
    if dest.status != "active":
        raise RelayError(f"destination {to_instance} is {dest.status}, not active")
    mid = message_id or new_message_id()
    existing_live = message_path(corpus, mid)
    existing_dead = message_path(corpus, mid, dead=True)
    if existing_live.is_file() or existing_dead.is_file():
        return load_message(corpus, mid)
    try:
        msg = RelayMessage(
            message_id=mid,
            conversation_id=conversation_id or f"conv_{uuid.uuid4().hex[:12]}",
            from_instance=from_instance,
            to_instance=to_instance,
            kind=kind,  # pydantic validates MessageKind
            created_at=utcnow(),
            reply_to=reply_to,
            requires_ack=requires_ack,
            artifact_refs=list(artifact_refs or []),
            body=body,
            state="queued",
        )
    except ValidationError as exc:
        raise RelayError(str(exc)) from exc
    save_message(corpus, msg)
    return msg


def receive(corpus: Path, instance_id: str) -> list[RelayMessage]:
    load_instance(corpus, instance_id)
    return [
        m
        for m in list_messages(corpus, include_dead=False)
        if m.to_instance == instance_id and m.state in {"queued", "delivered"}
    ]


def pending_outbound(corpus: Path) -> list[RelayMessage]:
    return [m for m in list_messages(corpus, include_dead=False) if m.state == "queued"]


def ack(corpus: Path, message_id: str) -> RelayMessage:
    msg = load_message(corpus, message_id)
    msg.state = "acked"
    msg.acked_at = utcnow()
    save_message(corpus, msg)
    return msg


def mark_delivered(corpus: Path, message_id: str) -> RelayMessage:
    msg = load_message(corpus, message_id)
    msg.state = "delivered"
    msg.delivered_at = utcnow()
    msg.delivery_attempts += 1
    save_message(corpus, msg)
    return msg


def mark_delivery_failed(corpus: Path, message_id: str, error: str) -> RelayMessage:
    msg = load_message(corpus, message_id)
    msg.delivery_attempts += 1
    msg.last_error = error
    if msg.delivery_attempts >= MAX_DELIVERY_ATTEMPTS:
        msg.state = "dead"
    save_message(corpus, msg)
    return msg


def status_payload(corpus: Path) -> dict[str, Any]:
    instances = [i.model_dump(mode="json") for i in list_instances(corpus)]
    messages = list_messages(corpus, include_dead=True)
    return {
        "instances": instances,
        "queued": sum(1 for m in messages if m.state == "queued"),
        "delivered": sum(1 for m in messages if m.state == "delivered"),
        "acked": sum(1 for m in messages if m.state == "acked"),
        "dead": sum(1 for m in messages if m.state == "dead"),
    }


def file_verdict(corpus: Path, *, dest_rel: str, body: str) -> Path:
    """Write a Sparring verdict only under ruling/-shaped paths."""
    rel = dest_rel.replace("\\", "/").lstrip("/")
    if ".." in Path(rel).parts:
        raise RelayError("verdict path must not contain ..")
    if not rel.startswith("ruling/") or not rel.endswith(".md"):
        raise RelayError("verdict path must be ruling/<name>.md")
    dest = Path(corpus) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(dest, body if body.endswith("\n") else body + "\n")
    return dest
