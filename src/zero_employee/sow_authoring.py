"""SOW authoring: ZEO owns governance syntax; peers supply semantic values."""

from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from typing import Any, Callable, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .core import (
    ERROR,
    Finding,
    _exclusive_create,
    canonical_name,
    extract_frontmatter,
    filename_sow_number,
    find_canonical_claude_md,
    lint_file,
    locate_stream,
    parse_current_rev,
    project_of,
    words_to_slug,
)
from .migrate import atomic_replace
from .ollama_client import DEFAULT_MODEL, ollama_model
from .schemas.common import LIFECYCLES, STATUS_ENUM, STATUS_WORKING, normalize_status

SCHEMA_REV = 17
DEFAULT_SOW_REPO = "example-org/org"

KIND_MAP: dict[str, tuple[str, str]] = {
    "1": ("DESIGN", "DESIGN-MEMO"),
    "design": ("DESIGN", "DESIGN-MEMO"),
    "2": ("PROGRESS", "DESIGN-MEMO"),
    "implementation": ("PROGRESS", "DESIGN-MEMO"),
    "3": ("FINDING", "DECISION-RECORD"),
    "finding": ("FINDING", "DECISION-RECORD"),
    "4": ("HANDOVER", "HANDOVER"),
    "handover": ("HANDOVER", "HANDOVER"),
    "5": ("CLOSEOUT", "CLOSEOUT-RECORD"),
    "closeout": ("CLOSEOUT", "CLOSEOUT-RECORD"),
}

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_THINK = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)

BodyModelFn = Callable[..., str]


class SowWriteFrontmatter(BaseModel):
    """Canonical Rev-17 frontmatter written by ZEO authoring verbs."""

    model_config = ConfigDict(extra="allow")

    sow: str
    n: int
    schema_rev: Literal[17] = SCHEMA_REV
    project: str
    status: str
    lifecycle: str
    created: _dt.date
    updated: _dt.date
    genre: Literal["sow"] = "sow"
    done_when: str | None = None
    restaufwand: int | float | str | None = None
    sow_repo: str = DEFAULT_SOW_REPO
    work_repo: str
    requested_by: str
    binds: list[str] | None = None
    resolved_by: str | None = None
    ledger: list[Any] | None = None

    @field_validator("status", mode="before")
    @classmethod
    def _status(cls, value: object) -> object:
        if value is None or value == "":
            return value
        st = normalize_status(value)
        if st in STATUS_ENUM or str(value).strip().upper().startswith("SUPERSEDED"):
            return st
        raise ValueError(f"status must be one of {sorted(STATUS_ENUM)}")

    @field_validator("lifecycle", mode="before")
    @classmethod
    def _lifecycle(cls, value: object) -> object:
        if value is None or value == "":
            return value
        raw = str(value).strip().upper()
        if raw in LIFECYCLES:
            return raw
        raise ValueError(f"lifecycle must be one of {list(LIFECYCLES)}")

    @field_validator("n", mode="before")
    @classmethod
    def _n_int(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("n must be an integer")
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return value

    @model_validator(mode="after")
    def _working_fields(self) -> SowWriteFrontmatter:
        st = normalize_status(self.status)
        if st in STATUS_WORKING:
            if not str(self.done_when or "").strip():
                raise ValueError(f"done_when required for status {st}")
            if self.restaufwand is None or not str(self.restaufwand).strip():
                raise ValueError(f"restaufwand required for status {st}")
        return self


def slugify_title(title: str) -> str:
    return words_to_slug(title)


def canonical_sow_filename(stream: str, n: int, title_or_slug: str) -> str:
    """Zero-padded canonical SOW filename."""
    slug = (
        slugify_title(title_or_slug)
        if " " in title_or_slug or title_or_slug != title_or_slug.lower()
        else title_or_slug
    )
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug or ""):
        slug = slugify_title(title_or_slug)
    return canonical_name(stream, n, slug)


