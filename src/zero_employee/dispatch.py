"""A5: git-backed exclusive ownership for unattended mutation.

A label, prompt, or seat name is not a lock. GitHub concurrency groups are not
organizational identity. Never uses bare `git push --force`.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .schemas.execution_receipt import ExecutionReceipt, ReceiptUsage, dump_canonical

LIVE = "live"
FAILED = "failed"
ABORTED = "aborted"
COMPLETED = "completed"
REFUSED = "refused"
CLEANED = "cleaned"


class DispatchError(Exception):
    """Operator-visible dispatch failure (duplicate lock, remote race, unauthorized cleanup)."""


def ownership_key(*, repository: str, branch: str | None = None, stream: str | None = None) -> str:
    if branch:
        return f"{repository}|branch:{branch}"
    if stream:
        return f"{repository}|stream:{stream}"
    raise DispatchError("ownership key requires repository + mutable branch, or repository + governed stream")


def _lock_dir(repo: Path) -> Path:
    return Path(repo) / "executions" / "dispatch" / "locks"


def _lock_path(repo: Path, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return _lock_dir(repo) / f"{digest}.lock.json"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def pin_head_sha(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def remote_branch_sha(repo: Path, branch: str, remote: str = "origin") -> str | None:
    proc = _git(repo, "ls-remote", remote, f"refs/heads/{branch}", check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return proc.stdout.split()[0]


def check_remote_advancement(repo: Path, branch: str, expected_sha: str, remote: str = "origin") -> None:
    actual = remote_branch_sha(repo, branch, remote)
    if actual is None:
        return
    if actual != expected_sha:
        raise DispatchError(f"remote {remote}/{branch} advanced: expected {expected_sha}, found {actual}")


def push_with_lease(repo: Path, branch: str, expected_sha: str, remote: str = "origin") -> None:
    """Lease rewrite only. Bare --force is refused by construction."""
    proc = _git(
        repo,
        "push",
        f"--force-with-lease={branch}:{expected_sha}",
        remote,
        branch,
        check=False,
    )
    if proc.returncode != 0:
        raise DispatchError(proc.stderr.strip() or proc.stdout.strip() or "force-with-lease failed")


def load_lock(repo: Path, key: str) -> dict | None:
    path = _lock_path(repo, key)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_lock(repo: Path, key: str, payload: dict) -> Path:
    path = _lock_path(repo, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _receipt_path(repo: Path, execution_id: str, suffix: str) -> Path:
    dest = Path(repo) / "executions" / f"{execution_id}.{suffix}.execution.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    return dest


def _write_receipt(repo: Path, receipt: ExecutionReceipt, suffix: str) -> Path:
    dest = _receipt_path(repo, receipt.execution_id, suffix)
    dest.write_text(dump_canonical(receipt), encoding="utf-8")
    return dest


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AcquireResult:
    acquired: bool
    lock: dict
    receipt_path: Path | None = None


def acquire(
    repo: Path,
    *,
    key: str,
    execution_id: str,
    branch: str,
    seat_type: str = "zeo-stream",
    seat_instance: str = "unattended",
    base_sha: str | None = None,
) -> AcquireResult:
    """Refuse duplicate live ownership; record refusal as a receipt."""
    repo = Path(repo)
    head = pin_head_sha(repo)
    base = base_sha or head
    existing = load_lock(repo, key)
    if existing and existing.get("status") == LIVE and existing.get("execution_id") != execution_id:
        receipt = ExecutionReceipt(
            execution_id=execution_id,
            conversation_id=None,
            seat_type=seat_type,
            seat_instance=seat_instance,
            runtime="zeo-dispatch",
            runtime_address=None,
            agent_provider="none",
            sandbox_kind="none",
            branch=branch,
            base_commit=base,
            started_at=_now(),
            ended_at=_now(),
            termination="aborted",
            completion_signal_seen=False,
            structured_result_valid=False,
            usage=ReceiptUsage(source="unknown"),
            warnings=[f"duplicate live ownership for key {key}; held by {existing.get('execution_id')}"],
        )
        path = _write_receipt(repo, receipt, "refusal")
        return AcquireResult(acquired=False, lock=existing, receipt_path=path)
    payload = {
        "key": key,
        "execution_id": execution_id,
        "branch": branch,
        "base_sha": base,
        "head_sha": head,
        "status": LIVE,
        "acquired_at": _now().isoformat(),
    }
    _write_lock(repo, key, payload)
    return AcquireResult(acquired=True, lock=payload)


def set_status(repo: Path, key: str, status: str) -> dict:
    lock = load_lock(repo, key)
    if lock is None:
        raise DispatchError(f"no lock for {key}")
    lock["status"] = status
    lock["updated_at"] = _now().isoformat()
    _write_lock(repo, key, lock)
    return lock


def cleanup(repo: Path, key: str, *, authorize: bool = False) -> dict:
    """Preserve failed/aborted state unless a separately authorized cleanup applies."""
    lock = load_lock(repo, key)
    if lock is None:
        raise DispatchError(f"no lock for {key}")
    if lock.get("status") in (FAILED, ABORTED, REFUSED) and not authorize:
        raise DispatchError(
            f"lock {key} status {lock.get('status')} preserved for inspection; pass authorize=True to clean"
        )
    lock["status"] = CLEANED
    lock["updated_at"] = _now().isoformat()
    _write_lock(repo, key, lock)
    return lock
