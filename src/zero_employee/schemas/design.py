"""Design frontmatter grading — RULING-286's fifth genre.

Pre-decision approach comparison: a stream or Master weighing 2+ real approaches
BEFORE committing to one, sitting between `intake` (operator-only, no evidence) and
`charter` (already-decided, binds work). Modeled directly on `schemas/intake.py`'s
own pattern — this genre is `intake`'s own successful shape, one layer over.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from ..core import ERROR, WARN, Finding
from .common import DESIGN_STATUS_ENUM


class DesignFrontmatter(BaseModel):
    """Read-side design frontmatter (loose)."""

    model_config = ConfigDict(extra="ignore")

    genre: Any = None
    design: Any = None
    sow: Any = None  # legacy/alias identity field, same tolerance charter.py extends
    project: Any = None
    created: Any = None
    updated: Any = None
    status: Any = None
    decided_into: Any = None  # RULING-286 s2 closure: the charter/ruling this became

    @field_validator("status", mode="before")
    @classmethod
    def _status_ok(cls, value: object) -> object:
        if value is None or value == "":
            return value
        st = str(value).strip().upper()
        if st not in DESIGN_STATUS_ENUM:
            raise ValueError(
                f"status '{value}' is not one of {sorted(DESIGN_STATUS_ENUM)} "
                "(RULING-286: a design filing uses OPEN|DECIDED|SUPERSEDED, not the SOW status enum)"
            )
        return st


def grade_design(fm: dict, *, body: str = "", commit_mode: bool = False) -> list[Finding]:
    """Grade design frontmatter + minimal body semantics (RULING-286 s2).

    QUESTION and at least 2 APPROACHES entries are mandatory — a design comparing
    fewer than two approaches is not comparing anything, it is a charter that has not
    been relabeled. NOT DECIDING HERE is mandatory even when empty (the same
    load-bearing role intake's own NOT THIS line carries — the must-not-decide fence
    institutionalised at filing time, not left to memory).
    """
    out: list[Finding] = []
    try:
        DesignFrontmatter.model_validate(fm)
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            for error in exc.errors():
                msg = error.get("msg", "invalid").replace("Value error, ", "")
                out.append(Finding(ERROR, "design-status-enum", msg))
            return out
        raise

    did = str(fm.get("design") or fm.get("sow") or "").strip()
    if not did:
        out.append(Finding(ERROR, "design-id", "design id (design: or sow:) is required"))

    st = str(fm.get("status") or "").strip().upper()
    if not st:
        sev = ERROR if commit_mode else WARN
        out.append(Finding(sev, "design-status", "status is required"))

    if st == "DECIDED":
        di = fm.get("decided_into")
        if not di or not str(di).strip():
            out.append(
                Finding(
                    ERROR,
                    "design-undecided-successor",
                    f"design {did or '?'} is DECIDED with no decided_into: naming the charter "
                    "or ruling it became. Fix: set decided_into: <path or id>",
                )
            )
    if st == "SUPERSEDED":
        di = fm.get("decided_into")
        if not di or not str(di).strip():
            out.append(
                Finding(
                    WARN,
                    "design-nosuccessor",
                    f"design {did or '?'} is SUPERSEDED with no decided_into naming what "
                    "replaced it. Fix: set decided_into: <successor id>",
                )
            )

    sections = _parse_design_sections(body)
    question = (sections.get("QUESTION") or "").strip()
    if not question:
        out.append(Finding(ERROR, "design-no-question", "QUESTION section is required"))

    approaches = sections.get("_APPROACHES", [])
    if len(approaches) < 2:
        out.append(
            Finding(
                ERROR,
                "design-fewer-than-two-approaches",
                f"{len(approaches)} approach(es) found — a design compares 2 or more "
                "options before a decision; fewer than two is a charter that has not "
                "been relabeled, not a real comparison",
            )
        )
    for i, a in enumerate(approaches):
        if not (a.get("evidence") or "").strip():
            out.append(
                Finding(
                    WARN,
                    "design-approach-no-evidence",
                    f"approach {i + 1} ({a.get('name') or 'unnamed'}) states no evidence — "
                    "RULING-286 s2 requires evidence per approach, not an unverified lean",
                )
            )

    not_deciding = sections.get("NOT DECIDING HERE")
    if not_deciding is None:
        out.append(
            Finding(
                ERROR,
                "design-no-not-deciding-line",
                "NOT DECIDING HERE section is mandatory, even when its body is empty/'none' — "
                "the must-not-decide fence institutionalised at filing time (mirrors intake's "
                "own NOT THIS: doctrine)",
            )
        )

    return out


def _parse_design_sections(body: str) -> dict[str, Any]:
    """Parse QUESTION:/APPROACHES:/NOT DECIDING HERE: style sections.

    APPROACHES is a repeated block, not a single free-text field — each entry starts
    with a "- name:" line (matching the ruling's own YAML-ish worked example) and
    accumulates "evidence:"/"tradeoff:" sub-lines until the next "- name:" or the
    next top-level header.
    """
    headers = ("QUESTION", "APPROACHES", "NOT DECIDING HERE")
    lines = (body or "").splitlines()
    current: str | None = None
    buckets: dict[str, list[str]] = {h: [] for h in headers}
    seen_headers: set[str] = set()
    approaches: list[dict[str, str]] = []
    cur_approach: dict[str, str] | None = None

    for line in lines:
        stripped = line.strip()
        matched = None
        for h in headers:
            if stripped.upper() == f"{h}:" or stripped.upper().startswith(f"{h}:"):
                matched = h
                break
        if matched:
            current = matched
            seen_headers.add(matched)
            if cur_approach is not None:
                approaches.append(cur_approach)
                cur_approach = None
            after = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
            if after and matched != "APPROACHES":
                buckets[matched].append(after)
            continue
        if current == "APPROACHES":
            if stripped.startswith("- name:") or stripped.startswith("-name:"):
                if cur_approach is not None:
                    approaches.append(cur_approach)
                cur_approach = {"name": stripped.split(":", 1)[1].strip()}
                continue
            if cur_approach is not None:
                for key in ("evidence", "tradeoff"):
                    if stripped.lower().startswith(f"{key}:"):
                        cur_approach[key] = stripped.split(":", 1)[1].strip()
                        break
            continue
        if current:
            buckets[current].append(line.rstrip())

    if cur_approach is not None:
        approaches.append(cur_approach)

    out: dict[str, Any] = {h: "\n".join(buckets[h]).strip() for h in headers if h != "APPROACHES"}
    out["_APPROACHES"] = approaches
    if "NOT DECIDING HERE" not in seen_headers:
        out["NOT DECIDING HERE"] = None
    return out
