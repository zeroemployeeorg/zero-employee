"""Intake authoring: frictionless capture; grounded promote into SOWs.

Intake captures intent before identity is known.
SOW governs work after identity is known.
Coding agents own investigation; ZEO owns evidence validation and governance syntax.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import pathlib
import re
import subprocess
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .core import _exclusive_create, extract_frontmatter, words_to_slug
from .migrate import atomic_replace
from .schemas.intake import (
    INTAKE_STATUSES,
    _parse_sections,
    grade_intake,
    normalize_intake_status,
)
from .sow_authoring import create_sow, split_frontmatter_body

SECTION_HEADERS = ("WHAT", "WHY", "DONE WHEN", "NOT THIS", "CONTEXT")

EDITOR_TEMPLATE = """WHAT:

WHY:

DONE WHEN:

NOT THIS:

CONTEXT:
"""

PROPOSAL_SCHEMA_HINT = {
    "type": "object",
    "required": ["observations", "implementation", "repo_head"],
    "properties": {
        "summary": {"type": "string"},
        "repo_head": {"type": "string"},
        "worktree_fingerprint": {"type": "string"},
        "observations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["fact", "evidence"],
                "properties": {
                    "fact": {"type": "string"},
                    "evidence": {
                        "type": "object",
                        "required": ["path", "line_start", "line_end"],
                        "properties": {
                            "path": {"type": "string"},
                            "line_start": {"type": "integer"},
                            "line_end": {"type": "integer"},
                        },
                    },
                },
            },
        },
        "interpretations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "based_on": {"type": "array", "items": {"type": "integer"}},
                },
            },
        },
        "implementation": {
            "type": "object",
            "required": ["problem", "invariant", "approach", "done_when"],
            "properties": {
                "problem": {"type": "string"},
                "invariant": {"type": "string"},
                "approach": {"type": "array", "items": {"type": "string"}},
                "files_expected_to_change": {"type": "array", "items": {"type": "string"}},
                "non_goals": {"type": "array", "items": {"type": "string"}},
                "done_when": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"enum": ["command", "inspection"]},
                            "command": {"type": "string"},
                            "expect": {"type": "string"},
                            "criterion": {"type": "string"},
                        },
                    },
                },
            },
        },
        "destination": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "stream": {"type": "string"},
                "title": {"type": "string"},
            },
        },
    },
}


class IntakeWriteFrontmatter(BaseModel):
    """ZEO-owned intake frontmatter — deliberately weak."""

    model_config = ConfigDict(extra="allow")

    genre: Literal["intake"] = "intake"
    id: str
    intake: str
    created: _dt.date
    updated: _dt.date
    status: Literal["OPEN", "PROMOTED", "DUPLICATE", "REJECTED", "PARKED"] = "OPEN"
    promoted_to: str | None = None
    project_hint: str | None = None
    stream_hint: str | None = None
    project: str | None = None  # legacy triage display

    @field_validator("status", mode="before")
    @classmethod
    def _status(cls, value: object) -> object:
        if value is None or value == "":
            return "OPEN"
        st = normalize_intake_status(value)
        if st not in INTAKE_STATUSES:
            raise ValueError(f"status must be one of {sorted(INTAKE_STATUSES)}")
        return st


class IntakeCreateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    id: str
    status: str
    checks: list[str] = Field(default_factory=list)


class PromoteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intake_path: str
    sow_path: str
    project: str
    stream: str
    n: int
    checks: list[str] = Field(default_factory=list)


# ── paths / ids ──────────────────────────────────────────────────────


def intake_dir(root: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(root).resolve() / "intake"


def proposals_dir(root: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(root).resolve() / ".zeo" / "intake-proposals"


def ensure_intake_dir(root: pathlib.Path) -> pathlib.Path:
    d = intake_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    return d


def intake_id_from_title(title: str, *, today: _dt.date | None = None) -> str:
    today = today or _dt.date.today()
    slug = words_to_slug(title, max_words=8, max_len=64)
    return f"{today.isoformat()}-{slug}"


def canonical_intake_filename(intake_id: str) -> str:
    return f"{intake_id}.md"


def resolve_intake_path(root: pathlib.Path, ref: str) -> pathlib.Path:
    """Resolve FILE path or 'latest' token to an intake markdown path."""
    root = pathlib.Path(root).resolve()
    if ref == "latest":
        path = find_latest_intake(root, open_only=True) or find_latest_intake(root, open_only=False)
        if path is None:
            raise FileNotFoundError("no intake files found")
        return path
    p = pathlib.Path(ref)
    if not p.is_absolute():
        cand = root / p
        if cand.is_file():
            return cand.resolve()
        cand2 = intake_dir(root) / p.name
        if cand2.is_file():
            return cand2.resolve()
        if not p.suffix:
            cand3 = intake_dir(root) / f"{p.name}.md"
            if cand3.is_file():
                return cand3.resolve()
    if p.is_file():
        return p.resolve()
    raise FileNotFoundError(f"intake not found: {ref}")


def find_latest_intake(root: pathlib.Path, *, open_only: bool = False) -> pathlib.Path | None:
    rows = list_intakes(root)
    if open_only:
        rows = [r for r in rows if r["status"] == "OPEN"]
    if not rows:
        return None
    rows.sort(key=lambda r: (r["created"], r["mtime"]), reverse=True)
    return pathlib.Path(rows[0]["path"])


# ── render / parse ───────────────────────────────────────────────────


def parse_intake_sections(body: str) -> dict[str, str]:
    return _parse_sections(body)


def render_intake_body(
    *,
    what: str = "",
    why: str = "",
    done_when: str = "",
    not_this: str | list[str] = "",
    context: str | list[str] = "",
    extra_sections: dict[str, str] | None = None,
) -> str:
    def _block(val: str | list[str]) -> str:
        if isinstance(val, list):
            lines = [str(x).strip() for x in val if str(x).strip()]
            return "\n".join(f"- {x}" if not x.startswith("-") else x for x in lines)
        return str(val or "").strip()

    parts = [
        f"WHAT:\n{_block(what)}\n",
        f"WHY:\n{_block(why)}\n",
        f"DONE WHEN:\n{_block(done_when)}\n",
        f"NOT THIS:\n{_block(not_this)}\n",
        f"CONTEXT:\n{_block(context)}\n",
    ]
    if extra_sections:
        for key, val in extra_sections.items():
            if key.upper() in SECTION_HEADERS:
                continue
            parts.append(f"{key}:\n{_block(val)}\n")
    text = "\n".join(parts).rstrip() + "\n"
    return text


def render_intake(frontmatter: IntakeWriteFrontmatter | dict, body: str) -> bytes:
    if isinstance(frontmatter, IntakeWriteFrontmatter):
        values = frontmatter.model_dump(mode="json", exclude_none=True)
    else:
        values = dict(frontmatter)
        for key in ("created", "updated"):
            if isinstance(values.get(key), _dt.date):
                values[key] = values[key].isoformat()

    order = [
        "genre",
        "id",
        "intake",
        "created",
        "updated",
        "status",
        "promoted_to",
        "project_hint",
        "stream_hint",
        "project",
    ]
    ordered: dict[str, Any] = {}
    for key in order:
        if key in values and values[key] is not None:
            ordered[key] = values[key]
    for key in sorted(k for k in values if k not in ordered and values[k] is not None):
        ordered[key] = values[key]

    yaml_fragment = yaml.safe_dump(
        ordered,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).rstrip()
    body_text = body if body.endswith("\n") or body == "" else body + "\n"
    return f"---\n{yaml_fragment}\n---\n\n{body_text}".encode("utf-8")


def load_intake(path: pathlib.Path) -> tuple[dict, str]:
    text = pathlib.Path(path).read_text(encoding="utf-8")
    fm, body = split_frontmatter_body(text)
    if fm == "MALFORMED":
        raise ValueError("frontmatter is not valid YAML")
    if not isinstance(fm, dict):
        raise ValueError("frontmatter missing or malformed")
    # Normalize status alias in-memory for callers.
    if "status" in fm:
        fm = dict(fm)
        fm["status"] = normalize_intake_status(fm.get("status")) or fm.get("status")
    return fm, body


def intake_identity(fm: dict, path: pathlib.Path) -> str:
    return str(fm.get("id") or fm.get("intake") or path.stem).strip()


# ── create ───────────────────────────────────────────────────────────


def create_intake(
    root: pathlib.Path,
    *,
    title: str | None = None,
    what: str | None = None,
    why: str | None = None,
    done_when: str | None = None,
    not_this: str | list[str] | None = None,
    context: str | list[str] | None = None,
    raw_body: str | None = None,
    project_hint: str | None = None,
    stream_hint: str | None = None,
    today: _dt.date | None = None,
) -> tuple[IntakeCreateResult | None, str]:
    """Create a lightweight intake. Returns (result, error)."""
    root = pathlib.Path(root).resolve()
    today = today or _dt.date.today()
    ensure_intake_dir(root)

    sections: dict[str, str] = {}
    extra: dict[str, str] = {}

    if raw_body is not None:
        parsed = parse_intake_sections(raw_body)
        if any(parsed.get(h) for h in SECTION_HEADERS):
            sections = {h: parsed.get(h, "") for h in SECTION_HEADERS}
            for k, v in parsed.items():
                if k not in SECTION_HEADERS and v:
                    extra[k] = v
        else:
            sections = {"WHAT": raw_body.strip(), "WHY": "", "DONE WHEN": "", "NOT THIS": "", "CONTEXT": ""}

    if what is not None:
        sections["WHAT"] = what
    if why is not None:
        sections["WHY"] = why
    if done_when is not None:
        sections["DONE WHEN"] = done_when
    if not_this is not None:
        sections["NOT THIS"] = "\n".join(not_this) if isinstance(not_this, list) else str(not_this)
    if context is not None:
        sections["CONTEXT"] = "\n".join(context) if isinstance(context, list) else str(context)

    what_text = (sections.get("WHAT") or "").strip()
    if not what_text and title:
        what_text = title.strip()
        sections["WHAT"] = what_text
    if not what_text:
        return None, "WHAT is required (pass --what, --title, --spec, or body with WHAT:)"

    title_for_id = (title or what_text).strip()
    base_id = intake_id_from_title(title_for_id, today=today)
    dest_dir = intake_dir(root)

    # Collision: append -2, -3, ...
    intake_id = base_id
    dest = dest_dir / canonical_intake_filename(intake_id)
    n = 2
    while dest.exists():
        intake_id = f"{base_id}-{n}"
        dest = dest_dir / canonical_intake_filename(intake_id)
        n += 1

    fm = IntakeWriteFrontmatter(
        id=intake_id,
        intake=intake_id,
        created=today,
        updated=today,
        status="OPEN",
        project_hint=project_hint,
        stream_hint=stream_hint,
        project=project_hint,
    )
    body = render_intake_body(
        what=sections.get("WHAT", ""),
        why=sections.get("WHY", ""),
        done_when=sections.get("DONE WHEN", ""),
        not_this=sections.get("NOT THIS", ""),
        context=sections.get("CONTEXT", ""),
        extra_sections=extra or None,
    )
    content = render_intake(fm, body)
    from .core import ERROR

    findings = grade_intake(fm.model_dump(mode="json"), body=body, commit_mode=True)
    errors = [f for f in findings if f.severity == ERROR]
    if errors:
        return None, "; ".join(f.message for f in errors)

    if not _exclusive_create(dest, content.decode("utf-8")):
        return None, f"collision: {dest.name} already exists"

    rel = str(dest.relative_to(root)) if dest.is_relative_to(root) else str(dest)
    return (
        IntakeCreateResult(
            path=rel,
            id=intake_id,
            status="OPEN",
            checks=["ZEO frontmatter written", "WHAT present", "status OPEN"],
        ),
        "",
    )


def create_intake_from_spec(root: pathlib.Path, spec: dict) -> tuple[IntakeCreateResult | None, str]:
    title = spec.get("title")
    what = spec.get("what")
    if not title and not what:
        return None, "spec requires title or what"
    not_this = spec.get("not_this") or spec.get("not-this")
    context = spec.get("context")
    return create_intake(
        root,
        title=title,
        what=what,
        why=spec.get("why"),
        done_when=spec.get("done_when") or spec.get("done-when"),
        not_this=not_this,
        context=context,
        project_hint=spec.get("project_hint") or spec.get("project"),
        stream_hint=spec.get("stream_hint") or spec.get("stream"),
    )


def open_editor_template(initial_what: str = "") -> str:
    if initial_what:
        return EDITOR_TEMPLATE.replace("WHAT:\n", f"WHAT:\n{initial_what}\n", 1)
    return EDITOR_TEMPLATE


# ── list / doctor ────────────────────────────────────────────────────


def list_intakes(root: pathlib.Path) -> list[dict[str, Any]]:
    root = pathlib.Path(root).resolve()
    d = intake_dir(root)
    out: list[dict[str, Any]] = []
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.md")):
        if f.name.upper() == "README.MD":
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            fm = extract_frontmatter(text)
        except Exception:
            continue
        if not isinstance(fm, dict):
            continue
        if str(fm.get("genre", "")).strip().lower() != "intake":
            continue
        st = normalize_intake_status(fm.get("status")) or str(fm.get("status") or "").upper()
        iid = intake_identity(fm, f)
        out.append(
            {
                "id": iid,
                "intake": iid,
                "status": st,
                "created": str(fm.get("created") or ""),
                "project": str(fm.get("project_hint") or fm.get("project") or "-"),
                "promoted_to": fm.get("promoted_to"),
                "file": f.name,
                "path": str(f.resolve()),
                "mtime": f.stat().st_mtime,
            }
        )
    return out


def status_counts(root: pathlib.Path) -> dict[str, int]:
    counts = {s: 0 for s in sorted(INTAKE_STATUSES)}
    for row in list_intakes(root):
        st = row["status"]
        if st in counts:
            counts[st] += 1
        else:
            counts.setdefault(st, 0)
            counts[st] += 1
    return counts


def doctor_intake(path: pathlib.Path, *, root: pathlib.Path | None = None) -> tuple[bool, list[str], list[str]]:
    """Return (ready, errors, advice)."""
    path = pathlib.Path(path).resolve()
    errors: list[str] = []
    advice: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return False, [f"unreadable: {exc}"], []
    fm, body = split_frontmatter_body(text)
    if fm == "MALFORMED":
        return False, ["frontmatter is not valid YAML"], []
    if not isinstance(fm, dict):
        return False, ["frontmatter missing"], []
    findings = grade_intake(fm, body=body, commit_mode=False)
    from .core import ERROR, WARN

    for f in findings:
        if f.severity == ERROR:
            errors.append(f.message)
        elif f.severity == WARN:
            advice.append(f.message)
    st = normalize_intake_status(fm.get("status"))
    if st == "OPEN":
        advice.append("status OPEN — candidate for mission → propose → promote")
    elif st == "PROMOTED":
        advice.append(f"already PROMOTED → {fm.get('promoted_to') or '?'}")
    ready = not errors
    return ready, errors, advice


# ── git / fingerprint helpers ────────────────────────────────────────


def git_head(cwd: pathlib.Path) -> str | None:
    try:
        r = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def worktree_fingerprint(cwd: pathlib.Path) -> str | None:
    """Cheap fingerprint: HEAD + porcelain status hash."""
    head = git_head(cwd) or "no-git"
    try:
        r = subprocess.run(
            ["git", "-C", str(cwd), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
        status = r.stdout if r.returncode == 0 else ""
    except Exception:
        status = ""
    blob = f"{head}\n{status}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _search_roots(corpus_root: pathlib.Path) -> list[pathlib.Path]:
    roots = [corpus_root]
    env = os.environ.get("ZEO_WORK_ROOT")
    if env:
        p = pathlib.Path(env).resolve()
        if p.is_dir() and p not in roots:
            roots.append(p)
    # Common: code lives beside corpus or corpus is the code repo.
    return roots


def _tokenize_terms(text: str) -> list[str]:
    # Identifiers, path-like tokens, kebab words of length >= 3
    found = re.findall(r"[A-Za-z_][A-Za-z0-9_./-]{2,}", text or "")
    stop = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "when",
        "what",
        "why",
        "not",
        "done",
        "context",
        "must",
        "should",
        "will",
        "have",
        "each",
        "file",
        "files",
    }
    out: list[str] = []
    seen: set[str] = set()
    for tok in found:
        low = tok.lower().strip("./")
        if low in stop or len(low) < 3:
            continue
        if low not in seen:
            seen.add(low)
            out.append(tok)
    return out[:40]


def gather_context(root: pathlib.Path, intake_path: pathlib.Path) -> dict[str, Any]:
    """Retrieval helper — no reasoning claims."""
    root = pathlib.Path(root).resolve()
    fm, body = load_intake(intake_path)
    terms = _tokenize_terms(body + "\n" + json.dumps(fm, default=str))
    search_roots = _search_roots(root)
    code_matches: list[str] = []
    test_matches: list[str] = []
    for sroot in search_roots:
        for term in terms[:15]:
            # Prefer path hints that look like files
            if "/" in term or term.endswith((".py", ".md", ".ts", ".tsx")):
                for sroot2 in search_roots:
                    cand = sroot2 / term
                    if cand.is_file():
                        rel = str(cand)
                        if rel not in code_matches:
                            code_matches.append(rel)
            # Glob basename matches under src/ and tests/
            base = pathlib.Path(term).name
            if not re.search(r"[A-Za-z]", base):
                continue
            for pattern in (
                f"**/{base}",
                f"**/{base}.py",
                f"**/test_{base}*.py",
                f"**/*{base}*",
            ):
                try:
                    hits = list(sroot.glob(pattern))[:5]
                except Exception:
                    hits = []
                for h in hits:
                    if not h.is_file():
                        continue
                    rel = str(h.relative_to(sroot)) if h.is_relative_to(sroot) else str(h)
                    if "test" in rel.lower() or rel.startswith("tests/"):
                        if rel not in test_matches:
                            test_matches.append(rel)
                    elif rel.endswith((".py", ".ts", ".tsx", ".js", ".md")):
                        if rel not in code_matches:
                            code_matches.append(rel)
                if len(code_matches) >= 20:
                    break
            if len(code_matches) >= 20:
                break

    recent: list[str] = []
    for sroot in search_roots:
        if not (sroot / ".git").exists() and not (sroot / ".git").is_file():
            # maybe git root is sroot
            pass
        paths = (code_matches + test_matches)[:8]
        if not paths:
            break
        try:
            r = subprocess.run(
                ["git", "-C", str(sroot), "log", "-5", "--oneline", "--"] + paths,
                capture_output=True,
                text=True,
                check=False,
            )
            if r.returncode == 0 and r.stdout.strip():
                recent = [ln for ln in r.stdout.strip().splitlines() if ln][:10]
                break
        except Exception:
            pass

    return {
        "intake": str(intake_path.relative_to(root)) if intake_path.is_relative_to(root) else str(intake_path),
        "terms": terms,
        "likely_code_matches": code_matches[:20],
        "likely_tests": test_matches[:20],
        "recent_commits": recent,
        "search_roots": [str(r) for r in search_roots],
        "repo_head": git_head(root),
        "worktree_fingerprint": worktree_fingerprint(root),
    }


def build_mission(root: pathlib.Path, intake_path: pathlib.Path) -> dict[str, Any]:
    root = pathlib.Path(root).resolve()
    intake_path = pathlib.Path(intake_path).resolve()
    fm, body = load_intake(intake_path)
    sections = parse_intake_sections(body)
    ctx = gather_context(root, intake_path)
    rel = str(intake_path.relative_to(root)) if intake_path.is_relative_to(root) else str(intake_path)
    iid = intake_identity(fm, intake_path)
    questions = [
        "What existing implementation should be reused rather than duplicated?",
        "What current behavior conflicts with the requested invariant?",
        "Which public CLI surfaces need to change?",
        "Which tests prove the invariant?",
        "What existing callers must remain compatible?",
    ]
    if sections.get("WHAT"):
        questions.append(f"What is the smallest change that satisfies WHAT: {sections['WHAT'][:120]}")
    return {
        "protocol_version": 1,
        "action": "investigate_then_promote",
        "intake": rel,
        "intake_id": iid,
        "goal": "Determine the smallest robust implementation needed to satisfy this intake.",
        "sections": {k: sections.get(k, "") for k in SECTION_HEADERS},
        "frontmatter": {
            "status": fm.get("status"),
            "project_hint": fm.get("project_hint") or fm.get("project"),
            "stream_hint": fm.get("stream_hint"),
        },
        "repo_head": ctx.get("repo_head"),
        "worktree_fingerprint": ctx.get("worktree_fingerprint"),
        "questions": questions,
        "suggested_context": {
            "terms": ctx.get("terms"),
            "likely_code_matches": ctx.get("likely_code_matches"),
            "likely_tests": ctx.get("likely_tests"),
            "recent_commits": ctx.get("recent_commits"),
        },
        "submission": {
            "command": f"zeo intake propose {rel} --spec -",
            "then": f"zeo intake promote {rel}",
            "schema": PROPOSAL_SCHEMA_HINT,
        },
    }


# ── proposal / evidence ──────────────────────────────────────────────


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    line_start: int
    line_end: int
    sha256: str | None = None


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact: str
    evidence: EvidenceRef


class Interpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str
    based_on: list[int] = Field(default_factory=list)


class DoneWhenItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["command", "inspection"] = "inspection"
    command: str | None = None
    expect: str | None = None
    criterion: str | None = None


class ImplementationContract(BaseModel):
    model_config = ConfigDict(extra="allow")

    problem: str
    invariant: str
    approach: list[str] = Field(default_factory=list)
    files_expected_to_change: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    done_when: list[DoneWhenItem | str] = Field(default_factory=list)


class Destination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: str | None = None
    stream: str | None = None
    title: str | None = None


class IntakeProposal(BaseModel):
    model_config = ConfigDict(extra="allow")

    summary: str | None = None
    repo_head: str
    worktree_fingerprint: str | None = None
    observations: list[Observation] = Field(default_factory=list)
    interpretations: list[Interpretation] = Field(default_factory=list)
    implementation: ImplementationContract
    destination: Destination | None = None

    @model_validator(mode="after")
    def _need_observations(self) -> IntakeProposal:
        if not self.observations:
            raise ValueError("observations must be non-empty (ground claims in current bytes)")
        return self


def _resolve_evidence_path(root: pathlib.Path, rel: str) -> pathlib.Path | None:
    p = pathlib.Path(rel)
    if p.is_file():
        return p.resolve()
    for sroot in _search_roots(root):
        cand = (sroot / rel).resolve()
        if cand.is_file():
            # Must stay under a search root
            try:
                cand.relative_to(sroot.resolve())
            except ValueError:
                continue
            return cand
        cand2 = pathlib.Path(rel).resolve()
        if cand2.is_file():
            return cand2
    return None


def hash_line_range(path: pathlib.Path, line_start: int, line_end: int) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if line_start < 1 or line_end < line_start or line_end > len(lines):
        raise ValueError(f"line range {line_start}-{line_end} out of bounds for {path} ({len(lines)} lines)")
    chunk = "\n".join(lines[line_start - 1 : line_end]).encode("utf-8")
    return hashlib.sha256(chunk).hexdigest()


def validate_proposal_evidence(
    root: pathlib.Path,
    proposal: IntakeProposal,
    *,
    require_fresh_head: bool = True,
) -> tuple[IntakeProposal, list[str]]:
    """Validate evidence; return (enriched_proposal, errors)."""
    errors: list[str] = []
    current_head = git_head(root)
    if require_fresh_head and current_head and proposal.repo_head and proposal.repo_head != current_head:
        errors.append(
            f"proposal evidence is stale: repo_head {proposal.repo_head} != current {current_head}; "
            "rerun investigation before promotion"
        )
    if proposal.worktree_fingerprint:
        now_fp = worktree_fingerprint(root)
        if now_fp and proposal.worktree_fingerprint != now_fp:
            errors.append(
                f"worktree fingerprint changed since investigation ({proposal.worktree_fingerprint} → {now_fp})"
            )

    enriched_obs: list[Observation] = []
    for obs in proposal.observations:
        ev = obs.evidence
        path = _resolve_evidence_path(root, ev.path)
        if path is None:
            errors.append(f"evidence path missing: {ev.path}")
            enriched_obs.append(obs)
            continue
        try:
            digest = hash_line_range(path, ev.line_start, ev.line_end)
        except ValueError as exc:
            errors.append(str(exc))
            enriched_obs.append(obs)
            continue
        if ev.sha256 and ev.sha256 != digest:
            errors.append(
                f"evidence bytes changed: {ev.path}:{ev.line_start}-{ev.line_end} "
                f"(stored {ev.sha256[:12]}… now {digest[:12]}…)"
            )
        enriched_obs.append(
            Observation(
                fact=obs.fact,
                evidence=EvidenceRef(
                    path=ev.path,
                    line_start=ev.line_start,
                    line_end=ev.line_end,
                    sha256=digest,
                ),
            )
        )

    for interp in proposal.interpretations:
        for idx in interp.based_on:
            if idx < 0 or idx >= len(proposal.observations):
                errors.append(f"interpretation based_on index {idx} out of range")

    data = proposal.model_dump()
    data["observations"] = [o.model_dump() for o in enriched_obs]
    enriched = IntakeProposal.model_validate(data)
    return enriched, errors


def proposal_path_for(root: pathlib.Path, intake_id: str) -> pathlib.Path:
    return proposals_dir(root) / f"{intake_id}.json"


def save_proposal(root: pathlib.Path, intake_id: str, proposal: IntakeProposal) -> pathlib.Path:
    d = proposals_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    path = proposal_path_for(root, intake_id)
    path.write_text(json.dumps(proposal.model_dump(), indent=2) + "\n", encoding="utf-8")
    return path


def load_proposal(root: pathlib.Path, intake_id: str) -> IntakeProposal | None:
    path = proposal_path_for(root, intake_id)
    if not path.is_file():
        return None
    return IntakeProposal.model_validate(json.loads(path.read_text(encoding="utf-8")))


def propose_intake(
    root: pathlib.Path,
    intake_path: pathlib.Path,
    spec: dict,
) -> tuple[pathlib.Path | None, IntakeProposal | None, str]:
    """Validate and persist a grounded proposal. Returns (path, proposal, error)."""
    root = pathlib.Path(root).resolve()
    intake_path = pathlib.Path(intake_path).resolve()
    try:
        fm, _body = load_intake(intake_path)
    except ValueError as exc:
        return None, None, str(exc)
    st = normalize_intake_status(fm.get("status"))
    if st != "OPEN":
        return None, None, f"intake status is {st}, expected OPEN"
    try:
        proposal = IntakeProposal.model_validate(spec)
    except ValidationError as exc:
        return None, None, f"proposal schema: {exc}"
    enriched, errors = validate_proposal_evidence(root, proposal)
    if errors:
        return None, None, "; ".join(errors)
    iid = intake_identity(fm, intake_path)
    path = save_proposal(root, iid, enriched)
    return path, enriched, ""


# ── promote ──────────────────────────────────────────────────────────


def _done_when_text(impl: ImplementationContract) -> str:
    parts: list[str] = []
    for item in impl.done_when:
        if isinstance(item, str):
            parts.append(item)
            continue
        if item.type == "command":
            parts.append(f"`{item.command}` → {item.expect or 'exit 0'}")
        else:
            parts.append(item.criterion or item.expect or "")
    text = "; ".join(p for p in parts if p)
    return text or impl.invariant or "Acceptance criteria established"


def build_sow_body_from_proposal(
    *,
    title: str,
    n: int,
    intake_rel: str,
    proposal: IntakeProposal,
) -> str:
    impl = proposal.implementation
    lines = [
        f"# SOW-{n:02d}: {title}",
        "",
        f"_Promoted from intake `{intake_rel}` (grounded proposal)._",
        "",
        "## Problem",
        "",
        impl.problem,
        "",
        "## Desired invariant",
        "",
        impl.invariant,
        "",
        "## Approach",
        "",
    ]
    for step in impl.approach:
        lines.append(f"- {step}")
    if not impl.approach:
        lines.append("- (see observations)")
    lines += ["", "## Files expected to change", ""]
    for f in impl.files_expected_to_change:
        lines.append(f"- `{f}`")
    if not impl.files_expected_to_change:
        lines.append("- (unspecified)")
    lines += ["", "## Non-goals", ""]
    for g in impl.non_goals:
        lines.append(f"- {g}")
    if not impl.non_goals:
        lines.append("- (none stated)")
    lines += ["", "## Grounded observations", ""]
    for obs in proposal.observations:
        ev = obs.evidence
        lines.append(f"- {obs.fact} (`{ev.path}:{ev.line_start}-{ev.line_end}`)")
    if proposal.interpretations:
        lines += ["", "## Interpretations", ""]
        for interp in proposal.interpretations:
            lines.append(f"- {interp.claim}")
    lines += ["", "## Done when", ""]
    for item in impl.done_when:
        if isinstance(item, str):
            lines.append(f"- {item}")
        elif item.type == "command":
            lines.append(f"- command: `{item.command}` expect {item.expect or 'exit 0'}")
        else:
            lines.append(f"- inspection: {item.criterion or item.expect}")
    if not impl.done_when:
        lines.append(f"- {impl.invariant}")
    lines.append("")
    return "\n".join(lines)


def build_ungrounded_sow_body(*, title: str, n: int, intake_rel: str, sections: dict[str, str]) -> str:
    return (
        f"# SOW-{n:02d}: {title}\n\n"
        f"_Promoted from intake `{intake_rel}` (ungrounded escape hatch)._\n\n"
        f"## Problem\n\n{sections.get('WHAT') or '(from intake WHAT)'}\n\n"
        f"## Why\n\n{sections.get('WHY') or '(none)'}\n\n"
        f"## Desired invariant\n\n{sections.get('DONE WHEN') or '(establish acceptance criteria)'}\n\n"
        f"## Non-goals\n\n{sections.get('NOT THIS') or '(none)'}\n\n"
        f"## Context\n\n{sections.get('CONTEXT') or '(none)'}\n\n"
        f"## Done when\n\n{sections.get('DONE WHEN') or '(establish acceptance criteria)'}\n"
    )


def mark_intake_promoted(
    root: pathlib.Path,
    intake_path: pathlib.Path,
    sow_rel: str,
) -> tuple[bool, str]:
    intake_path = pathlib.Path(intake_path).resolve()
    original = intake_path.read_bytes()
    fm, body = load_intake(intake_path)
    fm = dict(fm)
    fm["status"] = "PROMOTED"
    fm["promoted_to"] = sow_rel
    fm["updated"] = _dt.date.today()
    # Keep id/intake in sync
    iid = intake_identity(fm, intake_path)
    fm["id"] = iid
    fm["intake"] = iid
    try:
        validated = IntakeWriteFrontmatter.model_validate(
            {k: fm[k] for k in IntakeWriteFrontmatter.model_fields if k in fm}
        )
        rendered = validated.model_dump(mode="json", exclude_none=True)
        for k, v in fm.items():
            if k not in rendered:
                rendered[k] = v.isoformat() if isinstance(v, _dt.date) else v
    except ValidationError as exc:
        return False, str(exc)
    content = render_intake(rendered, body)
    try:
        atomic_replace(intake_path, expected=original, replacement=content)
    except RuntimeError as exc:
        return False, str(exc)
    return True, "ok"


def promote_intake(
    root: pathlib.Path,
    intake_path: pathlib.Path,
    *,
    spec: dict | None = None,
    project: str | None = None,
    stream: str | None = None,
    title: str | None = None,
    allow_ungrounded: bool = False,
    cwd: pathlib.Path | None = None,
) -> tuple[PromoteResult | None, str]:
    """Materialize an evidence-backed proposal into a governed SOW."""
    root = pathlib.Path(root).resolve()
    intake_path = pathlib.Path(intake_path).resolve()
    try:
        fm, body = load_intake(intake_path)
    except ValueError as exc:
        return None, str(exc)
    st = normalize_intake_status(fm.get("status"))
    if st != "OPEN":
        return None, f"intake status is {st}, expected OPEN"

    iid = intake_identity(fm, intake_path)
    sections = parse_intake_sections(body)
    proposal: IntakeProposal | None = None

    if spec is not None:
        path, proposal, err = propose_intake(root, intake_path, spec)
        if err:
            return None, err
    else:
        proposal = load_proposal(root, iid)
        if proposal is not None:
            enriched, errors = validate_proposal_evidence(root, proposal)
            if errors:
                return None, "; ".join(errors)
            proposal = enriched
            save_proposal(root, iid, proposal)

    if proposal is None and not allow_ungrounded:
        return None, (
            "no grounded proposal found; run `zeo intake mission` then "
            "`zeo intake propose FILE --spec ...` (or pass --spec / --allow-ungrounded)"
        )

    dest_project = project
    dest_stream = stream
    dest_title = title
    if proposal and proposal.destination:
        dest_project = dest_project or proposal.destination.project
        dest_stream = dest_stream or proposal.destination.stream
        dest_title = dest_title or proposal.destination.title
    dest_project = dest_project or fm.get("project_hint") or fm.get("project")
    dest_stream = dest_stream or fm.get("stream_hint")
    dest_title = dest_title or (sections.get("WHAT") or "").split("\n")[0][:80] or iid

    if not dest_project or not dest_stream:
        return None, "need project and stream (flags, proposal.destination, or intake hints)"

    intake_rel = str(intake_path.relative_to(root)) if intake_path.is_relative_to(root) else str(intake_path)

    # Pre-allocate n for body heading via locate after create — create_sow allocates.
    # Build body with placeholder n=0 then... better: call create_sow with body that uses
    # actual n. create_sow allocates internally. So build body inside a custom path:
    # use create_sow with a body callback... simplest: first resolve allocate_n.
    from .sow_authoring import allocate_n

    n = allocate_n(root, dest_stream)
    if proposal is not None:
        sow_body = build_sow_body_from_proposal(title=dest_title, n=n, intake_rel=intake_rel, proposal=proposal)
        done_when = _done_when_text(proposal.implementation)
    else:
        sow_body = build_ungrounded_sow_body(title=dest_title, n=n, intake_rel=intake_rel, sections=sections)
        done_when = sections.get("DONE WHEN") or "Clear acceptance criteria established"

    result, err = create_sow(
        root,
        project=str(dest_project),
        stream=str(dest_stream),
        title=str(dest_title),
        status="DESIGN",
        lifecycle="DESIGN-MEMO",
        done_when=done_when,
        restaufwand=1,
        body=sow_body,
        n=n,
        requested_by=f"intake:{iid}",
        cwd=cwd,
    )
    if result is None:
        return None, err

    # If create_sow collided and used a higher n, body heading may say wrong n — acceptable for V1
    # or rewrite. Prefer rewrite when n differs.
    if result.n != n:
        sow_path = root / result.path
        text = sow_path.read_text(encoding="utf-8")
        text = text.replace(f"# SOW-{n:02d}:", f"# SOW-{result.n:02d}:", 1)
        from .sow_authoring import transactional_replace

        transactional_replace(sow_path, text.encode("utf-8"), root=root)

    ok, mark_err = mark_intake_promoted(root, intake_path, result.path)
    if not ok:
        return None, f"SOW written at {result.path} but failed to mark intake: {mark_err}"

    checks = [
        f"allocated n={result.n}",
        "rendered Rev 17 frontmatter",
        "filename canonical",
        "body assembled from proposal" if proposal else "body assembled ungrounded",
        "lint passed",
        "written",
        "intake marked PROMOTED",
    ]
    return (
        PromoteResult(
            intake_path=intake_rel,
            sow_path=result.path,
            project=result.project,
            stream=result.sow,
            n=result.n,
            checks=checks,
        ),
        "",
    )


def ensure_zeo_gitignore(corpus_root: pathlib.Path) -> bool:
    """Ensure .zeo/ local proposal cache is gitignored."""
    corpus_root = pathlib.Path(corpus_root).resolve()
    path = corpus_root / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    have = {ln.strip() for ln in existing.splitlines() if ln.strip() and not ln.strip().startswith("#")}
    entries = [".zeo/"]
    missing = [e for e in entries if e not in have]
    if not missing:
        return False
    body = existing
    if body and not body.endswith("\n"):
        body += "\n"
    if body and not body.endswith("\n\n"):
        body += "\n"
    if "# zeo local cache" not in existing:
        body += "# zeo local cache (proposals — do not commit)\n"
    for name in missing:
        body += f"{name}\n"
    path.write_text(body, encoding="utf-8")
    return True
