"""Learnings diary entry grading."""

from __future__ import annotations

import re
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

from .common import LEARNINGS_KINDS, sentence_count


class LearningsEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    date: Any = None
    stream: Any = None
    sow_ref: Any = None
    kind: Any = None
    genre: Any = None
    lesson: Any = None
    ground: Any = None

    @field_validator("kind", mode="before")
    @classmethod
    def _kind_ok(cls, value: object) -> object:
        if value is None or value == "":
            return value
        raw = str(value).strip().lower()
        if raw not in LEARNINGS_KINDS:
            raise ValueError(
                f"kind must be one of {sorted(LEARNINGS_KINDS)}. Fix: set kind: craft|gotcha|doctrine-candidate"
            )
        return value


_ENTRY_KEYS = {"date", "stream", "kind", "lesson", "ground", "genre", "sow-ref", "sow_ref"}


def _body_entries(text: str) -> list[dict]:
    """Parse learnings body as a YAML list of entries (skill shape)."""
    # Strip frontmatter if present.
    lines = text.splitlines()
    body = text
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                body = "\n".join(lines[i + 1 :])
                break
    body = body.strip()
    if not body:
        return []
    try:
        data = yaml.safe_load(body)
    except yaml.YAMLError:
        return []
    if isinstance(data, list):
        return [e for e in data if isinstance(e, dict)]
    if isinstance(data, dict) and _ENTRY_KEYS & set(data):
        return [data]
    return []


def _addressable_ground(ground: object) -> bool:
    text = str(ground or "").strip()
    if not text:
        return False
    # block-id, file:line, commit-ish, SOW-N, or path
    if re.search(r"\bSOW-\d+\b", text, re.I):
        return True
    if re.search(r"[A-Za-z0-9_./-]+\.(md|py|ts|tsx):\d+", text):
        return True
    if re.search(r"\b[0-9a-f]{7,40}\b", text):
        return True
    if re.search(r"\b[A-Z]{2,}[-_][A-Z0-9]+-\d+\b", text):
        return True
    # at least names an incident with some specificity
    return len(text) >= 20


def grade_learnings(fm: dict, *, text: str = "") -> list:
    from zero_employee.core import ERROR, HINT, WARN, Finding

    out: list = []
    entries = _body_entries(text)

    # Frontmatter-only learnings file (genre marker) with no entries yet.
    if not entries:
        out.append(
            Finding(
                HINT,
                "hint-learnings-empty",
                "learnings file has no diary entries in the body. "
                "Fix: append a YAML list item with date, stream, kind, lesson, ground "
                "(5 content lines max per the learnings-authoring skill)",
            )
        )
        return out

    for idx, entry in enumerate(entries):
        # Normalize sow-ref key
        if "sow-ref" in entry and "sow_ref" not in entry:
            entry = {**entry, "sow_ref": entry.get("sow-ref")}

        try:
            LearningsEntry.model_validate(entry)
        except Exception as exc:
            from pydantic import ValidationError

            if isinstance(exc, ValidationError):
                for error in exc.errors():
                    msg = error.get("msg", "invalid").replace("Value error, ", "")
                    out.append(
                        Finding(
                            ERROR,
                            "learnings-kind",
                            f"entry[{idx}]: {msg}",
                        )
                    )
            else:
                raise

        for required in ("date", "stream", "kind", "lesson", "ground"):
            # sow-ref is recommended but skill says "or a block-id, or a commit"
            if not str(entry.get(required) or entry.get(required.replace("_", "-")) or "").strip():
                out.append(
                    Finding(
                        ERROR,
                        "learnings-missing-field",
                        f"entry[{idx}] missing required field `{required}`. "
                        f"Fix: add {required}: <value> (learnings-authoring skill)",
                    )
                )

        lesson = str(entry.get("lesson") or "")
        if sentence_count(lesson) > 3:
            out.append(
                Finding(
                    HINT,
                    "hint-learnings-lesson-long",
                    f"entry[{idx}] lesson has >3 sentences. Fix: compress to 3 sentences max (diary friction-parity)",
                )
            )

        ground = entry.get("ground")
        if ground is not None and str(ground).strip() and not _addressable_ground(ground):
            out.append(
                Finding(
                    HINT,
                    "hint-learnings-ground-weak",
                    f"entry[{idx}] ground is present but not clearly addressable "
                    "(want block-id, file:line, commit, or SOW-N). "
                    "Fix: cite the incident so a distiller can count it",
                )
            )
        genre = str(entry.get("genre") or fm.get("genre") or "").strip().lower()
        if genre and genre != "learnings":
            out.append(
                Finding(
                    WARN,
                    "learnings-genre",
                    f"entry[{idx}] genre: {genre!r} should be 'learnings'. Fix: set genre: learnings",
                )
            )

    return out
