"""SOW frontmatter grading via Pydantic + keystone rules."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .common import (
    LIFECYCLES,
    STATUS_ENUM,
    STATUS_WORKING,
    normalize_status,
    presence_check_smell,
)


class LedgerEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    claim: str | None = None
    state: str | None = None
    commit: str | None = None
    check: str | None = None
    gate: str | None = None


class SowFrontmatter(BaseModel):
    """Read-side SOW model. Extra fields ignored so the live corpus stays gradeable."""

    model_config = ConfigDict(extra="ignore")

    sow: Any = None
    n: Any = None
    rev: Any = None
    schema_rev: Any = None
    status: Any = None
    lifecycle: Any = None
    ledger: list[Any] | None = None
    done_when: Any = None
    restaufwand: Any = None
    project: Any = None
    sow_repo: Any = None
    work_repo: Any = None
    created: Any = None
    updated: Any = None

    @field_validator("status", mode="before")
    @classmethod
    def _status_ok(cls, value: object) -> object:
        if value is None or value == "":
            return value
        st = normalize_status(value)
        if st in STATUS_ENUM or str(value).strip().upper().startswith("SUPERSEDED"):
            return value
        raise ValueError(
            f"'{value}' is not a valid SOW status. Must be one of {sorted(STATUS_ENUM)}. "
            f"Fix: set status to one of {sorted(STATUS_ENUM)}"
        )

    @field_validator("lifecycle", mode="before")
    @classmethod
    def _lifecycle_ok(cls, value: object) -> object:
        if value is None or value == "":
            return value
        raw = str(value).strip().upper()
        if raw in LIFECYCLES:
            return value
        raise ValueError(
            f"'{value}' is not a lifecycle genre. Must be one of {list(LIFECYCLES)}. "
            f"Fix: set lifecycle to one of {list(LIFECYCLES)} (document genre, not work status)"
        )


def keystone_messages(fm: dict) -> list[str]:
    """v0 keystone: SHIPPED ledger rows need commit + non-empty check.

    FINDING is graded the same way (skill: verified observation still needs commit+check).
    """
    findings: list[str] = []
    ledger = fm.get("ledger")
    if ledger is None:
        return []
    if not isinstance(ledger, list):
        return ["ledger: is present but not a list"]
    for idx, entry in enumerate(ledger):
        if not isinstance(entry, dict):
            findings.append(f"ledger[{idx}] is not a mapping")
            continue
        state = str(entry.get("state", "")).strip().upper()
        # Keep SHIPPED message text identical for v0 tests; FINDING uses its own label.
        if state == "SHIPPED":
            claim = entry.get("claim", f"<entry {idx}>")
            commit = entry.get("commit")
            if not commit or not str(commit).strip():
                findings.append(f"SHIPPED claim '{claim}' has no commit")
            check = entry.get("check")
            if check is None or not str(check).strip():
                findings.append(
                    f"SHIPPED claim '{claim}' has an EMPTY check "
                    "(the SEAM failure — needs a runnable check or 'none — <reason>')"
                )
        elif state == "FINDING":
            claim = entry.get("claim", f"<entry {idx}>")
            commit = entry.get("commit")
            if not commit or not str(commit).strip():
                findings.append(f"FINDING claim '{claim}' has no commit")
            check = entry.get("check")
            if check is None or not str(check).strip():
                findings.append(
                    f"FINDING claim '{claim}' has an EMPTY check "
                    "(needs a runnable check or 'none — <reason>')"
                )
    return findings


def grade_sow(
    fm: dict,
    *,
    commit_mode: bool = False,
    path_canonical: bool | None = None,
    project_known: bool | None = None,
) -> list:
    """Produce Findings for a SOW frontmatter mapping."""
    from zero_employee.core import ERROR, HINT, WARN, Finding

    out: list = []

    # Status enum (era-aware: ERROR on canonical project, WARN pre-migration).
    st_raw = fm.get("status")
    if st_raw:
        st = normalize_status(st_raw)
        if st not in STATUS_ENUM and not str(st_raw).strip().upper().startswith("SUPERSEDED"):
            if project_known:
                out.append(
                    Finding(
                        ERROR,
                        "status-enum",
                        f"status: '{st_raw}' is not a valid SOW status. Must be one of "
                        f"{sorted(STATUS_ENUM)}. Fix: set status to a value from the enum",
                    )
                )
            elif project_known is False:
                out.append(
                    Finding(
                        WARN,
                        "status-enum-premigration",
                        f"status: '{st_raw}' not in enum (pre-schema project — backfill on migration)",
                    )
                )
            else:
                out.append(
                    Finding(
                        ERROR,
                        "status-enum",
                        f"status: '{st_raw}' is not a valid SOW status. Must be one of "
                        f"{sorted(STATUS_ENUM)}. Fix: set status to a value from the enum",
                    )
                )

    # Lifecycle — previously ungraded; WARN so existing corpus is not failed.
    life = fm.get("lifecycle")
    if life not in (None, ""):
        raw = str(life).strip().upper()
        if raw not in LIFECYCLES:
            out.append(
                Finding(
                    WARN,
                    "lifecycle-enum",
                    f"lifecycle: '{life}' is not a document genre. Must be one of {list(LIFECYCLES)}. "
                    f"Fix: set lifecycle to one of {list(LIFECYCLES)} (not a work status)",
                )
            )

    for msg in keystone_messages(fm):
        out.append(Finding(ERROR, "keystone", msg))

    # Working fields (doctrine) — same severity policy as check_working_fields.
    st = normalize_status(fm.get("status"))
    if st in STATUS_WORKING:
        sev = ERROR if commit_mode else WARN
        if not str(fm.get("done_when") or "").strip():
            out.append(
                Finding(
                    sev,
                    "working-no-done-when",
                    f"status: {fm.get('status')} (sow) carries no done_when: - doctrine "
                    "requires a runnable stopping predicate on any WORKING status. "
                    'Fix: add done_when: "npm test -> 0 failures" (command + expected verdict)',
                )
            )
        if fm.get("restaufwand") is None or not str(fm.get("restaufwand")).strip():
            out.append(
                Finding(
                    sev,
                    "working-no-restaufwand",
                    f"status: {fm.get('status')} (sow) carries no restaufwand: - doctrine "
                    "requires a stated remaining-units figure. "
                    "Fix: add restaufwand: <integer> in your own unit",
                )
            )

    # HINT catalog
    ledger = fm.get("ledger")
    if isinstance(ledger, list):
        for idx, entry in enumerate(ledger):
            if not isinstance(entry, dict):
                continue
            state = str(entry.get("state", "")).strip().upper()
            if state not in {"SHIPPED", "FINDING"}:
                continue
            check = entry.get("check")
            if presence_check_smell(check):
                claim = entry.get("claim", f"<entry {idx}>")
                out.append(
                    Finding(
                        HINT,
                        "hint-presence-check",
                        f"ledger claim '{claim}' check looks like a presence proof "
                        f"(import/ls/test -f), not behavior. Fix: replace with a gate/"
                        f"behavioral assertion, or use check: \"none — <reason>\" for taste claims. "
                        f"Got: {check!r}",
                    )
                )
            if check and not entry.get("gate") and not str(check).lower().startswith("none"):
                claim = entry.get("claim", f"<entry {idx}>")
                out.append(
                    Finding(
                        HINT,
                        "hint-missing-gate",
                        f"ledger claim '{claim}' has a check but no gate: naming the contract. "
                        'Fix: add gate: "make verify" (or the contract this check satisfied)',
                    )
                )

    if path_canonical is False:
        out.append(
            Finding(
                HINT,
                "hint-noncanonical-name",
                "filename is not <stream>-SOW-<n>-<slug>.md. "
                "Fix: run `sow-lint --mint sow <stream> --words \"...\"` for new filings, "
                "or `sow-lint --promote <stream-dir>` to rename legacy files",
            )
        )

    return out
