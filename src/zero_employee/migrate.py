from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import stat
import subprocess
import tempfile
from enum import Enum
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from .core import (
    _SOW_FILE_RE,
    extract_frontmatter,
    migrate_check,
    project_of,
)
from .schemas.common import LIFECYCLES, STATUS_RESTING, STATUS_WORKING


UNKNOWN = "unknown - pre-schema prose"

RestingStatus = Enum(
    "RestingStatus",
    {f"VALUE_{i}": value for i, value in enumerate(sorted(STATUS_RESTING))},
    type=str,
)

Lifecycle = Enum(
    "Lifecycle",
    {f"VALUE_{i}": value for i, value in enumerate(LIFECYCLES)},
    type=str,
)


class Claim(BaseModel):
    """The model's entire authority."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    status: RestingStatus
    lifecycle: Lifecycle

    @field_validator("status", "lifecycle", mode="before")
    @classmethod
    def normalize_enum(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value


class Ground(BaseModel):
    """Facts derived without consulting the model."""

    model_config = ConfigDict(extra="forbid")

    sow: str | None
    project: str | None
    n: int | None
    created: datetime.date | None
    updated: datetime.date | None


UnknownText = Literal["unknown - pre-schema prose"]


class MigratedFrontmatter(BaseModel):
    """The exact schema written to disk."""

    model_config = ConfigDict(extra="forbid")

    sow: str | UnknownText
    n: int | UnknownText
    schema_rev: Literal[17]
    project: str | UnknownText
    status: RestingStatus
    lifecycle: Lifecycle
    created: datetime.date | UnknownText
    updated: datetime.date | UnknownText
    sow_repo: Literal["example-org/org"]
    work_repo: UnknownText
    requested_by: UnknownText
    migrated_by: str


class RejectionKind(str, Enum):
    MODEL = "MODEL"
    EXTRACT = "EXTRACT"
    CLAIM = "CLAIM"
    ASSEMBLY = "ASSEMBLY"
    GATE = "GATE"
    CONCURRENT_CHANGE = "CONCURRENT_CHANGE"


_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_THINK = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)
_KEYLINE = re.compile(
    r"""^\s*["']?(status|lifecycle)["']?\s*:\s*
        ["']?([A-Za-z][A-Za-z0-9_-]*)["']?\s*,?\s*$""",
    re.IGNORECASE | re.VERBOSE,
)


def prompt_for(body: str, feedback: str = "") -> str:
    return f"""You classify an OLD engineering document.

Return exactly one JSON object matching this schema:
{json.dumps(Claim.model_json_schema(), indent=2)}

The document is history of unknown age and is never in flight.
If it appears mid-work, use STALE.
Use HELD only when the body explicitly names what it is waiting on.

Do not infer dates, project, stream, identity, repositories, or provenance.
Those facts are derived mechanically.

{feedback}
--- DOCUMENT BEGINS ---
{body}
--- DOCUMENT ENDS ---"""


def _clean_model_output(text: str) -> str:
    text = _ANSI.sub("", text or "")
    text = _THINK.sub("", text)
    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("```")).strip()


def extract_claim(raw: str) -> dict[str, object]:
    """Extract the last audible claim without trusting surrounding prose."""

    text = _clean_model_output(raw)

    # Structured Ollama output normally takes this path.
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    # Find JSON objects embedded in reasoning text.
    decoder = json.JSONDecoder()
    candidates: list[dict[str, object]] = []

    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            candidates.append(value)

    if candidates:
        return candidates[-1]

    # Compatibility path for YAML-like model output.
    found: dict[str, object] = {}
    for line in text.splitlines():
        match = _KEYLINE.match(line)
        if match:
            found[match.group(1).lower()] = match.group(2)

    return found


