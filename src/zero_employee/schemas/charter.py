"""Charter frontmatter grading."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from .common import CHARTER_STATUS_ENUM, normalize_status


class CharterFrontmatter(BaseModel):
    model_config = ConfigDict(extra="ignore")

    charter: Any = None
    sow: Any = None
    status: Any = None
    landing_commit: Any = None
    superseded_by: Any = None
    done_when: Any = None
    restaufwand: Any = None
    genre: Any = None

    @field_validator("status", mode="before")
    @classmethod
    def _status_ok(cls, value: object) -> object:
        if value is None or value == "":
            return value
        st = str(value).strip().upper()
        if st not in CHARTER_STATUS_ENUM:
            raise ValueError(
                f"status '{value}' is not one of {sorted(CHARTER_STATUS_ENUM)} "
                "(a charter uses the ruling-shaped vocabulary, not the SOW status enum)"
            )
        return value


def grade_charter(fm: dict, *, commit_mode: bool = False) -> list:
    from zero_employee.core import ERROR, WARN, Finding

    out: list = []
    cid = str(fm.get("charter") or fm.get("sow") or "?").strip()
    status = str(fm.get("status", "")).strip().upper()

    try:
        CharterFrontmatter.model_validate(fm)
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            for error in exc.errors():
                msg = error.get("msg", "invalid").replace("Value error, ", "")
                out.append(Finding(WARN, "charter-status-enum", f"charter {cid}: {msg}"))
        else:
            raise

    if status == "ACTIVE":
        lc = fm.get("landing_commit")
        if not lc or not str(lc).strip():
            out.append(
                Finding(
                    ERROR,
                    "charter-unlanded",
                    f"charter {cid} is ACTIVE with an EMPTY landing_commit. Fix: set landing_commit: self (or the SHA)",
                )
            )
    if status == "SUPERSEDED":
        sb = fm.get("superseded_by")
        if not sb or not str(sb).strip():
            out.append(
                Finding(
                    WARN,
                    "charter-nosuccessor",
                    f"charter {cid} is SUPERSEDED with no superseded_by naming what replaced it. "
                    "Fix: set superseded_by: <successor id>",
                )
            )

    # Working fields for charter ACTIVE (mirrors check_working_fields).
    st = normalize_status(fm.get("status"))
    if st == "ACTIVE":
        sev = ERROR if commit_mode else WARN
        if not str(fm.get("done_when") or "").strip():
            out.append(
                Finding(
                    sev,
                    "working-no-done-when",
                    f"status: {fm.get('status')} (charter) carries no done_when: - doctrine "
                    "requires a runnable stopping predicate on any WORKING status. "
                    'Fix: add done_when: "<command> -> <verdict>"',
                )
            )
        if fm.get("restaufwand") is None or not str(fm.get("restaufwand")).strip():
            out.append(
                Finding(
                    sev,
                    "working-no-restaufwand",
                    f"status: {fm.get('status')} (charter) carries no restaufwand: - doctrine "
                    "requires a stated remaining-units figure. "
                    "Fix: add restaufwand: <integer>",
                )
            )

    return out