def split_frontmatter_body(text: str) -> tuple[dict | str | None, str]:
    """Return (frontmatter, body). Body excludes the closing --- fence."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            block = "".join(lines[1:i])
            body = "".join(lines[i + 1 :])
            if body.startswith("\n"):
                body = body[1:]
            try:
                fm = yaml.safe_load(block)
            except yaml.YAMLError:
                return "MALFORMED", body
            return fm, body
    return None, text


def render_sow(frontmatter: SowWriteFrontmatter | dict, body: str) -> bytes:
    """Serialize frontmatter with a real YAML library; attach body."""
    if isinstance(frontmatter, SowWriteFrontmatter):
        values = frontmatter.model_dump(mode="json", exclude_none=True)
    else:
        values = dict(frontmatter)
        # Normalize dates to ISO strings for dump stability.
        for key in ("created", "updated"):
            if isinstance(values.get(key), _dt.date):
                values[key] = values[key].isoformat()

    # Canonical key order for known fields; extras append in sorted order.
    order = [
        "sow",
        "n",
        "schema_rev",
        "project",
        "status",
        "lifecycle",
        "created",
        "updated",
        "genre",
        "done_when",
        "restaufwand",
        "sow_repo",
        "work_repo",
        "requested_by",
        "binds",
        "resolved_by",
        "ledger",
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
    if body_text and not body_text.startswith("\n") and not body_text.startswith("#"):
        # Keep a blank line after closing fence when body is non-empty.
        pass
    header = f"---\n{yaml_fragment}\n---\n\n"
    return (header + body_text).encode("utf-8")


def default_body(title: str, n: int, stream: str) -> str:
    return (
        f"# SOW-{n:02d}: {title}\n\n"
        f"## Problem\n\n"
        f"(describe the problem for workstream `{stream}`)\n\n"
        f"## Desired invariant\n\n"
        f"(what must be true when this SOW is done)\n\n"
        f"## Approach\n\n"
        f"(how we get there)\n\n"
        f"## Done when\n\n"
        f"(runnable stopping predicate — mirror `done_when:`)\n"
    )


def resolve_sow_target(
    root: pathlib.Path,
    *,
    project: str | None = None,
    stream: str | None = None,
    cwd: pathlib.Path | None = None,
) -> tuple[str, str, pathlib.Path]:
    """Resolve (project, stream, chain_dir)."""
    root = pathlib.Path(root).resolve()
    cwd = (cwd or pathlib.Path.cwd()).resolve()

    if project and stream:
        chain = root / "projects" / project / "sow" / stream
        return project, stream, chain

    # Infer from cwd: .../projects/<project>/sow/<stream>[/...]
    try:
        rel = cwd.relative_to(root)
    except ValueError:
        rel = None
    if rel is not None:
        parts = rel.parts
        if "projects" in parts:
            i = parts.index("projects")
            if len(parts) >= i + 3 and parts[i + 2] == "sow":
                proj = parts[i + 1]
                strm = parts[i + 3] if len(parts) > i + 3 else None
                if strm:
                    return proj, strm, root / "projects" / proj / "sow" / strm
        # <project>/sow/<stream>
        if "sow" in parts:
            i = parts.index("sow")
            if i >= 1 and len(parts) > i + 1:
                proj = parts[i - 1]
                strm = parts[i + 1]
                return (
                    proj,
                    strm,
                    root / proj / "sow" / strm
                    if not (root / "projects" / proj).is_dir()
                    else root / "projects" / proj / "sow" / strm,
                )

    if stream and not project:
        L = locate_stream(root, stream)
        if L["ambiguous"]:
            raise ValueError(f"stream {stream!r} is ambiguous ({len(L['candidates'])} dirs)")
        if L["chain_dir"]:
            chain = pathlib.Path(L["chain_dir"])
            proj = project_of(chain / "dummy.md", root) or _infer_project_from_chain(chain, root)
            if not proj:
                raise ValueError(f"cannot derive project for stream {stream!r}; pass --project")
            return proj, stream, chain
        projects = root / "projects"
        if projects.is_dir():
            projs = [p for p in projects.iterdir() if p.is_dir()]
            if len(projs) == 1:
                return projs[0].name, stream, projs[0] / "sow" / stream
        raise ValueError(f"cannot place stream {stream!r}; pass project and stream")

    raise ValueError("need <project> <stream>, or run from projects/<project>/sow/<stream>/")


def _infer_project_from_chain(chain: pathlib.Path, root: pathlib.Path) -> str | None:
    return project_of(chain / "x.md", root)


def allocate_n(root: pathlib.Path, stream: str, *, preferred: int | None = None) -> int:
    if preferred is not None:
        return preferred
    L = locate_stream(root, stream)
    if L["next_n"] is not None:
        return int(L["next_n"])
    return 1


def build_frontmatter(
    *,
    project: str,
    stream: str,
    n: int,
    status: str = "DESIGN",
    lifecycle: str | None = None,
    title: str = "",
    done_when: str | None = None,
    restaufwand: int | float | str | None = None,
    requested_by: str | None = None,
    work_repo: str | None = None,
    sow_repo: str = DEFAULT_SOW_REPO,
    binds: list[str] | None = None,
    today: _dt.date | None = None,
) -> SowWriteFrontmatter:
    today = today or _dt.date.today()
    st = normalize_status(status)
    if lifecycle is None:
        lifecycle = "DESIGN-MEMO"
        for _kind, (ks, kl) in KIND_MAP.items():
            if ks == st:
                lifecycle = kl
                break
    rb = requested_by or os.environ.get("ZEO_REQUESTED_BY") or "unknown"
    return SowWriteFrontmatter(
        sow=stream,
        n=n,
        schema_rev=SCHEMA_REV,
        project=project,
        status=st,
        lifecycle=str(lifecycle).upper(),
        created=today,
        updated=today,
        genre="sow",
        done_when=done_when,
        restaufwand=restaufwand,
        sow_repo=sow_repo,
        work_repo=work_repo or f"example-org/{project}",
        requested_by=rb,
        binds=binds,
    )


def validate_candidate_bytes(
    dest: pathlib.Path,
    content: bytes,
    *,
    root: pathlib.Path,
) -> tuple[bool, str, list[Finding]]:
    """Parse, schema-validate, identity-check, and lint. Does not write dest."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return False, "candidate is not valid UTF-8", []

    fm = extract_frontmatter(text)
    if fm is None:
        return False, "candidate has no parseable frontmatter block", []
    if fm == "MALFORMED" or not isinstance(fm, dict):
        return False, "candidate frontmatter is malformed", []

    try:
        SowWriteFrontmatter.model_validate(fm)
    except ValidationError as exc:
        msg = "; ".join(f"{'.'.join(str(p) for p in e.get('loc', ()))}: {e.get('msg')}" for e in exc.errors())
        return False, f"schema: {msg}", []

    name = dest.name
    declared_n = fm.get("n")
    file_n = filename_sow_number(dest)
    if file_n is None:
        return False, f"filename {name!r} is not canonical <stream>-SOW-<n>-<slug>.md", []
    if declared_n is not None and int(declared_n) != file_n:
        return False, f"n mismatch: frontmatter n={declared_n} filename n={file_n}", []
    stream = str(fm.get("sow") or "").strip()
    if stream and not name.lower().startswith(f"{stream.lower()}-sow-"):
        return False, f"filename does not match stream {stream!r}", []

    canon = find_canonical_claude_md(root)
    current_rev = parse_current_rev(canon.read_text(encoding="utf-8", errors="replace")) if canon else SCHEMA_REV

    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{dest.name}.", suffix=".zeo-validate", dir=dest.parent)
    tmp_path = pathlib.Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        status, findings = lint_file(
            tmp_path,
            current_rev=current_rev,
            root=root,
            commit_mode=True,
        )
        if status == "FAIL":
            errs = [f for f in findings if f.severity == ERROR]
            reason = "; ".join(f.message for f in errs) or "lint FAIL"
            return False, reason, findings
        if status == "CANNOT-GRADE":
            reason = "; ".join(f.message for f in findings) or "cannot-grade"
            return False, reason, findings
        return True, "ok", findings
    finally:
        tmp_path.unlink(missing_ok=True)