def validate_claim(raw: str) -> tuple[Claim | None, str | None]:
    extracted = extract_claim(raw)

    if not extracted:
        return None, ("EXTRACT: no status/lifecycle claim was found; return exactly one JSON object")

    try:
        return Claim.model_validate(extracted), None
    except ValidationError as exc:
        messages = []

        for error in exc.errors():
            field = ".".join(str(part) for part in error["loc"])
            error_type = error["type"]

            if field == "status":
                allowed = ", ".join(sorted(STATUS_RESTING))
                messages.append(f"status must be an at-rest value; allowed: {allowed}")
            elif field == "lifecycle":
                messages.append(f"lifecycle must be one of: {', '.join(LIFECYCLES)}")
            elif error_type == "extra_forbidden":
                messages.append(f"remove unexpected key: {field}")
            else:
                messages.append(f"{field}: {error['msg']}")

        return None, "CLAIM: " + "; ".join(messages)


def _body_window(body: str, head: int = 80, tail: int = 20) -> str:
    lines = body.splitlines()

    if len(lines) <= head + tail:
        return body

    omitted = len(lines) - head - tail
    return "\n".join(lines[:head] + [f"... ({omitted} lines omitted) ..."] + lines[-tail:])


def stream_of(path: pathlib.Path, root: pathlib.Path | None = None) -> str | None:
    candidate = path

    if root is not None:
        try:
            candidate = path.relative_to(root)
        except ValueError:
            pass

    parts = candidate.parts

    for index, segment in enumerate(parts):
        if segment == "sow":
            return parts[index + 1] if index + 2 < len(parts) else None

    return None


def n_of(path: pathlib.Path) -> int | None:
    match = _SOW_FILE_RE.match(path.name)

    if match is None:
        return None

    try:
        return int(match.group("n"))
    except (TypeError, ValueError):
        return None


def _git_root(repo: pathlib.Path) -> pathlib.Path | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        return None

    return pathlib.Path(result.stdout.strip())


def git_dates(
    path: pathlib.Path,
    repo: pathlib.Path,
) -> tuple[datetime.date | None, datetime.date | None]:
    root = _git_root(repo)

    if root is None:
        return None, None

    try:
        relative_path = path.resolve().relative_to(root.resolve())
    except ValueError:
        return None, None

    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "log",
            "--follow",
            "--diff-filter=AM",
            "--format=%ad",
            "--date=short",
            "--",
            relative_path.as_posix(),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        return None, None

    dates: list[datetime.date] = []

    for line in result.stdout.splitlines():
        try:
            dates.append(datetime.date.fromisoformat(line.strip()))
        except ValueError:
            continue

    if not dates:
        return None, None

    # git log is newest first.
    return dates[-1], dates[0]


def derive_ground(
    path: pathlib.Path,
    root: pathlib.Path,
    repo: pathlib.Path,
) -> Ground:
    created, updated = git_dates(path, repo)

    return Ground(
        sow=stream_of(path, root),
        project=project_of(path, root),
        n=n_of(path),
        created=created,
        updated=updated,
    )


def ground_blockers(ground: Ground) -> list[str]:
    """Fields whose absence makes a conformant candidate impossible."""

    blockers = []

    if ground.n is None:
        blockers.append("n: filename does not contain a conformant SOW number")

    if ground.project is None:
        blockers.append("project: project cannot be derived from the path")

    return blockers


def assemble_frontmatter(
    ground: Ground,
    claim: Claim,
    *,
    tag: str,
    version: str,
    today: datetime.date,
) -> MigratedFrontmatter:
    return MigratedFrontmatter(
        sow=ground.sow if ground.sow is not None else UNKNOWN,
        n=ground.n if ground.n is not None else UNKNOWN,
        schema_rev=17,
        project=ground.project if ground.project is not None else UNKNOWN,
        status=claim.status,
        lifecycle=claim.lifecycle,
        created=ground.created if ground.created is not None else UNKNOWN,
        updated=ground.updated if ground.updated is not None else UNKNOWN,
        sow_repo="example-org/org",
        work_repo=UNKNOWN,
        requested_by=UNKNOWN,
        migrated_by=f"{tag} · {today.isoformat()} · zeo {version}",
    )


