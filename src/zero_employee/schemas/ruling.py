"""Ruling frontmatter grading."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class RulingFrontmatter(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ruling: Any = None
    title: Any = None
    authority: Any = None
    scope: Any = None
    status: Any = None
    supersedes: Any = None
    superseded_by: Any = None
    requested_by: Any = None
    landing_commit: Any = None
    binds: Any = None
    genre: Any = None
    conformance: Any = None
    created: Any = None
    updated: Any = None


def grade_ruling(
    fm: dict,
    *,
    raw_text: str | None = None,
    commit_mode: bool = False,
    nnn: str | int | None = None,
) -> list:
    """Mirror historical check_ruling + HINT for conformance."""
    from zero_employee.core import ERROR, HINT, WARN, Finding, ruling_id_from_bytes

    out: list = []
    # Validate shape (extra ignored); failures are soft — rulings vary widely.
    try:
        RulingFrontmatter.model_validate(fm)
    except Exception:
        pass

    status = str(fm.get("status", "")).strip().upper()
    if nnn is None:
        nnn = ruling_id_from_bytes(raw_text) if raw_text else None
        if nnn is None:
            _r = fm.get("ruling")
            nnn = str(_r).strip() if _r else "?"

    _in_force = status.startswith("ACTIVE") or status.startswith("AMENDED")
    if _in_force:
        lc = fm.get("landing_commit")
        if not lc or not str(lc).strip():
            out.append(
                Finding(
                    ERROR,
                    "ruling-unlanded",
                    f"RULING-{nnn} is {status} with an EMPTY landing_commit - a ruling is not "
                    "in force until it has landed. Fix: set landing_commit: self (or the SHA)",
                )
            )
    if status.startswith("SUPERSEDED"):
        sb = fm.get("superseded_by")
        if not sb or not str(sb).strip():
            out.append(
                Finding(
                    ERROR,
                    "ruling-nosuccessor",
                    f"RULING-{nnn} is SUPERSEDED with no superseded_by - chain unwalkable. "
                    "Fix: set superseded_by: <new NNN>",
                )
            )
    if not str(fm.get("genre", "")).strip():
        out.append(
            Finding(
                WARN,
                "ruling-genre-missing",
                f"RULING-{nnn} has no explicit genre: ruling - classified by filename shape "
                "(correct and sufficient; classification lands in the POINTER artifact, "
                "never by editing this landed file - doctrine)",
            )
        )

    if commit_mode and str(fm.get("scope", "")).strip().lower() == "org" and nnn not in (None, "?"):
        try:
            nnn_int = int(nnn)
        except (TypeError, ValueError):
            nnn_int = None
        if nnn_int is not None and nnn_int < 200:
            out.append(
                Finding(
                    ERROR,
                    "ruling-below-org-band",
                    f"RULING-{nnn} declares scope: org and is numbered below 200 - doctrine "
                    "reserves 200+ for org-scope rulings filed from that ruling forward. "
                    'Fix: use `sow-lint --mint ruling --words "..."` for the next free id',
                )
            )

    # HINT: org + all-streams without a behavioral conformance predicate.
    scope = str(fm.get("scope", "")).strip().lower()
    binds = fm.get("binds") or []
    if isinstance(binds, str):
        binds_list = [binds]
    elif isinstance(binds, list):
        binds_list = [str(b) for b in binds]
    else:
        binds_list = []
    binds_flat = " ".join(binds_list).lower()
    if _in_force and (scope == "org" or scope.startswith("program:")):
        if "all-streams" in binds_flat:
            conf = str(fm.get("conformance") or "").strip()
            if not conf:
                out.append(
                    Finding(
                        HINT,
                        "hint-conformance-absent",
                        f"RULING-{nnn} binds all-streams with no conformance: field "
                        "(defaults to acknowledged). Fix: set conformance: acknowledged "
                        'or a behavioral predicate like "latest SOW carries a RESTING status"',
                    )
                )
            elif conf.lower() == "acknowledged":
                out.append(
                    Finding(
                        HINT,
                        "hint-conformance-floor",
                        f"RULING-{nnn} uses conformance: acknowledged (receipt floor). "
                        "Prefer a behavioral predicate on the stream's next filing when one exists",
                    )
                )

    return out