def transactional_create(
    dest: pathlib.Path,
    content: bytes,
    *,
    root: pathlib.Path,
) -> tuple[bool, str, list[Finding]]:
    """Validate then exclusive-create. Never leaves a half-written SOW."""
    ok, reason, findings = validate_candidate_bytes(dest, content, root=root)
    if not ok:
        return False, reason, findings
    text = content.decode("utf-8")
    if not _exclusive_create(dest, text):
        return False, f"collision: {dest.name} already exists", findings
    return True, "ok", findings


def transactional_replace(
    dest: pathlib.Path,
    content: bytes,
    *,
    root: pathlib.Path,
    expected: bytes | None = None,
) -> tuple[bool, str, list[Finding]]:
    ok, reason, findings = validate_candidate_bytes(dest, content, root=root)
    if not ok:
        return False, reason, findings
    try:
        atomic_replace(dest, expected=expected if expected is not None else dest.read_bytes(), replacement=content)
    except RuntimeError as exc:
        return False, str(exc), findings
    return True, "ok", findings


# ── create / new ────────────────────────────────────────────────────


class CreateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    project: str
    sow: str
    n: int
    status: str
    lifecycle: str
    schema_rev: int = SCHEMA_REV
    checks: list[str] = Field(default_factory=list)


def create_sow(
    root: pathlib.Path,
    *,
    project: str | None = None,
    stream: str | None = None,
    title: str,
    status: str = "DESIGN",
    lifecycle: str | None = None,
    done_when: str | None = None,
    restaufwand: int | float | str | None = None,
    body: str | None = None,
    n: int | None = None,
    requested_by: str | None = None,
    cwd: pathlib.Path | None = None,
    retries: int = 8,
) -> tuple[CreateResult | None, str]:
    """Create a valid SOW. Returns (result, error_reason)."""
    root = pathlib.Path(root).resolve()
    try:
        project, stream, chain = resolve_sow_target(root, project=project, stream=stream, cwd=cwd)
    except ValueError as exc:
        return None, str(exc)

    chain.mkdir(parents=True, exist_ok=True)
    # Ensure project directory exists for greenfield convenience.
    (root / "projects" / project).mkdir(parents=True, exist_ok=True)

    st = normalize_status(status)
    if st in STATUS_WORKING:
        if done_when is None:
            done_when = "Clear acceptance criteria established"
        if restaufwand is None:
            restaufwand = 1

    start_n = allocate_n(root, stream, preferred=n)
    last_reason = "could not create"
    for attempt in range(retries):
        candidate_n = start_n + attempt
        try:
            fm = build_frontmatter(
                project=project,
                stream=stream,
                n=candidate_n,
                status=status,
                lifecycle=lifecycle,
                title=title,
                done_when=done_when,
                restaufwand=restaufwand,
                requested_by=requested_by,
            )
        except ValidationError as exc:
            return None, str(exc)

        filename = canonical_sow_filename(stream, candidate_n, title)
        dest = chain / filename
        body_text = body if body is not None else default_body(title, candidate_n, stream)
        content = render_sow(fm, body_text)
        ok, reason, findings = transactional_create(dest, content, root=root)
        if ok:
            checks = [
                "filename matches stream + n",
                "YAML parses",
                "required fields present",
                f"canonical Rev {SCHEMA_REV}",
                "no collision",
                "zeo lint passes",
            ]
            return (
                CreateResult(
                    path=str(dest.relative_to(root)) if dest.is_relative_to(root) else str(dest),
                    project=project,
                    sow=stream,
                    n=candidate_n,
                    status=fm.status,
                    lifecycle=fm.lifecycle,
                    schema_rev=SCHEMA_REV,
                    checks=checks,
                ),
                "",
            )
        if "collision" in reason or "already exists" in reason:
            last_reason = reason
            continue
        return None, reason
    return None, last_reason


