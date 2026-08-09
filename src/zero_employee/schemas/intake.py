"""Lightweight intake grading — intent capture, not SOW machinery."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from ..core import ERROR, WARN, Finding

INTAKE_STATUSES = frozenset({"OPEN", "PROMOTED", "DUPLICATE", "REJECTED", "PARKED"})
INTAKE_STATUS_ALIASES = {
    "CHARTERED": "PROMOTED",
    "DECLINED": "REJECTED",
    "SUPERSEDED": "DUPLICATE",
}


def normalize_intake_status(value: object) -> str:
    raw = str(value or "").strip().upper()
    if not raw:
        return ""
    return INTAKE_STATUS_ALIASES.get(raw, raw)


class IntakeFrontmatter(BaseModel):
    """Read-side intake frontmatter (loose)."""

    model_config = ConfigDict(extra="ignore")

    genre: Any = None
    id: Any = None
    intake: Any = None
    created: Any = None
    updated: Any = None
    status: Any = None
    promoted_to: Any = None
    project_hint: Any = None
    stream_hint: Any = None
    project: Any = None  # legacy triage field

    @field_validator("status", mode="before")
    @classmethod
    def _status_ok(cls, value: object) -> object:
        if value is None or value == "":
            return value
        st = normalize_intake_status(value)
        if st not in INTAKE_STATUSES:
            raise ValueError(
                f"status '{value}' is not a valid intake status. "
                f"Must be one of {sorted(INTAKE_STATUSES)} "
                f"(aliases: CHARTERED→PROMOTED, DECLINED→REJECTED, SUPERSEDED→DUPLICATE)"
            )
        return st


def grade_intake(fm: dict, *, body: str = "", commit_mode: bool = False) -> list[Finding]:
    """Grade intake frontmatter + minimal body semantics.

    Only WHAT is mandatory in the body. Missing DONE WHEN is a soft WARN.
    """
    out: list[Finding] = []
    try:
        IntakeFrontmatter.model_validate(fm)
    except Exception as exc:
        out.append(Finding(ERROR, "intake-schema", str(exc)))
        return out

    genre = str(fm.get("genre") or "").strip().lower()
    if genre and genre != "intake":
        out.append(Finding(ERROR, "intake-genre", f"genre must be 'intake', got {genre!r}"))

    iid = str(fm.get("id") or fm.get("intake") or "").strip()
    if not iid:
        out.append(Finding(ERROR, "intake-id", "intake id (id: or intake:) is required"))

    st = normalize_intake_status(fm.get("status"))
    if not st:
        sev = ERROR if commit_mode else WARN
        out.append(Finding(sev, "intake-status", "status is required"))
    elif st not in INTAKE_STATUSES:
        out.append(
            Finding(
                ERROR,
                "intake-status",
                f"status '{fm.get('status')}' not in {sorted(INTAKE_STATUSES)}",
            )
        )

    sections = _parse_sections(body)
    what = (sections.get("WHAT") or "").strip()
    if not what:
        out.append(Finding(ERROR, "intake-what", "WHAT section is required"))
    done = (sections.get("DONE WHEN") or "").strip()
    if not done:
        out.append(
            Finding(
                WARN,
                "intake-done-when",
                "DONE WHEN is absent — promotion to SOW will be harder without a falsifiable criterion",
            )
        )
    return out


def _parse_sections(body: str) -> dict[str, str]:
    """Parse WHAT:/WHY:/DONE WHEN:/NOT THIS:/CONTEXT: style sections."""
    headers = ("WHAT", "WHY", "DONE WHEN", "NOT THIS", "CONTEXT")
    lines = (body or "").splitlines()
    current: str | None = None
    buckets: dict[str, list[str]] = {h: [] for h in headers}
    extra_key: str | None = None
    extras: dict[str, list[str]] = {}

    for line in lines:
        stripped = line.strip()
        matched = None
        for h in headers:
            if stripped.upper() == f"{h}:" or stripped.upper().startswith(f"{h}:"):
                matched = h
                break
        if matched:
            current = matched
            extra_key = None
            after = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
            if after:
                buckets[matched].append(after)
            continue
        # Arbitrary extra section headers: ALL CAPS WORD(S):
        if (
            stripped.endswith(":")
            and stripped[:-1]
            and stripped[:-1].replace(" ", "").isalpha()
            and stripped[:-1] == stripped[:-1].upper()
            and stripped[:-1] not in headers
        ):
            extra_key = stripped[:-1]
            current = None
            extras.setdefault(extra_key, [])
            continue
        if current:
            buckets[current].append(line.rstrip())
        elif extra_key:
            extras[extra_key].append(line.rstrip())

    out = {h: "\n".join(buckets[h]).strip() for h in headers}
    for k, v in extras.items():
        out[k] = "\n".join(v).strip()
    return out
