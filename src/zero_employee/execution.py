"""Execution evidence seam: capability manifests and receipts, not a harness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from .schemas.execution_receipt import ExecutionReceipt, dump_canonical, load_receipt
from .schemas.executor import ExecutorCapabilities


class ExecutionEvidenceAdapter(Protocol):
    def probe(self) -> ExecutorCapabilities: ...

    def import_receipt(self, source: Path) -> ExecutionReceipt: ...


def iter_execution_receipts(root: Path) -> list[Path]:
    """JSON receipts beside the markdown corpus walk (not iter_sow_files)."""
    root = Path(root)
    found: list[Path] = []
    bases = [root / "executions", *sorted(root.glob("projects/*/executions"))]
    for base in bases:
        if base.is_dir():
            found.extend(p for p in sorted(base.rglob("*.execution.json")) if p.is_file())
    return found


def load_capabilities(data: dict) -> ExecutorCapabilities:
    return ExecutorCapabilities.model_validate(data)


def validate_receipt_path(path: Path) -> tuple[ExecutionReceipt | None, list[str]]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"{path}: cannot read JSON ({exc})"]
    try:
        receipt = load_receipt(raw)
    except ValidationError as exc:
        return None, [f"{path}: {err['msg']}" for err in exc.errors()]
    return receipt, []


def import_receipt_json(source: Path) -> ExecutionReceipt:
    """Load a receipt that already matches the governed envelope."""
    receipt, errors = validate_receipt_path(source)
    if receipt is None:
        raise ValueError("; ".join(errors))
    return receipt


def write_canonical_receipt(receipt: ExecutionReceipt, dest: Path) -> None:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(dump_canonical(receipt), encoding="utf-8")