def render_candidate(
    frontmatter: MigratedFrontmatter,
    original_body: bytes,
) -> bytes:
    values = frontmatter.model_dump(mode="json")

    yaml_fragment = yaml.safe_dump(
        values,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).rstrip()

    # original_body is appended byte-for-byte.
    header = f"---\n{yaml_fragment}\n---\n\n".encode("utf-8")
    return header + original_body


def parse_verify(candidate: bytes) -> str | None:
    try:
        text = candidate.decode("utf-8")
    except UnicodeDecodeError:
        return "candidate is not valid UTF-8"

    frontmatter = extract_frontmatter(text)

    if frontmatter is None:
        return "candidate has no parseable frontmatter block"

    if frontmatter == "MALFORMED" or not isinstance(frontmatter, dict):
        return "candidate frontmatter is malformed"

    try:
        MigratedFrontmatter.model_validate(frontmatter)
    except ValidationError as exc:
        return f"candidate violates the write schema: {exc}"

    return None


def ollama_model(
    prompt: str,
    tag: str = "gemma4:latest",
    timeout: int = 180,
) -> str:
    """Claimant call via shared Ollama client (structured Claim JSON)."""
    from .ollama_client import ollama_model as _ollama

    return _ollama(
        prompt,
        tag,
        timeout,
        response_format=Claim.model_json_schema(),
        temperature=0,
        seed=23,
    )


