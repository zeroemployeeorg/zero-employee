"""Shared enums and Finding helpers for genre schemas."""

from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

# Imported lazily-safe constants — duplicated from historical core._STATUS_ENUM so
# schemas can load without circular imports. core.py re-exports STATUS_ENUM from here.
STATUS_ENUM = frozenset(
    {
        "DRAFT",
        "DESIGN",
        "PROGRESS",
        "RULING-REQUESTED",
        "HELD",
        "BLOCKED",
        "SHIPPED",
        "FINDING",
        "CLOSEOUT",
        "HANDOVER",
        "SUPERSEDED",
        "VOIDED",
        "STALE",
    }
)

STATUS_WORKING = frozenset({"DRAFT", "DESIGN", "PROGRESS", "RULING-REQUESTED"})
STATUS_RESTING = STATUS_ENUM - STATUS_WORKING

LIFECYCLES = (
    "DESIGN-MEMO",
    "HANDOVER",
    "SELF-CORRECTION",
    "ESCALATION",
    "DECISION-RECORD",
    "CLOSEOUT-RECORD",
    "RECON",
)

CHARTER_STATUS_ENUM = frozenset({"ACTIVE", "SUPERSEDED", "DONE", "VOIDED"})
RULING_STATUS_PREFIXES = ("ACTIVE", "AMENDED", "SUPERSEDED", "VOIDED")
LEARNINGS_KINDS = frozenset({"craft", "gotcha", "doctrine-candidate"})

# RULING-268 s1: open_questions[].status is exactly two values, no third state, no free
# text — the ruling is explicit that a looser shape is not a permitted simplification.
OPEN_QUESTION_STATUSES = frozenset({"OPEN", "RESOLVED"})

# Presence-check smell: runnable but proves import/existence, not behavior.
_PRESENCE_CHECK_RE = re.compile(
    r"""(?ix)
    ^\s*(?:python\s+-c\s+['\"].*\bimport\b
        |python3?\s+-c\s+['\"].*\bimport\b
        |(?:npx\s+)?tsx?\s+-e\s+['\"].*\bimport\b
        |\bls\b
        |\btest\s+-f\b
        |\btest\s+-d\b
        |\b\[+\s+-f\b
        |\bimport\s+\w+)
    """
)


def normalize_status(value: object) -> str:
    raw = str(value or "").strip().upper()
    return raw.split("-SEE")[0].split("-AMENDED")[0].strip()


def findings_from_validation_error(
    exc: ValidationError,
    *,
    default_code: str = "schema",
    severity: str = "ERROR",
) -> list:
    from zero_employee.core import Finding

    out = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", ()) if part != "__root__")
        msg = error.get("msg", "invalid")
        code = default_code
        if loc == "status" or loc.endswith(".status"):
            code = "status-enum"
        elif loc == "lifecycle" or loc.endswith(".lifecycle"):
            code = "lifecycle-enum"
        out.append(
            Finding(
                severity,
                code,
                f"{loc}: {msg}" if loc else msg,
            )
        )
    return out


def presence_check_smell(check: object) -> bool:
    text = str(check or "").strip()
    if not text or text.lower().startswith("none"):
        return False
    return bool(_PRESENCE_CHECK_RE.search(text))


def sentence_count(text: str) -> int:
    parts = re.split(r"[.!?]+", str(text or "").strip())
    return len([p for p in parts if p.strip()])


def as_mapping(value: Any) -> dict | None:
    return value if isinstance(value, dict) else None
