"""Git worktree lifecycle bound to the relay instance registry."""

from __future__ import annotations

import subprocess
from pathlib import Path

from . import relay as relay_mod
from .relay import RelayError, normalize_seat_type
from .schemas.relay import SeatKind


class WorkspaceError(RelayError):
    """Worktree create/list/retire failure."""


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def branch_name(seat: SeatKind, instance_id: str, round_id: str = "r1") -> str:
    return f"zeo/{seat}/{instance_id}/{round_id}"


def worktree_path(host_repo: Path, instance_id: str) -> Path:
    return Path(host_repo) / ".zeo" / "worktrees" / instance_id


def _head_sha(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def create(
    corpus: Path,
    *,
    seat: str,
    instance_id: str,
    host_repo: Path | None = None,
    stream: str | None = None,
    round_id: str = "r1",
    runtime: str = "codex",
) -> dict:
    host = Path(host_repo or Path.cwd()).resolve()
    if not (host / ".git").exists() and _git(host, "rev-parse", "--is-inside-work-tree", check=False).returncode != 0:
        raise WorkspaceError(f"{host} is not a git repository")
    seat_type = normalize_seat_type(seat)
    dest = worktree_path(host, instance_id)
    if dest.exists():
        raise WorkspaceError(f"worktree already exists: {dest}")
    for inst in relay_mod.list_instances(corpus):
        if inst.status == "active" and inst.worktree and Path(inst.worktree).resolve() == dest.resolve():
            if inst.write_authority != "none":
                raise WorkspaceError(f"active write-heavy instance {inst.instance_id} already owns {dest}")
    branch = branch_name(seat_type, instance_id, round_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = _git(host, "worktree", "add", "-b", branch, str(dest), check=False)
    if proc.returncode != 0:
        raise WorkspaceError(proc.stderr.strip() or proc.stdout.strip() or "git worktree add failed")
    base = _head_sha(host)
    inst = relay_mod.register(
        corpus,
        seat=seat_type,
        instance_id=instance_id,
        runtime=runtime,
        worktree=str(dest),
        branch=branch,
        repository=str(host),
        stream=stream,
        base_sha=base,
        write_authority="ruling-only" if seat_type == "sparring" else "workspace-write",
    )
    return {
        "instance": inst.model_dump(mode="json"),
        "worktree": str(dest),
        "branch": branch,
        "base_sha": base,
    }


def list_workspaces(corpus: Path) -> list[dict]:
    rows = []
    for inst in relay_mod.list_instances(corpus):
        rows.append(
            {
                "instance_id": inst.instance_id,
                "seat_type": inst.seat_type,
                "worktree": inst.worktree,
                "branch": inst.branch,
                "status": inst.status,
                "write_authority": inst.write_authority,
            }
        )
    return rows


def retire(corpus: Path, instance_id: str, *, remove_worktree: bool = True) -> dict:
    inst = relay_mod.load_instance(corpus, instance_id)
    removed = False
    if remove_worktree and inst.worktree and inst.repository:
        host = Path(inst.repository)
        proc = _git(host, "worktree", "remove", "--force", inst.worktree, check=False)
        removed = proc.returncode == 0
    retired = relay_mod.retire(corpus, instance_id)
    return {"instance": retired.model_dump(mode="json"), "worktree_removed": removed}


def trailer_lines(*, seat: str, instance_id: str, conversation_id: str | None = None) -> str:
    lines = [f"ZEO-Seat: {seat}", f"ZEO-Instance: {instance_id}"]
    if conversation_id:
        lines.append(f"ZEO-Conversation: {conversation_id}")
    return "\n".join(lines)


def commit_message_has_required_trailers(message: str) -> bool:
    import os

    seat = os.environ.get("ZEO_SEAT")
    instance = os.environ.get("ZEO_INSTANCE_ID")
    conversation = os.environ.get("ZEO_CONVERSATION")
    if not (seat or instance or conversation):
        return True
    if instance and f"ZEO-Instance: {instance}" not in message:
        return False
    if seat and f"ZEO-Seat: {seat}" not in message:
        return False
    if conversation and f"ZEO-Conversation: {conversation}" not in message:
        return False
    return True


def sparring_may_stage(rel_paths: list[str]) -> bool:
    import os

    if os.environ.get("ZEO_SEAT", "").lower() not in {"sparring", "zeo-sparring"}:
        return True
    for rel in rel_paths:
        posix = rel.replace("\\", "/")
        if posix.endswith(".md") and ("/ruling/" in f"/{posix}" or posix.startswith("ruling/")):
            continue
        if posix.startswith("executions/relay/"):
            continue
        return False
    return True