def create_sow_from_spec(
    root: pathlib.Path, spec: dict, *, cwd: pathlib.Path | None = None
) -> tuple[CreateResult | None, str]:
    return create_sow(
        root,
        project=spec.get("project"),
        stream=spec.get("stream") or spec.get("sow"),
        title=spec["title"],
        status=spec.get("status", "DESIGN"),
        lifecycle=spec.get("lifecycle"),
        done_when=spec.get("done_when") or spec.get("done-when"),
        restaufwand=spec.get("restaufwand"),
        body=spec.get("body"),
        n=spec.get("n"),
        requested_by=spec.get("requested_by"),
        cwd=cwd,
    )


# ── mutate ──────────────────────────────────────────────────────────


def _coerce_scalar(raw: str) -> Any:
    lowered = raw.strip().lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if re.fullmatch(r"-?\d+", raw.strip()):
        return int(raw.strip())
    if re.fullmatch(r"-?\d+\.\d+", raw.strip()):
        return float(raw.strip())
    return raw


def set_field(path: pathlib.Path, key: str, value: str, *, root: pathlib.Path | None = None) -> tuple[bool, str]:
    path = pathlib.Path(path).resolve()
    root = pathlib.Path(root).resolve() if root else _root_of(path)
    original = path.read_bytes()
    text = original.decode("utf-8")
    fm, body = split_frontmatter_body(text)
    if not isinstance(fm, dict):
        return False, "frontmatter missing or malformed"
    fm = dict(fm)
    fm[key] = _coerce_scalar(value)
    if key == "updated":
        pass
    else:
        fm["updated"] = _dt.date.today()
    try:
        # Re-validate when possible; allow extra keys via model + merge.
        known = {k: fm[k] for k in SowWriteFrontmatter.model_fields if k in fm}
        validated = SowWriteFrontmatter.model_validate(known)
        rendered_fm = validated.model_dump(mode="json", exclude_none=True)
        for k, v in fm.items():
            if k not in rendered_fm:
                rendered_fm[k] = v.isoformat() if isinstance(v, _dt.date) else v
    except ValidationError as exc:
        return False, f"schema: {exc}"
    content = render_sow(rendered_fm, body)
    ok, reason, _ = transactional_replace(path, content, root=root, expected=original)
    return ok, reason