def atomic_replace(
    path: pathlib.Path,
    *,
    expected: bytes,
    replacement: bytes,
) -> None:
    """Avoid partial writes and refuse to overwrite concurrent changes."""

    if path.read_bytes() != expected:
        raise RuntimeError("source changed while migration was running")

    original_mode = stat.S_IMODE(path.stat().st_mode)
    temporary_path: pathlib.Path | None = None

    try:
        fd, name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".migrate",
            dir=path.parent,
        )
        temporary_path = pathlib.Path(name)

        with os.fdopen(fd, "wb") as file:
            file.write(replacement)
            file.flush()
            os.fsync(file.fileno())

        os.chmod(temporary_path, original_mode)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def migrate_file(
    path,
    root,
    repo,
    model_fn,
    tag: str = "gemma4:latest",
    cap: int = 5,
    version: str = "unknown",
    today: str | None = None,
    write: bool = True,
):
    path = pathlib.Path(path)
    root = pathlib.Path(root)
    repo = pathlib.Path(repo)

    original_bytes = path.read_bytes()

    try:
        original_text = original_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return "ESCALATE", "source is not valid UTF-8; body left untouched"

    existing = extract_frontmatter(original_text)

    if existing == "MALFORMED":
        return "ESCALATE", "existing frontmatter is malformed"

    if existing is not None:
        return (
            "ALREADY-SCHEMA",
            "frontmatter present; v1 migrates Class-A only",
        )

    migration_date = datetime.date.fromisoformat(today) if today else datetime.date.today()

    ground = derive_ground(path, root, repo)
    blockers = ground_blockers(ground)

    # Do not spend model attempts on facts the model cannot repair.
    if blockers:
        return "ESCALATE", "ungrounded identity: " + "; ".join(blockers)

    gaps = sorted(field for field in ("sow", "created", "updated") if getattr(ground, field) is None)

    feedback = ""
    rejection_history: list[str] = []

    for attempt in range(1, cap + 1):
        prompt = prompt_for(
            _body_window(original_text),
            feedback=feedback,
        )

        try:
            raw = model_fn(prompt, tag)
        except Exception as exc:
            rejection = f"{RejectionKind.MODEL}: {exc}"
            rejection_history.append(rejection)
            feedback = f"Previous request failed: {rejection}"
            continue

        claim, claim_error = validate_claim(raw)

        if claim_error is not None:
            rejection_history.append(claim_error)
            feedback = f"Your previous answer was rejected: {claim_error}. Return one corrected JSON object."
            continue

        try:
            frontmatter = assemble_frontmatter(
                ground,
                claim,
                tag=tag,
                version=version,
                today=migration_date,
            )
            candidate = render_candidate(frontmatter, original_bytes)
        except ValidationError as exc:
            rejection = f"{RejectionKind.ASSEMBLY}: {exc}"
            rejection_history.append(rejection)
            feedback = f"Your previous answer was rejected: {rejection}"
            continue

        parse_error = parse_verify(candidate)

        if parse_error is not None:
            rejection = f"{RejectionKind.ASSEMBLY}: {parse_error}"
            rejection_history.append(rejection)
            feedback = f"Your previous answer was rejected: {rejection}"
            continue

        with tempfile.TemporaryDirectory() as temporary_root:
            try:
                relative = path.relative_to(root)
            except ValueError:
                return (
                    "ESCALATE",
                    f"path {path} is outside migration root {root}",
                )

            destination = pathlib.Path(temporary_root) / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(candidate)

            status, gate_feedback = migrate_check(destination)

        if status != "PASS":
            rejection = f"{RejectionKind.GATE}: " + "; ".join(str(item) for item in gate_feedback)
            rejection_history.append(rejection)
            feedback = f"Your previous answer was rejected by the gate: {rejection}. Correct only status and lifecycle."

            # Stop early when the model repeats an identical invalid claim.
            if len(rejection_history) >= 3 and len(set(rejection_history[-3:])) == 1:
                break

            continue

        if write:
            try:
                atomic_replace(
                    path,
                    expected=original_bytes,
                    replacement=candidate,
                )
            except RuntimeError as exc:
                return (
                    "ESCALATE",
                    f"{RejectionKind.CONCURRENT_CHANGE}: {exc}",
                )

        note = f"; UNGROUNDED={','.join(gaps)}" if gaps else ""

        return (
            "MIGRATED",
            f"attempt {attempt}; status={claim.status}{note}",
        )

    last = rejection_history[-1] if rejection_history else "no model response"

    return (
        "ESCALATE",
        f"gate never green after {len(rejection_history)} attempts; last: {last[:300]}",
    )


def migrate_render(path, tag=None, root=None):
    """CLI surface for --migrate.

    Resolves the sows root the way lint mode does (walk up to claude-md/CLAUDE.md)
    so path-derived fields see the real tree, and dates resolve against that
    repo's history.

    Exit codes: 0 = MIGRATED or ALREADY-SCHEMA; 1 = ESCALATE; 2 = missing path.
    """
    from .core import find_canonical_claude_md

    ver = "unknown"
    for package_name in ("zero-employee", "zeo"):
        try:
            from importlib.metadata import version as package_version

            ver = package_version(package_name)
            break
        except Exception:
            continue

    path = pathlib.Path(path)
    if not path.is_file():
        print(f"zeo: path does not exist: {path}")
        return 2

    if root is None:
        canon = find_canonical_claude_md(path)
        root = canon.parent.parent if canon is not None else path.parent

    tag = tag or "gemma4:latest"
    outcome, detail = migrate_file(
        path,
        root,
        root,
        ollama_model,
        tag=tag,
        version=ver,
    )
    print(f"MIGRATE: {outcome}  {path}")
    print(f"  - {detail}")
    if outcome == "MIGRATED":
        print(
            "  - RECONSTRUCTED-UNVERIFIED (doctrine A1.3): model-authored fields "
            "are navigation until a verifier samples this file."
        )
    return 0 if outcome in ("MIGRATED", "ALREADY-SCHEMA") else 1


__all__ = ["LIFECYCLES", "STATUS_RESTING", "STATUS_WORKING", "validate_claim", "Claim"]
