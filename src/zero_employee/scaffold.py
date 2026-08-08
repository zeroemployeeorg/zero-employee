"""Corpus scaffolding, opt-in IDE bridges, and local CLAUDE.md @import resolution.

Self-contained: does not touch doctrine --resync-* machinery or product seats
(zeo-master / zeo-sparring / zeo-stream).
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
from collections.abc import Iterable
from importlib import resources

_IMPORT_RE = re.compile(r"""^\s*@import\s+["']([^"']+)["']\s*$""")
_MAX_IMPORT_DEPTH = 16
_TOOL_FLAGS = frozenset({"cursor", "gemini", "claude", "agents", "all"})
_PERSONAS = ("zeo-architect.md", "zeo-claimant.md", "zeo-verifier.md")


def _templates_dir() -> pathlib.Path:
    try:
        root = resources.files("zero_employee").joinpath("scaffold_templates")
        return pathlib.Path(str(root))
    except (ModuleNotFoundError, FileNotFoundError, TypeError, AttributeError, OSError):
        return pathlib.Path(__file__).parent / "scaffold_templates"


def _read_template(*parts: str) -> str:
    path = _templates_dir().joinpath(*parts)
    return path.read_text(encoding="utf-8")


def normalize_tools(tools: Iterable[str] | None) -> set[str]:
    """Expand --all; drop unknowns; return concrete tool set."""
    raw = {str(t).strip().lower() for t in (tools or []) if str(t).strip()}
    if "all" in raw:
        return {"cursor", "gemini", "claude", "agents"}
    return {t for t in raw if t in _TOOL_FLAGS and t != "all"}


def parse_tool_flags(argv: list[str]) -> set[str]:
    """Collect opt-in bridge flags from a CLI argv slice."""
    selected: set[str] = set()
    if "--cursor" in argv:
        selected.add("cursor")
    if "--gemini" in argv:
        selected.add("gemini")
    if "--claude" in argv:
        selected.add("claude")
    if "--agents" in argv:
        selected.add("agents")
    if "--all" in argv:
        selected = {"cursor", "gemini", "claude", "agents"}
    return selected


def resolve_imports(
    path: pathlib.Path | str,
    *,
    max_depth: int = _MAX_IMPORT_DEPTH,
    _stack: frozenset[pathlib.Path] | None = None,
    _depth: int = 0,
) -> str:
    """Expand local `@import "rel/path"` lines. No HTTP. Cycle- and depth-safe."""
    path = pathlib.Path(path).resolve()
    stack = _stack or frozenset()
    if path in stack:
        return f"<!-- @import cycle: {path} -->\n"
    if _depth > max_depth:
        return f"<!-- @import depth exceeded at {path} -->\n"
    if not path.is_file():
        return f"<!-- @import missing: {path} -->\n"

    text = path.read_text(encoding="utf-8", errors="replace")
    out: list[str] = []
    next_stack = stack | {path}
    for line in text.splitlines(keepends=True):
        bare = line.removesuffix("\n").removesuffix("\r")
        m = _IMPORT_RE.match(bare)
        if not m:
            out.append(line)
            continue
        target = m.group(1).strip()
        if target.startswith(("http://", "https://")):
            out.append(f"<!-- @import skipped (remote not allowed): {target} -->\n")
            continue
        imported = (path.parent / target).resolve()
        expanded = resolve_imports(
            imported,
            max_depth=max_depth,
            _stack=next_stack,
            _depth=_depth + 1,
        )
        if expanded and not expanded.endswith("\n"):
            expanded += "\n"
        out.append(expanded)
    return "".join(out)


def read_doctrine(path: pathlib.Path | str) -> str:
    """Read a doctrine markdown file with @import expansion."""
    return resolve_imports(path)


def _symlink_or_fallback(link: pathlib.Path, target: str, fallback_text: str) -> str:
    """Create symlink `link` -> `target`, or a small text file. Returns action label."""
    if link.exists() or link.is_symlink():
        return "SKIP"
    try:
        link.symlink_to(target)
        return "SYMLINK"
    except OSError:
        link.write_text(fallback_text, encoding="utf-8")
        return "FILE"


def _write_if_absent(dest: pathlib.Path, content: str) -> str:
    if dest.exists():
        return "SKIP"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return "WRITTEN"


def install_bridges(root: pathlib.Path | str, tools: Iterable[str] | None = None) -> dict:
    """Install selected IDE/agent bridges under `root`. No-op when tools empty."""
    root = pathlib.Path(root).resolve()
    tools_set = normalize_tools(tools)
    actions: list[dict] = []

    if "cursor" in tools_set:
        (root / ".cursor" / "rules").mkdir(parents=True, exist_ok=True)
        mdc = root / ".cursor" / "rules" / "000-governance.mdc"
        content = _read_template("000-governance.mdc")
        # Always refresh the alwaysApply governance bridge (managed template).
        mdc.write_text(content, encoding="utf-8")
        actions.append({"path": str(mdc.relative_to(root)), "action": "WRITTEN"})
        cursorrules = root / ".cursorrules"
        act = _symlink_or_fallback(cursorrules, "CLAUDE.md", "See CLAUDE.md\n")
        actions.append({"path": ".cursorrules", "action": act})

    if "gemini" in tools_set:
        gemini = root / "GEMINI.md"
        act = _symlink_or_fallback(gemini, "CLAUDE.md", "See CLAUDE.md\n")
        actions.append({"path": "GEMINI.md", "action": act})

    if "claude" in tools_set:
        (root / ".claude").mkdir(parents=True, exist_ok=True)
        settings = root / ".claude" / "settings.json"
        act = _write_if_absent(settings, _read_template("claude-settings.json"))
        actions.append({"path": ".claude/settings.json", "action": act})

    if "agents" in tools_set:
        agents_dir = root / ".agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        for name in _PERSONAS:
            dest = agents_dir / name
            act = _write_if_absent(dest, _read_template("agents", name))
            actions.append({"path": f".agents/{name}", "action": act})

    return {"root": str(root), "tools": sorted(tools_set), "actions": actions}


def init_corpus(root: pathlib.Path | str, tools: Iterable[str] | None = None) -> dict:
    """Scaffold a corpus: marker + IDE entrypoint + dirs; optional bridges."""
    root = pathlib.Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    created: list[str] = []

    for d in ("claude-md", "projects", "ruling"):
        p = root / d
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            created.append(f"{d}/")

    canon = root / "claude-md" / "CLAUDE.md"
    if not canon.exists():
        canon.write_text(_read_template("claude-md", "CLAUDE.md"), encoding="utf-8")
        created.append("claude-md/CLAUDE.md")

    entry = root / "CLAUDE.md"
    if not entry.exists():
        entry.write_text(_read_template("CLAUDE.md"), encoding="utf-8")
        created.append("CLAUDE.md")

    tools_set = normalize_tools(tools)
    bridges = install_bridges(root, tools_set) if tools_set else {"root": str(root), "tools": [], "actions": []}
    return {"root": str(root), "created": created, "bridges": bridges}


def _slugify_title(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "initial-workstream-sow"


def scaffold_project_stream(
    root: pathlib.Path | str,
    project_name: str,
    stream_name: str,
    *,
    sow_num: int = 1,
    title: str = "Initial Workstream SOW",
    tools: Iterable[str] | None = None,
) -> dict:
    """Create projects/<project>/CLAUDE.md + Rev-17 SOW; optional bridges on project dir."""
    root = pathlib.Path(root).resolve()
    if not (root / "claude-md" / "CLAUDE.md").is_file():
        raise FileNotFoundError(f"corpus marker missing under {root}: run `zeo init` first (need claude-md/CLAUDE.md)")

    proj_dir = root / "projects" / project_name
    sow_dir = proj_dir / "sow" / stream_name
    sow_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    proj_claude = proj_dir / "CLAUDE.md"
    if not proj_claude.exists():
        body = _read_template("project-CLAUDE.md").replace("{project_name}", project_name)
        proj_claude.write_text(body, encoding="utf-8")
        created.append(str(proj_claude.relative_to(root)))

    today = _dt.datetime.now(_dt.UTC).date().isoformat()
    slug = _slugify_title(title)
    filename = f"{stream_name}-SOW-{sow_num:02d}-{slug}.md"
    sow_file = sow_dir / filename
    if not sow_file.exists():
        # Align field set with reserve_sow_stub (schema_rev 17).
        sow_content = (
            f"---\n"
            f"sow: {stream_name}\n"
            f"n: {sow_num}\n"
            f"schema_rev: 17\n"
            f"project: {project_name}\n"
            f"status: DRAFT\n"
            f"lifecycle: DESIGN-MEMO\n"
            f"created: {today}\n"
            f"updated: {today}\n"
            f"genre: sow\n"
            f'done_when: "Clear acceptance criteria established"\n'
            f"restaufwand: 1\n"
            f"sow_repo: example-org/org\n"
            f"work_repo: example-org/{project_name}\n"
            f"requested_by: unknown - initial scaffold\n"
            f"---\n\n"
            f"# SOW-{sow_num:02d}: {title}\n\n"
            f"## Objective\n\n"
            f"Define objective for workstream `{stream_name}`.\n"
        )
        sow_file.write_text(sow_content, encoding="utf-8")
        created.append(str(sow_file.relative_to(root)))

    tools_set = normalize_tools(tools)
    bridges = install_bridges(proj_dir, tools_set) if tools_set else {"root": str(proj_dir), "tools": [], "actions": []}
    return {
        "root": str(root),
        "project": project_name,
        "stream": stream_name,
        "sow": str(sow_file.relative_to(root)) if sow_file.exists() else None,
        "created": created,
        "bridges": bridges,
    }
