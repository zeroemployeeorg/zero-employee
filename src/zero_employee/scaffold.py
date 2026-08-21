"""Corpus scaffolding, opt-in IDE bridges, and local CLAUDE.md @import resolution.

Self-contained: does not touch doctrine --resync-* machinery or product seats
(zeo-master / zeo-sparring / zeo-stream).
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import pathlib
import re
from collections.abc import Iterable
from importlib import resources

_IMPORT_RE = re.compile(r"""^\s*@import\s+["']([^"']+)["']\s*$""")
_MAX_IMPORT_DEPTH = 16
_TOOL_FLAGS = frozenset({"cursor", "codex", "gemini", "claude", "agents", "all"})
_PERSONAS = ("zeo-architect.md", "zeo-claimant.md", "zeo-verifier.md")
_ZEO_AGENTS = ("zeo-master.md", "zeo-stream.md", "zeo-sparring.md")
# CODEX-SWAP-UX-SOW-1: the `.toml`-shaped equivalent of _ZEO_AGENTS, for Codex's
# `.codex/agents/*.toml` persona convention (RULING-351 approach C, human-in-the-loop
# only -- see install_bridges()'s codex branch for the caveat this install carries).
# Bare stems (no extension): the destination is `.codex/agents/{stem}.toml`, the
# template is `codex-agents/{stem}.toml` -- kept in a dedicated template dir rather
# than sharing `agents/` with the `.md` originals, since the TOML shape/destination
# differ enough that a shared directory would blur `_read_template`'s lookup, not
# clarify it.
_ZEO_AGENTS_CODEX = ("zeo-master", "zeo-stream", "zeo-sparring")

# REPO-EQUIP-SOW-5 (`zeo equip`) ALWAYS tier: (dest-relative-path, template-parts, executable?).
# Matches SOW-1 s1's table exactly. Sourcing of the agent defs is documented in
# scaffold_templates/agents/ and this stream's own SOW filing.
_EQUIP_ALWAYS_FILES: tuple[tuple[str, tuple[str, ...], bool], ...] = (
    (".claude/settings.json", ("claude-settings.json",), False),
    (".claude/hooks/check-trunk-guard.sh", ("claude-hooks", "check-trunk-guard.sh"), True),
    ("CLAUDE.md", ("CLAUDE.md",), False),
    *((f".claude/agents/{name}", ("agents", name), False) for name in _ZEO_AGENTS),
)


def _templates_dir() -> pathlib.Path:
    try:
        root = resources.files("zero_employee").joinpath("scaffold_templates")
        return pathlib.Path(str(root))
    except (ModuleNotFoundError, FileNotFoundError, TypeError, AttributeError, OSError):
        return pathlib.Path(__file__).parent / "scaffold_templates"


def _read_template(*parts: str) -> str:
    path = _templates_dir().joinpath(*parts)
    return path.read_text(encoding="utf-8")


# REPO-EQUIP-SOW-7 (step 3 of REPO-EQUIP-SOW-1): 4-level content precedence for
# `zeo equip`. Level 1 (repo's own existing file) is handled entirely by
# equip_repo()'s never-clobber branch and never reaches this function -- this
# resolves content ONLY for a file that is actually about to be WRITTEN.
_PER_USER_TEMPLATES_SUBDIR = (".config", "zeo", "templates")


def _per_user_templates_dir() -> pathlib.Path:
    return pathlib.Path.home().joinpath(*_PER_USER_TEMPLATES_SUBDIR)


def resolve_template_content(*parts: str) -> tuple[str, str]:
    """Resolve a template's content through the 4-level precedence chain (levels 2-4).

    Level 1 ("repo's own file, already present") is never-clobber and is decided by
    the caller before this is reached -- this function only answers "what content
    should be WRITTEN", checking in order:
      2. $ZEO_TEMPLATES_DIR/<relative-path>  (env var, explicit)
      3. ~/.config/zeo/templates/<relative-path>  (per-user)
      4. packaged scaffold_templates/<relative-path>  (shipped default)
    First match wins. Returns (content, source) where source is one of
    "env", "user", "package" -- for callers/tests that want to assert which
    level actually fired.
    """
    rel = pathlib.PurePath(*parts)

    env_dir = os.environ.get("ZEO_TEMPLATES_DIR")
    if env_dir:
        candidate = pathlib.Path(env_dir).joinpath(rel)
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8"), "env"

    user_candidate = _per_user_templates_dir().joinpath(rel)
    if user_candidate.is_file():
        return user_candidate.read_text(encoding="utf-8"), "user"

    return _read_template(*parts), "package"


def _stamp_content(rel_path: str, content: str) -> str:
    """Insert an UPSTREAM-SHA line, hashing `content` exactly as resolved (pre-stamp).

    Hash scope matches core.py's `resync_apply` convention exactly (core.py:1028-1029):
    sha256 of the raw resolved source text, computed BEFORE any banner/stamp is added --
    never a hash of the final stamped file (that would be circular). This is also why an
    override's stamp differs from the package default's stamp for the same file: they
    hash different `content`, not the same bytes.

    Comment syntax matches `_UPSTREAM_SHA_RE` (core.py:769: `#`, `//`, `/* */`,
    `<!-- -->`, or bare) and is picked per file type:
      - `.sh`               -> `# UPSTREAM-SHA: ...` as line 2, after the shebang.
      - `.md` w/ frontmatter -> `<!-- UPSTREAM-SHA: ... -->` right after the closing `---`.
      - `.md` w/o frontmatter -> `<!-- UPSTREAM-SHA: ... -->` at the very top.
      - `.json`              -> a top-level `"_upstreamSha"` string key carrying the
        marker text (`"_upstreamSha": "UPSTREAM-SHA: <hex>"`). JSON has no comment
        syntax at all, and `.claude/settings.json` is parsed as strict JSON by Claude
        Code itself (confirmed: no JSONC/comment tolerance -- a `#`/`//`/`/* */` line
        would break the live settings file), so this is the only shape that keeps the
        file valid JSON.

        KNOWN, NAMED GAP (not fixed here -- out of scope, see module docstring / SOW):
        `_UPSTREAM_SHA_RE` (core.py:769) is anchored at line-start with `re.M`, allowing
        only a `#`/`//`/`/* */`/`<!--`/bare prefix before `UPSTREAM-SHA:`. Because JSON
        always renders a value as `"key": "..."`,
        the marker text can never itself BEGIN a physical line while staying valid JSON
        (the leading `"key": "` always precedes it on the same line) -- so this stamp is
        real, greppable by a human (`grep UPSTREAM-SHA`), and hashed with the same
        pre-stamp-content scope as every other file, but is NOT currently discoverable
        by `_UPSTREAM_SHA_RE.search()` the way the `.sh`/`.md` stamps are. Fixing that
        needs either a regex change or a settings.json-specific reader in `core.py`,
        which is step 4's territory (`.claude/` visibility to `--resync-check`), not
        this SOW's. Recorded here rather than silently glossed over.
      - anything else        -> `# UPSTREAM-SHA: ...` at the top (default fallback).
    """
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    marker = f"UPSTREAM-SHA: {sha}"

    if rel_path.endswith(".sh"):
        lines = content.splitlines(keepends=True)
        if lines and lines[0].startswith("#!"):
            return lines[0] + f"# {marker}\n" + "".join(lines[1:])
        return f"# {marker}\n" + content

    if rel_path.endswith(".json"):
        data = json.loads(content) if content.strip() else {}
        data["_upstreamSha"] = marker
        return json.dumps(data, indent=2) + "\n"

    if rel_path.endswith(".md"):
        banner = f"<!-- {marker} -->\n"
        if content.startswith("---"):
            try:
                end = content.index("\n---", 3) + 4
                return content[:end] + "\n" + banner + content[end:].lstrip("\n")
            except ValueError:
                pass
        return banner + content

    return f"# {marker}\n" + content


def normalize_tools(tools: Iterable[str] | None) -> set[str]:
    """Expand --all; drop unknowns; return concrete tool set."""
    raw = {str(t).strip().lower() for t in (tools or []) if str(t).strip()}
    if "all" in raw:
        return {"cursor", "codex", "gemini", "claude", "agents"}
    return {t for t in raw if t in _TOOL_FLAGS and t != "all"}


def parse_tool_flags(argv: list[str]) -> set[str]:
    """Collect opt-in bridge flags from a CLI argv slice."""
    selected: set[str] = set()
    if "--cursor" in argv:
        selected.add("cursor")
    if "--codex" in argv:
        selected.add("codex")
    if "--gemini" in argv:
        selected.add("gemini")
    if "--claude" in argv:
        selected.add("claude")
    if "--agents" in argv:
        selected.add("agents")
    if "--all" in argv:
        selected = {"cursor", "codex", "gemini", "claude", "agents"}
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

    if "codex" in tools_set:
        # Codex CLI discovery (developers.openai.com/codex/guides/agents-md, read
        # 2026-08-21): a flat AGENTS.md at the project root (Codex walks the Git
        # root down to cwd, concatenating AGENTS.md/AGENTS.override.md per
        # directory level) -- no frontmatter, no directory-of-rules convention
        # the way Cursor's `.cursor/rules/` is. Same shape as the GEMINI.md
        # bridge: a single symlink deferring to CLAUDE.md, not a content fork.
        agents_md = root / "AGENTS.md"
        act = _symlink_or_fallback(agents_md, "CLAUDE.md", "See CLAUDE.md\n")
        actions.append({"path": "AGENTS.md", "action": act})

        # CODEX-SWAP-UX-SOW-1 (RULING-351 approach C, S8 Amendment 2): the
        # `.codex/agents/*.toml` human-in-the-loop persona layer, generalized from
        # the one real, behaviorally-verified persona this org has ever shipped
        # (org/.codex/agents/zeo-stream.toml, RULING-353). These personas load ONLY
        # under an interactive Codex TUI session where a human explicitly invokes
        # one by name -- NOT under `codex exec`/GitHub Action (approach B), which
        # runs a plain prompt and never reads a persona file at all. Mirrors the
        # `.claude/agents/{name}.md` install-triple pattern immediately below
        # (`agents` tool), same never-clobber write, different destination/format.
        codex_agents_dir = root / ".codex" / "agents"
        codex_agents_dir.mkdir(parents=True, exist_ok=True)
        for stem in _ZEO_AGENTS_CODEX:
            dest = codex_agents_dir / f"{stem}.toml"
            act = _write_if_absent(dest, _read_template("codex-agents", f"{stem}.toml"))
            actions.append({"path": f".codex/agents/{stem}.toml", "action": act})

    if "gemini" in tools_set:
        gemini = root / "GEMINI.md"
        act = _symlink_or_fallback(gemini, "CLAUDE.md", "See CLAUDE.md\n")
        actions.append({"path": "GEMINI.md", "action": act})

    if "claude" in tools_set:
        (root / ".claude").mkdir(parents=True, exist_ok=True)
        settings = root / ".claude" / "settings.json"
        act = _write_if_absent(settings, _read_template("claude-settings.json"))
        actions.append({"path": ".claude/settings.json", "action": act})

        hooks_dir = root / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        guard = hooks_dir / "check-trunk-guard.sh"
        act = _write_if_absent(guard, _read_template("claude-hooks", "check-trunk-guard.sh"))
        if act == "WRITTEN":
            guard.chmod(guard.stat().st_mode | 0o111)
        actions.append({"path": ".claude/hooks/check-trunk-guard.sh", "action": act})

    if "agents" in tools_set:
        agents_dir = root / ".agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        for name in _PERSONAS:
            dest = agents_dir / name
            act = _write_if_absent(dest, _read_template("agents", name))
            actions.append({"path": f".agents/{name}", "action": act})

    return {"root": str(root), "tools": sorted(tools_set), "actions": actions}


def equip_repo(
    root: pathlib.Path | str,
    *,
    force: bool = False,
    diff: bool = False,
) -> dict:
    """Install the ALWAYS-tier `.claude/` + `CLAUDE.md` files into a work repo.

    REPO-EQUIP-SOW-5 (step 2 of REPO-EQUIP-SOW-1's charter): `.claude/settings.json`,
    `.claude/hooks/check-trunk-guard.sh`, `CLAUDE.md`, `.claude/agents/zeo-{master,stream,sparring}.md`.

    Never clobbers an existing file by default (reported as "kept") -- level 1 of
    REPO-EQUIP-SOW-7's precedence chain; a kept file is never read FROM, only checked
    for presence. For a file that IS being written, content is resolved through the
    4-level precedence chain (REPO-EQUIP-SOW-7, step 3 of the charter):
    `$ZEO_TEMPLATES_DIR/...` > `~/.config/zeo/templates/...` > packaged
    `scaffold_templates/...`, via `resolve_template_content()`. Every written file is
    then stamped with `# UPSTREAM-SHA: <sha256 of the resolved content>` (comment
    syntax per file type, see `_stamp_content()`) -- hashing the content actually
    chosen, so a deliberate override's stamp never reads as stale against a default
    it isn't using.

    `force=True` overwrites. `diff=True` writes nothing and instead reports a unified
    diff (or "would create" for a new file) for every target, against the same
    resolved+stamped content that would actually be written.

    Reuses the same never-clobber shape `install_bridges()` already established for
    the `--claude` bridge flag (`_write_if_absent`) rather than a second copy
    mechanism; this function adds the force/diff modes that flag doesn't need.
    """
    root = pathlib.Path(root).resolve()
    actions: list[dict] = []

    for rel_path, template_parts, executable in _EQUIP_ALWAYS_FILES:
        dest = root / rel_path
        existed = dest.exists()

        if diff and not existed:
            actions.append({"path": rel_path, "action": "would-create", "diff": None})
            continue

        if existed and not force and not diff:
            actions.append({"path": rel_path, "action": "kept"})
            continue

        resolved, source = resolve_template_content(*template_parts)
        content = _stamp_content(rel_path, resolved)

        if diff:
            current = dest.read_text(encoding="utf-8")
            if current == content:
                actions.append({"path": rel_path, "action": "unchanged", "diff": None})
                continue
            udiff = "".join(
                difflib.unified_diff(
                    current.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=f"a/{rel_path}",
                    tofile=f"b/{rel_path}",
                )
            )
            actions.append({"path": rel_path, "action": "would-change", "diff": udiff})
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        if executable:
            dest.chmod(dest.stat().st_mode | 0o111)
        actions.append({"path": rel_path, "action": "overwritten" if existed else "written", "source": source})

    return {"root": str(root), "diff": diff, "force": force, "actions": actions}


def init_corpus(root: pathlib.Path | str, tools: Iterable[str] | None = None) -> dict:
    """Scaffold a corpus: marker + IDE entrypoint + dirs; optional bridges."""
    from .hooks import ensure_board_gitignore
    from .intake_authoring import ensure_zeo_gitignore

    root = pathlib.Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    created: list[str] = []

    for d in ("claude-md", "projects", "ruling", "intake"):
        p = root / d
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            created.append(f"{d}/")

    intake_readme = root / "intake" / "README.md"
    if not intake_readme.exists():
        intake_readme.write_text(
            "# Intake\n\n"
            "Frictionless capture of operator intent before project/stream identity is known.\n\n"
            'Create with `zeo intake new` / `zeo intake "..."`.\n'
            "Promote grounded implementation work with "
            "`zeo intake mission` → `zeo intake propose` → `zeo intake promote`.\n\n"
            "Statuses: OPEN | PROMOTED | DUPLICATE | REJECTED | PARKED.\n",
            encoding="utf-8",
        )
        created.append("intake/README.md")

    canon = root / "claude-md" / "CLAUDE.md"
    if not canon.exists():
        canon.write_text(_read_template("claude-md", "CLAUDE.md"), encoding="utf-8")
        created.append("claude-md/CLAUDE.md")

    entry = root / "CLAUDE.md"
    if not entry.exists():
        entry.write_text(_read_template("CLAUDE.md"), encoding="utf-8")
        created.append("CLAUDE.md")

    gitignore_touched = False
    if ensure_board_gitignore(root):
        gitignore_touched = True
    if ensure_zeo_gitignore(root):
        gitignore_touched = True
    if gitignore_touched:
        created.append(".gitignore")

    tools_set = normalize_tools(tools)
    bridges = install_bridges(root, tools_set) if tools_set else {"root": str(root), "tools": [], "actions": []}
    return {"root": str(root), "created": created, "bridges": bridges}


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

    from .sow_authoring import create_sow

    # Greenfield wrapper: ensure project CLAUDE.md, then create via sow new substrate.
    sow_rel = None
    # If an explicit n is requested and that file already exists, stay idempotent.
    from .sow_authoring import canonical_sow_filename

    preview = sow_dir / canonical_sow_filename(stream_name, sow_num, title)
    if preview.exists():
        sow_file = preview
        sow_rel = str(sow_file.relative_to(root))
    else:
        result, err = create_sow(
            root,
            project=project_name,
            stream=stream_name,
            title=title,
            status="DRAFT",
            lifecycle="DESIGN-MEMO",
            done_when="Clear acceptance criteria established",
            restaufwand=1,
            n=sow_num,
            requested_by="unknown - initial scaffold",
            body=(
                f"# SOW-{sow_num:02d}: {title}\n\n## Objective\n\nDefine objective for workstream `{stream_name}`.\n"
            ),
        )
        if result is None:
            raise RuntimeError(f"scaffold SOW create failed: {err}")
        sow_rel = result.path
        sow_file = root / result.path
        created.append(sow_rel)

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