def add_list_value(path: pathlib.Path, key: str, value: str, *, root: pathlib.Path | None = None) -> tuple[bool, str]:
    path = pathlib.Path(path).resolve()
    root = pathlib.Path(root).resolve() if root else _root_of(path)
    original = path.read_bytes()
    text = original.decode("utf-8")
    fm, body = split_frontmatter_body(text)
    if not isinstance(fm, dict):
        return False, "frontmatter missing or malformed"
    fm = dict(fm)
    current = fm.get(key)
    if current is None:
        items: list[Any] = []
    elif isinstance(current, list):
        items = list(current)
    else:
        return False, f"{key} is not a list field"
    if value not in items:
        items.append(value)
    fm[key] = items
    fm["updated"] = _dt.date.today()
    content = render_sow(fm, body)
    ok, reason, _ = transactional_replace(path, content, root=root, expected=original)
    return ok, reason


def remove_list_value(
    path: pathlib.Path, key: str, value: str, *, root: pathlib.Path | None = None
) -> tuple[bool, str]:
    path = pathlib.Path(path).resolve()
    root = pathlib.Path(root).resolve() if root else _root_of(path)
    original = path.read_bytes()
    text = original.decode("utf-8")
    fm, body = split_frontmatter_body(text)
    if not isinstance(fm, dict):
        return False, "frontmatter missing or malformed"
    fm = dict(fm)
    current = fm.get(key)
    if not isinstance(current, list):
        return False, f"{key} is not a list field"
    fm[key] = [item for item in current if str(item) != value]
    if not fm[key]:
        fm[key] = None
    fm["updated"] = _dt.date.today()
    content = render_sow(fm, body)
    ok, reason, _ = transactional_replace(path, content, root=root, expected=original)
    return ok, reason


def _root_of(path: pathlib.Path) -> pathlib.Path:
    canon = find_canonical_claude_md(path)
    if canon:
        return canon.parent.parent
    return path.parent


# ── doctor ──────────────────────────────────────────────────────────


def doctor_file(path: pathlib.Path, *, root: pathlib.Path | None = None) -> tuple[bool, list[str], list[str]]:
    """Return (ready, ok_lines, fail_lines)."""
    path = pathlib.Path(path).resolve()
    root = pathlib.Path(root).resolve() if root else _root_of(path)
    oks: list[str] = []
    fails: list[str] = []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, [], [f"cannot read: {exc}"]

    fm = extract_frontmatter(text)
    if fm == "MALFORMED" or (fm is not None and not isinstance(fm, dict)):
        fails.append("YAML invalid")
        return False, oks, fails
    if fm is None:
        fails.append("no frontmatter")
        return False, oks, fails
    oks.append("YAML valid")

    sr = fm.get("schema_rev")
    if sr == SCHEMA_REV or sr == str(SCHEMA_REV):
        oks.append(f"Rev {SCHEMA_REV}")
    else:
        fails.append(f"schema_rev is {sr!r}, want {SCHEMA_REV}")

    file_n = filename_sow_number(path)
    declared_n = fm.get("n")
    stream = str(fm.get("sow") or "")
    if (
        file_n is not None
        and declared_n is not None
        and int(declared_n) == file_n
        and path.name.lower().startswith(f"{stream.lower()}-sow-")
    ):
        oks.append("filename = stream + n")
    else:
        fails.append("filename does not match stream + n")

    proj = project_of(path, root)
    if proj:
        oks.append("project exists")
    else:
        fails.append("project path not canonical / missing")

    if stream:
        L = locate_stream(root, stream)
        if L["chain_dir"] or (root / "projects" / str(fm.get("project")) / "sow" / stream).is_dir():
            oks.append("stream exists")
        else:
            fails.append("stream directory missing")

    if declared_n is not None:
        oks.append(f"n={declared_n} consistent")

    try:
        SowWriteFrontmatter.model_validate(fm)
        oks.append("required fields complete")
    except ValidationError as exc:
        # RULING-325 §4: `exc.errors()[0]['loc']` (the actual field PATH) was previously
        # discarded — only `.get('msg')` (Pydantic's generic "Field required") was read,
        # so a seat hitting this had to reverse-engineer which field from source. Name
        # every missing field, not just the first, so one doctor run surfaces the whole
        # defect instead of a single fix-rerun-refail cycle per field.
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", ())) or "<root>"
            fails.append(f"required field missing: {loc} ({err.get('msg')})")

    canon = find_canonical_claude_md(root)
    current_rev = parse_current_rev(canon.read_text(encoding="utf-8", errors="replace")) if canon else SCHEMA_REV
    status, findings = lint_file(path, current_rev=current_rev, root=root, commit_mode=True)
    if status == "PASS":
        oks.append("lint passes")
    else:
        errs = [f.message for f in findings if f.severity == ERROR] or [f.message for f in findings]
        fails.append("lint: " + ("; ".join(errs[:3]) if errs else status))

    oks.append("no historical artifact mutation")  # doctor is read-only by construction
    return not fails, oks, fails


def git_changed_markdown(root: pathlib.Path) -> list[pathlib.Path]:
    root = pathlib.Path(root).resolve()
    paths: set[str] = set()
    for args in (
        ["git", "-C", str(root), "diff", "--name-only"],
        ["git", "-C", str(root), "diff", "--name-only", "--cached"],
        ["git", "-C", str(root), "ls-files", "--others", "--exclude-standard"],
    ):
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if proc.returncode != 0:
            continue
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.endswith(".md"):
                paths.add(line)
    out = []
    for rel in sorted(paths):
        p = root / rel
        if not p.is_file():
            continue
        # SOW or ruling under sow/ or ruling/
        norm = rel.replace("\\", "/")
        if "/sow/" in f"/{norm}" or norm.startswith("ruling/") or "/ruling/" in f"/{norm}":
            out.append(p)
    return out


# ── draft (Ollama peer loop) ────────────────────────────────────────


def clean_body_output(raw: str) -> str:
    text = _ANSI.sub("", raw or "")
    text = _THINK.sub("", text)
    lines = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines.append(line)
    return "\n".join(lines).strip() + "\n"


def body_contains_frontmatter(body: str) -> bool:
    """True if the model tried to emit YAML frontmatter."""
    lines = body.splitlines()
    if not lines:
        return False
    # Leading --- ... --- block
    if lines[0].strip() == "---":
        for line in lines[1:6]:
            if ":" in line and not line.strip().startswith("#"):
                return True
        if any(l.strip() == "---" for l in lines[1:]):
            return True
    return bool(re.search(r"(?m)^schema_rev\s*:", body) or re.search(r"(?m)^sow\s*:", body))


def draft_body_prompt(
    *,
    title: str,
    stream: str,
    status: str,
    done_when: str | None,
    peer_notes: str = "",
    prior_body: str = "",
    structure_hint: str | None = None,
) -> str:
    structure = structure_hint or ("## Problem\n\n## Desired invariant\n\n## Approach\n\n## Done when\n")
    return f"""You author the BODY of a Statement of Work (SOW).

Return ONLY markdown body sections. Do NOT output YAML. Do NOT output a --- frontmatter block.
Do NOT invent schema_rev, project, n, sow, status, or lifecycle fields.

Title: {title}
Stream: {stream}
Status: {status}
Done when (frontmatter): {done_when or "(unset)"}

Required section structure:
{structure}

{f"Peer notes to incorporate:{chr(10)}{peer_notes}{chr(10)}" if peer_notes else ""}
{f"Prior body draft to revise:{chr(10)}{prior_body}{chr(10)}" if prior_body else ""}
--- BEGIN BODY ONLY ---"""


def draft_sow(
    root: pathlib.Path,
    *,
    project: str | None,
    stream: str | None,
    title: str,
    status: str = "DESIGN",
    done_when: str | None = None,
    restaufwand: int | float | str | None = None,
    peer: Literal["human", "agent"] = "human",
    model_tag: str = DEFAULT_MODEL,
    model_fn: BodyModelFn | None = None,
    seed_prompt: str = "",
    cap: int = 5,
    stdin=None,
    stdout=None,
) -> tuple[CreateResult | None, str]:
    """Draft loop that only writes after peer accept (preferred entrypoint)."""
    root = pathlib.Path(root).resolve()
    model_fn = model_fn or ollama_model
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout

    try:
        project, stream, chain = resolve_sow_target(root, project=project, stream=stream)
    except ValueError as exc:
        return None, str(exc)

    if done_when is None and normalize_status(status) in STATUS_WORKING:
        done_when = "Clear acceptance criteria established"
    if restaufwand is None and normalize_status(status) in STATUS_WORKING:
        restaufwand = 1

    notes = seed_prompt
    prior = ""
    peer_body: str | None = None

    def emit(obj: dict) -> None:
        if peer == "agent":
            print(json.dumps(obj, ensure_ascii=False), file=stdout, flush=True)
        else:
            action = obj.get("action")
            if action == "propose":
                print("\n--- proposed body ---\n", file=stdout)
                print(obj.get("body") or "", file=stdout)
                for f in obj.get("findings") or []:
                    print(f"  ✗ {f}", file=stdout)
            elif action == "written":
                print(f"\nWritten: {obj.get('path')}", file=stdout)
            elif action == "failed":
                print(f"✗ SOW not written\nReason: {obj.get('reason')}", file=stdout)
            elif action == "needs_input":
                print(obj.get("message") or "", file=stdout)

    def read_peer() -> dict:
        if peer == "agent":
            line = stdin.readline()
            if not line:
                return {"role": "peer", "action": "reject"}
            return json.loads(line)
        print("Accept body? [a]ccept / [e]dit notes / [b]ody paste / [r]eject: ", end="", file=stdout, flush=True)
        choice = (stdin.readline() or "r").strip().lower() or "r"
        if choice.startswith("a"):
            return {"role": "peer", "action": "accept"}
        if choice.startswith("r"):
            return {"role": "peer", "action": "reject"}
        if choice.startswith("b"):
            print("Paste body, end with a line containing only END", file=stdout)
            lines = []
            while True:
                line = stdin.readline()
                if not line or line.strip() == "END":
                    break
                lines.append(line)
            return {"role": "peer", "action": "revise", "body": "".join(lines)}
        print("Notes: ", end="", file=stdout, flush=True)
        note = stdin.readline() or ""
        return {"role": "peer", "action": "revise", "notes": note.strip()}

    if peer == "agent":
        emit({"role": "zeo", "action": "needs_input", "message": "send seed JSON (action=seed|revise)"})
        first = read_peer()
        if first.get("action") == "reject":
            return None, "peer rejected"
        if first.get("title"):
            title = str(first["title"])
        notes = first.get("notes") or first.get("prompt") or notes
        if first.get("body"):
            peer_body = first["body"]
        if first.get("done_when"):
            done_when = first["done_when"]
        if first.get("status"):
            status = first["status"]

    last_reason = "no attempt"
    for _attempt in range(1, cap + 1):
        if peer_body is not None:
            body = peer_body if peer_body.endswith("\n") else peer_body + "\n"
            peer_body = None
        else:
            prompt = draft_body_prompt(
                title=title,
                stream=stream,
                status=status,
                done_when=done_when,
                peer_notes=notes,
                prior_body=prior,
            )
            try:
                raw = model_fn(prompt, model_tag)
            except Exception as exc:
                last_reason = f"model: {exc}"
                continue
            body = clean_body_output(raw)
            if body_contains_frontmatter(body):
                last_reason = "model emitted frontmatter; body-only required"
                notes = f"Previous answer rejected: {last_reason}. Output markdown sections only."
                prior = body
                continue

        n = allocate_n(root, stream)
        try:
            fm = build_frontmatter(
                project=project,
                stream=stream,
                n=n,
                status=status,
                done_when=done_when,
                restaufwand=restaufwand,
            )
        except ValidationError as exc:
            return None, str(exc)

        filename = canonical_sow_filename(stream, n, title)
        dest = chain / filename
        content = render_sow(fm, body)
        ok, reason, _findings = validate_candidate_bytes(dest, content, root=root)
        findings_msgs = [] if ok else [reason]
        emit({"role": "zeo", "action": "propose", "body": body, "findings": findings_msgs, "path": None})

        msg = read_peer()
        action = msg.get("action")
        if action == "reject":
            return None, "peer rejected"
        if action == "revise":
            notes = msg.get("notes") or notes
            if msg.get("body"):
                peer_body = msg["body"]
            prior = body
            last_reason = reason if not ok else "peer requested revise"
            continue
        if action != "accept":
            last_reason = f"unknown peer action {action!r}"
            continue

        if msg.get("body"):
            body = msg["body"] if str(msg["body"]).endswith("\n") else str(msg["body"]) + "\n"
            content = render_sow(fm, body)

        # Re-allocate n in case of race, then write.
        result, err = create_sow(
            root,
            project=project,
            stream=stream,
            title=title,
            status=status,
            done_when=done_when,
            restaufwand=restaufwand,
            body=body,
        )
        if result:
            emit({"role": "zeo", "action": "written", "path": result.path, "body": body})
            return result, ""
        last_reason = err
        notes = f"Gate rejected write: {err}"
        prior = body

    emit({"role": "zeo", "action": "failed", "reason": last_reason})
    return None, last_reason
