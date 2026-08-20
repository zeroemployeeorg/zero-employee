"""Shared orientation model for humans (`zeo`) and agents (`zeo orient --json`).

One builder, two renderers — humans and agents see the same operational truth.
"""

from __future__ import annotations

import json
import os
import pathlib
from dataclasses import asdict, dataclass, field
from typing import Any

from .core import (
    awaiting_ruling,
    board_rows,
    extract_frontmatter,
    find_canonical_claude_md,
    find_sow_roots,
    flat_dark_files,
    git_ref_state,
    intake_open_rows,
    iter_sow_files,
    locate_stream,
    needs_successor,
    parse_current_rev,
    project_of,
    ungraded_streams,
)
from .scaffold import read_doctrine
from .sow_authoring import resolve_sow_target

PROTOCOL_VERSION = 1

DEFAULT_RULES = [
    "Inspect repository bytes before making implementation claims.",
    "Never author governance YAML manually.",
    "Use zeo intake promote for grounded intake-to-SOW conversion.",
    "Use zeo doctor before considering governed work ready.",
]

DEFAULT_ENTRYPOINTS = {
    "new_work": "zeo new --json",
    "available_work": "zeo work --json",
    "triage": "zeo triage",
    "intakes": "zeo intake open --json",
    "next": "zeo next --json",
    "doctor": "zeo doctor",
}

_WORKING = {"DRAFT", "DESIGN", "PROGRESS"}
_PAUSED = {"HELD", "HANDOVER"}
_BLOCKED = {"BLOCKED"}
_RESTING = {"CLOSEOUT", "SHIPPED", "SUPERSEDED", "VOIDED", "STALE", "FINDING"}


@dataclass
class SuggestedAction:
    label: str
    command: str
    detail: str = ""


@dataclass
class CorpusInfo:
    root: str
    branch: str | None
    head: str | None
    dirty: bool | None
    name: str | None = None


@dataclass
class GovernanceInfo:
    canonical_rev: int | None
    current: bool | None
    hooks_installed: bool
    working_tree_clean: bool | None


@dataclass
class ActiveContext:
    kind: str  # corpus | stream | implementation_repo | none
    project: str | None = None
    stream: str | None = None
    sow_n: int | None = None
    status: str | None = None
    title_or_goal: str | None = None
    restaufwand: int | None = None
    chain_dir: str | None = None
    impl_repo: str | None = None
    associated_corpus: str | None = None


@dataclass
class WorkSummary:
    active_streams: int = 0
    needs_ruling: int = 0
    needs_successor: int = 0
    blocked: int = 0
    paused: int = 0
    open_intakes: int = 0
    dark: int = 0
    resting: int = 0
    total_streams: int = 0


@dataclass
class Orientation:
    protocol_version: int = PROTOCOL_VERSION
    oriented: bool = False
    corpus: CorpusInfo | None = None
    governance: GovernanceInfo | None = None
    role: str = "coding-agent"
    active_context: ActiveContext | None = None
    work: WorkSummary = field(default_factory=WorkSummary)
    warnings: list[str] = field(default_factory=list)
    suggested_actions: list[SuggestedAction] = field(default_factory=list)
    rules: list[str] = field(default_factory=lambda: list(DEFAULT_RULES))
    entrypoints: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_ENTRYPOINTS))


@dataclass
class WorkItem:
    project: str
    stream: str
    sow: str
    status: str
    detail: str = ""
    updated: str = ""


@dataclass
class WorkListing:
    active: list[WorkItem] = field(default_factory=list)
    waiting_on_you: list[WorkItem] = field(default_factory=list)
    recently_touched: list[WorkItem] = field(default_factory=list)
    open_intakes: list[dict[str, str]] = field(default_factory=list)


@dataclass
class NextAction:
    kind: str
    summary: str
    detail: str = ""
    command: str = ""
    stream: str | None = None
    project: str | None = None
    blocked_on: str | None = None
    verify: str | None = None


def discover_corpus_root(
    explicit: str | pathlib.Path | None = None,
    *,
    cwd: pathlib.Path | None = None,
) -> pathlib.Path | None:
    """Resolve corpus root: explicit path, cwd walk-up, or ZEO_SOWS_ROOT."""
    if explicit:
        canon = find_canonical_claude_md(explicit)
        return canon.parent.parent if canon else None
    here = (cwd or pathlib.Path.cwd()).resolve()
    for d in (here, *here.parents):
        if (d / "claude-md" / "CLAUDE.md").is_file():
            return d
    env = os.environ.get("ZEO_SOWS_ROOT")
    if env:
        k = pathlib.Path(env).expanduser().resolve()
        if (k / "claude-md" / "CLAUDE.md").is_file():
            return k
    return None


def _load_files_fm(root: pathlib.Path) -> list[tuple[str, dict]]:
    files_fm: list[tuple[str, dict]] = []
    for f in iter_sow_files(root):
        fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if isinstance(fm, dict):
            files_fm.append((str(f), fm))
    return files_fm


def _status_base(status: str) -> str:
    return str(status or "").upper().split("-SEE")[0]


def build_work_summary(root: pathlib.Path) -> WorkSummary:
    files_fm = _load_files_fm(root)
    rows = board_rows(files_fm)
    aw = awaiting_ruling(files_fm, root=root)
    sow_roots = find_sow_roots(root)
    ug = [u for r in sow_roots for u in ungraded_streams(r)]
    flat = [x for r in sow_roots for x in flat_dark_files(r)]

    def by_status(*want: str) -> list:
        return [r for r in rows if _status_base(r["status"]) in want]

    openq = [r for r in aw if not r.get("answered") and not r.get("resolved")]
    ans, _suppressed = needs_successor(aw, rows)
    needs_master = by_status("RULING-REQUESTED")
    paused = by_status(*_PAUSED)
    blocked = by_status(*_BLOCKED)
    dark_rows = by_status("UNKNOWN")
    resting = by_status(*_RESTING)
    working = by_status(*_WORKING)
    intake_open = intake_open_rows(root)

    return WorkSummary(
        active_streams=len(working),
        needs_ruling=len(needs_master) + len(openq),
        needs_successor=len(ans),
        blocked=len(blocked),
        paused=len(paused),
        open_intakes=len(intake_open),
        dark=len(dark_rows) + len(ug) + len(flat),
        resting=len(resting),
        total_streams=len(rows),
    )


def _hooks_installed(root: pathlib.Path) -> bool:
    return (root / "tools" / "hooks" / "pre-commit").is_file() or (root / ".git" / "hooks" / "pre-commit").is_file()


def _governance(root: pathlib.Path, ref: dict) -> GovernanceInfo:
    canon = find_canonical_claude_md(root)
    rev = None
    if canon and canon.is_file():
        try:
            rev = parse_current_rev(read_doctrine(canon))
        except Exception:
            rev = parse_current_rev(canon.read_text(encoding="utf-8", errors="replace"))
    dirty = ref.get("dirty")
    return GovernanceInfo(
        canonical_rev=rev,
        current=True if rev is not None else None,
        hooks_installed=_hooks_installed(root),
        working_tree_clean=(not dirty) if dirty is not None else None,
    )


def _corpus_name(root: pathlib.Path) -> str | None:
    """Best-effort display name: remote origin or directory name."""
    import subprocess

    r = subprocess.run(
        ["git", "-C", str(root), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
    )
    if r.returncode == 0 and r.stdout.strip():
        url = r.stdout.strip().rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        # github.com/org/repo or git@github.com:org/repo
        if ":" in url.split("@")[-1]:
            # ssh form
            tail = url.split(":")[-1]
        else:
            tail = "/".join(url.split("/")[-2:])
        if tail and "/" in tail:
            return tail
    return root.name


def _try_infer_stream_context(
    root: pathlib.Path,
    cwd: pathlib.Path,
    stream: str | None = None,
) -> ActiveContext | None:
    if stream:
        try:
            proj, strm, chain = resolve_sow_target(root, stream=stream, cwd=cwd)
        except ValueError:
            L = locate_stream(root, stream)
            if not L.get("chain_dir"):
                return None
            proj = L.get("project")
            strm = stream
            chain = pathlib.Path(L["chain_dir"])
        else:
            pass
        return _stream_context(root, proj, strm, chain)

    try:
        proj, strm, chain = resolve_sow_target(root, cwd=cwd)
    except ValueError:
        return ActiveContext(kind="corpus")
    return _stream_context(root, proj, strm, chain)


def _stream_context(
    root: pathlib.Path,
    project: str | None,
    stream: str,
    chain: pathlib.Path,
) -> ActiveContext:
    L = locate_stream(root, stream)
    latest = L.get("latest") or {}
    goal = None
    rest = None
    # Richer frontmatter from latest file
    if latest.get("file") and chain.is_dir():
        fp = chain / latest["file"]
        if fp.is_file():
            fm = extract_frontmatter(fp.read_text(encoding="utf-8", errors="replace"))
            if isinstance(fm, dict):
                goal = str(fm.get("done_when") or fm.get("title") or "") or None
                try:
                    rest = int(fm["restaufwand"]) if fm.get("restaufwand") is not None else None
                except (TypeError, ValueError):
                    rest = None
                if not project:
                    project = str(fm.get("project") or project or "") or None
    n = latest.get("n")
    try:
        n_int = int(n) if n is not None else None
    except (TypeError, ValueError):
        n_int = None
    return ActiveContext(
        kind="stream",
        project=project,
        stream=stream,
        sow_n=n_int,
        status=str(latest.get("status") or "") or None,
        title_or_goal=goal,
        restaufwand=rest,
        chain_dir=str(chain),
    )


def _impl_repo_context(
    cwd: pathlib.Path,
    *,
    corpus: pathlib.Path | None,
) -> ActiveContext | None:
    """Best-effort: cwd is an implementation repo associated with a corpus."""
    if corpus is not None:
        try:
            cwd.relative_to(corpus)
            return None  # inside corpus already
        except ValueError:
            pass

    associated = corpus
    if associated is None:
        # Sibling heuristic: parent/<something> with claude-md
        parent = cwd.parent
        for candidate in (parent / "org", parent / "sows", parent / "corpus", *parent.iterdir()):
            if candidate.is_dir() and (candidate / "claude-md" / "CLAUDE.md").is_file():
                associated = candidate.resolve()
                break

    open_work: list[str] = []
    if associated is not None:
        repo_name = cwd.name
        for path, fm in _load_files_fm(associated):
            work_repo = str(fm.get("work_repo") or "")
            if repo_name and repo_name in work_repo:
                sid = str(fm.get("sow") or pathlib.Path(path).parent.name)
                status = _status_base(str(fm.get("status") or ""))
                if status in _WORKING | {"RULING-REQUESTED"} | _BLOCKED | _PAUSED:
                    proj = project_of(path, associated) or "-"
                    open_work.append(f"{proj}/{sid}")
        open_work = sorted(set(open_work))

    return ActiveContext(
        kind="implementation_repo",
        impl_repo=cwd.name,
        associated_corpus=str(associated) if associated else None,
        title_or_goal="; ".join(open_work[:8]) if open_work else None,
    )


def build_orientation(
    *,
    root: pathlib.Path | None = None,
    cwd: pathlib.Path | None = None,
    stream: str | None = None,
    role: str = "coding-agent",
) -> Orientation:
    cwd = (cwd or pathlib.Path.cwd()).resolve()
    root = root.resolve() if root is not None else discover_corpus_root(cwd=cwd)

    if root is None:
        ctx = _impl_repo_context(cwd, corpus=None)
        warnings = ["Not inside a ZEO corpus (no claude-md/CLAUDE.md found)."]
        actions = [
            SuggestedAction("Initialize a corpus here", "zeo init", "Creates doctrine + intake/"),
            SuggestedAction("Show help", "zeo help"),
            SuggestedAction("Agent briefing", "zeo orient --json"),
        ]
        if ctx and ctx.associated_corpus:
            warnings.append(f"Possible associated corpus: {ctx.associated_corpus}")
            actions.insert(
                0,
                SuggestedAction(
                    "Orient from associated corpus",
                    f"ZEO_SOWS_ROOT={ctx.associated_corpus} zeo orient --json",
                ),
            )
        return Orientation(
            oriented=False,
            role=role,
            active_context=ctx,
            warnings=warnings,
            suggested_actions=actions,
            entrypoints={
                **DEFAULT_ENTRYPOINTS,
                "init": "zeo init",
            },
        )

    ref = git_ref_state(root)
    gov = _governance(root, ref)
    corpus = CorpusInfo(
        root=str(root),
        branch=ref.get("ref"),
        head=ref.get("sha"),
        dirty=ref.get("dirty"),
        name=_corpus_name(root),
    )
    work = build_work_summary(root)
    ctx = _try_infer_stream_context(root, cwd, stream=stream)
    if ctx is None or ctx.kind == "corpus":
        # Outside corpus tree but ZEO_SOWS_ROOT / walk found root from elsewhere
        try:
            cwd.relative_to(root)
        except ValueError:
            impl = _impl_repo_context(cwd, corpus=root)
            if impl is not None:
                ctx = impl

    warnings: list[str] = []
    if gov.hooks_installed is False:
        warnings.append("Hooks not installed — run: zeo hooks install")
    if work.dark:
        warnings.append(f"{work.dark} dark/pre-schema item(s) invisible to the board")
    if corpus.dirty:
        warnings.append("Working tree has uncommitted changes")

    actions = [
        SuggestedAction("Start something new", "zeo new"),
        SuggestedAction("Continue existing work", "zeo work"),
        SuggestedAction("See what needs attention", "zeo triage"),
        SuggestedAction("Capture an idea", "zeo intake new"),
        SuggestedAction("Check this repository", "zeo doctor"),
    ]
    if ctx and ctx.kind == "stream" and ctx.stream:
        actions.insert(
            0,
            SuggestedAction(
                f"Continue {ctx.stream}",
                f"zeo work {ctx.stream}",
                detail=f"SOW-{ctx.sow_n} · {ctx.status}" if ctx.sow_n else "",
            ),
        )
        actions.append(
            SuggestedAction(
                "Agent stream briefing",
                f"zeo orient --stream {ctx.stream} --json",
            )
        )

    return Orientation(
        oriented=True,
        corpus=corpus,
        governance=gov,
        role=role,
        active_context=ctx,
        work=work,
        warnings=warnings,
        suggested_actions=actions,
        rules=list(DEFAULT_RULES),
        entrypoints=dict(DEFAULT_ENTRYPOINTS),
    )


def orientation_to_dict(o: Orientation) -> dict[str, Any]:
    def _clean(obj: Any) -> Any:
        if hasattr(obj, "__dataclass_fields__"):
            return {k: _clean(v) for k, v in asdict(obj).items()}
        if isinstance(obj, list):
            return [_clean(x) for x in obj]
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        return obj

    return _clean(o)


def render_orientation_human(o: Orientation) -> str:
    lines: list[str] = []
    lines.append("ZEO · Zero-Employee Organization")
    lines.append("")

    if not o.oriented:
        lines.append("Not oriented")
        for w in o.warnings:
            lines.append(f"  {w}")
        if o.active_context and o.active_context.kind == "implementation_repo":
            lines.append("")
            lines.append("You appear to be in an implementation repo:")
            lines.append(f"  {o.active_context.impl_repo}")
            if o.active_context.associated_corpus:
                lines.append(f"  Possible corpus: {o.active_context.associated_corpus}")
            if o.active_context.title_or_goal:
                lines.append(f"  Open governed work: {o.active_context.title_or_goal}")
        lines.append("")
        lines.append("What do you want to do?")
        lines.append("")
        for a in o.suggested_actions:
            lines.append(f"  {a.label}")
            lines.append(f"    {a.command}")
            lines.append("")
        lines.append("More commands:")
        lines.append("  zeo help")
        return "\n".join(lines).rstrip() + "\n"

    assert o.corpus is not None and o.governance is not None
    c, g, w = o.corpus, o.governance, o.work

    lines.append("Corpus")
    lines.append(f"  {c.name or pathlib.Path(c.root).name}")
    if c.branch or c.head:
        dirty = ""
        if c.dirty:
            dirty = " (dirty)"
        elif c.dirty is False:
            dirty = ""
        lines.append(f"  {c.branch or 'DETACHED'} @ {c.head or '?'}{dirty}")
    else:
        lines.append(f"  {c.root}")
    rev = f"Rev {g.canonical_rev}" if g.canonical_rev is not None else "Rev unknown"
    lines.append(f"  {'✓' if g.current else '?'} governance current ({rev})")
    lines.append(f"  {'✓' if g.hooks_installed else '○'} hooks {'installed' if g.hooks_installed else 'not installed'}")
    if g.working_tree_clean is True:
        lines.append("  ✓ working tree clean")
    elif g.working_tree_clean is False:
        lines.append("  ○ working tree dirty")
    lines.append("")

    ctx = o.active_context
    if ctx and ctx.kind == "stream":
        lines.append("You are inside:")
        lines.append(f"  project: {ctx.project or '?'}")
        lines.append(f"  stream: {ctx.stream}")
        lines.append("")
        lines.append("Current work:")
        sow = f"SOW-{ctx.sow_n}" if ctx.sow_n is not None else "SOW-?"
        lines.append(f"  {sow} · {ctx.status or '?'}")
        if ctx.title_or_goal:
            lines.append("")
            lines.append("Goal:")
            lines.append(f"  {ctx.title_or_goal}")
        if ctx.restaufwand is not None:
            lines.append(f"  restaufwand: {ctx.restaufwand}")
        lines.append("")
    elif ctx and ctx.kind == "implementation_repo":
        lines.append("You are in implementation repo:")
        lines.append(f"  {ctx.impl_repo}")
        if ctx.associated_corpus:
            lines.append("")
            lines.append("Associated corpus:")
            lines.append(f"  {ctx.associated_corpus}")
        if ctx.title_or_goal:
            lines.append("")
            lines.append("Open governed work touching this repo:")
            for item in ctx.title_or_goal.split("; "):
                lines.append(f"  {item}")
        lines.append("")

    lines.append("Work")
    lines.append(f"  {w.active_streams} active streams")
    attention = w.needs_ruling + w.needs_successor
    lines.append(f"  {attention} need a ruling / successor")
    lines.append(f"  {w.blocked} blocked")
    lines.append(f"  {w.paused} paused")
    lines.append(f"  {w.open_intakes} open intakes")
    if w.dark:
        lines.append(f"  {w.dark} dark (pre-schema)")
    lines.append("")

    if o.warnings:
        lines.append("Warnings")
        for warn in o.warnings:
            lines.append(f"  ⚠ {warn}")
        lines.append("")

    lines.append("What do you want to do?")
    lines.append("")
    # Deduplicate by command for display
    seen: set[str] = set()
    for a in o.suggested_actions:
        if a.command in seen:
            continue
        seen.add(a.command)
        lines.append(f"  {a.label}")
        lines.append(f"    {a.command}")
        if a.detail:
            lines.append(f"    ({a.detail})")
        lines.append("")

    lines.append("Agent?")
    lines.append("  Run: zeo orient --json")
    lines.append("")
    lines.append("More commands:")
    lines.append("  zeo help")
    return "\n".join(lines).rstrip() + "\n"


def build_work_listing(root: pathlib.Path) -> WorkListing:
    files_fm = _load_files_fm(root)
    rows = board_rows(files_fm)
    aw = awaiting_ruling(files_fm, root=root)
    ans, _ = needs_successor(aw, rows)
    openq = [r for r in aw if not r.get("answered") and not r.get("resolved")]

    active: list[WorkItem] = []
    waiting: list[WorkItem] = []
    for r in rows:
        st = _status_base(r["status"])
        item = WorkItem(
            project=str(r.get("project") or "-"),
            stream=str(r["stream"]),
            sow=f"SOW-{r['latest']}",
            status=st,
            updated=str(r.get("updated") or ""),
        )
        if st in _WORKING:
            active.append(item)
        if st == "RULING-REQUESTED" or st in _BLOCKED:
            detail = "ruling requested" if st == "RULING-REQUESTED" else "blocked"
            waiting.append(
                WorkItem(
                    project=item.project,
                    stream=item.stream,
                    sow=item.sow,
                    status=st,
                    detail=detail,
                    updated=item.updated,
                )
            )

    for q in openq:
        waiting.append(
            WorkItem(
                project="-",
                stream=str(q["stream"]),
                sow=f"SOW-{q['rev']}",
                status="OPEN-QUESTION",
                detail="open question",
                updated=str(q.get("updated") or ""),
            )
        )
    for r in ans:
        nnn, upd = r["answered"]
        waiting.append(
            WorkItem(
                project="-",
                stream=str(r["stream"]),
                sow=f"SOW-{r['rev']}",
                status="NEEDS-SUCCESSOR",
                detail=f"ruled by RULING-{nnn}",
                updated=str(upd),
            )
        )

    # Recently touched: sort by updated date descending (ISO dates sort lexicographically)
    recent_src = sorted(rows, key=lambda r: str(r.get("updated") or ""), reverse=True)
    recently = [
        WorkItem(
            project=str(r.get("project") or "-"),
            stream=str(r["stream"]),
            sow=f"SOW-{r['latest']}",
            status=_status_base(r["status"]),
            updated=str(r.get("updated") or ""),
        )
        for r in recent_src[:8]
        if _status_base(r["status"]) not in _RESTING
    ]

    intakes = [
        {
            "id": str(x["intake"]),
            "project": str(x.get("project") or "-"),
            "created": str(x.get("created") or ""),
            "file": str(x.get("file") or ""),
        }
        for x in intake_open_rows(root)
    ]

    return WorkListing(
        active=active,
        waiting_on_you=waiting,
        recently_touched=recently,
        open_intakes=intakes,
    )


def render_work_listing_human(listing: WorkListing) -> str:
    lines = ["Work available to you", ""]

    def section(title: str, items: list[WorkItem]) -> None:
        lines.append(title)
        if not items:
            lines.append("  (none)")
        else:
            for it in items:
                left = f"{it.project}/{it.stream}"
                mid = f"{it.sow}  {it.status}"
                extra = f"  {it.detail}" if it.detail else ""
                when = f"  {it.updated}" if it.updated and title.startswith("RECENT") else ""
                lines.append(f"  {left:<40} {mid}{extra}{when}")
        lines.append("")

    section("ACTIVE", listing.active)
    section("WAITING ON YOU", listing.waiting_on_you)
    section("RECENTLY TOUCHED", listing.recently_touched)

    lines.append("OPEN INTAKES")
    if not listing.open_intakes:
        lines.append("  (none)")
    else:
        lines.append(f"  {len(listing.open_intakes)} waiting for investigation")
        for x in listing.open_intakes[:12]:
            lines.append(f"  {x['id']}  ({x['project']}, filed {x['created']})")
    lines.append("")
    lines.append("Use:")
    lines.append("  zeo work <stream>")
    lines.append("  zeo intake open")
    lines.append("  zeo triage")
    return "\n".join(lines).rstrip() + "\n"


def build_stream_detail(root: pathlib.Path, stream: str) -> dict[str, Any]:
    L = locate_stream(root, stream)
    if not L.get("chain_dir"):
        return {"found": False, "stream": stream, "error": "stream not found"}

    chain = pathlib.Path(L["chain_dir"])
    project = L.get("project")
    latest = L.get("latest") or {}
    files_fm = _load_files_fm(root)
    aw = [r for r in awaiting_ruling(files_fm, root=root) if str(r["stream"]).lower() == stream.lower()]
    openq = [r for r in aw if not r.get("answered") and not r.get("resolved")]

    goal = None
    rest = None
    requested_by = None
    next_acts: list[str] = []
    if latest.get("file"):
        fp = chain / latest["file"]
        if fp.is_file():
            fm = extract_frontmatter(fp.read_text(encoding="utf-8", errors="replace"))
            if isinstance(fm, dict):
                goal = str(fm.get("done_when") or "") or None
                requested_by = str(fm.get("requested_by") or "") or None
                try:
                    rest = int(fm["restaufwand"]) if fm.get("restaufwand") is not None else None
                except (TypeError, ValueError):
                    rest = None
                nta = fm.get("next_three_acts")
                if isinstance(nta, list):
                    next_acts = [str(x) for x in nta]
                elif isinstance(nta, str) and nta.strip():
                    next_acts = [nta.strip()]
                if not project:
                    project = str(fm.get("project") or "") or None

    status = str(latest.get("status") or "")
    next_cmd = f"zeo work {stream}"
    next_human = f"Continue SOW-{latest.get('n')}" if latest.get("n") else "Inspect stream"
    if openq:
        next_human = f"Address open ruling request on SOW-{openq[0]['rev']}"
        next_cmd = f"zeo inbox {stream}" if False else f"zeo --inbox {stream}"
    elif next_acts:
        next_human = next_acts[0]

    return {
        "found": True,
        "project": project,
        "stream": stream,
        "chain_dir": str(chain),
        "latest": {
            "n": latest.get("n"),
            "status": status,
            "file": latest.get("file"),
            "rev": latest.get("rev"),
        },
        "goal": goal,
        "restaufwand": rest,
        "requested_by": requested_by,
        "open_questions": len(openq),
        "answered_pending": len([r for r in aw if r.get("answered")]),
        "next_three_acts": next_acts,
        "next": {"summary": next_human, "command": next_cmd},
        "agent_command": f"zeo orient --stream {stream} --json",
    }


def render_stream_detail_human(d: dict[str, Any]) -> str:
    if not d.get("found"):
        return f"Stream not found: {d.get('stream')}\n"

    lines = [
        f"{d.get('project') or '?'} / {d['stream']}",
        "",
        "Latest:",
        f"  SOW-{d['latest'].get('n')} · {d['latest'].get('status') or '?'}",
    ]
    if d.get("goal"):
        lines += ["", "Goal:", f"  {d['goal']}"]
    lines += ["", "State:", f"  {d['latest'].get('status') or '?'}"]
    if d.get("restaufwand") is not None:
        lines.append(f"  restaufwand: {d['restaufwand']}")
    if d.get("requested_by"):
        lines += ["", "Requested by:", f"  {d['requested_by']}"]
    lines += [
        "",
        "Relevant:",
        f"  {d.get('open_questions', 0)} open questions",
        f"  {d.get('answered_pending', 0)} answered awaiting successor",
        "",
        "Next:",
        f"  {d['next']['summary']}",
        "",
        "Agent:",
        f"  {d['agent_command']}",
        "",
        "Commands:",
        f"  zeo work {d['stream']}",
        "  zeo doctor .",
        "  zeo digest",
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_next_action(
    *,
    root: pathlib.Path | None = None,
    cwd: pathlib.Path | None = None,
    stream: str | None = None,
) -> NextAction:
    """Highest-priority legitimate next action.

    Priority:
      1. Inside a stream → continue SOW / address inbox / waiting on ruling
      2. Corpus triage → NEEDS MASTER → NEEDS SUCCESSOR → INTAKE → BLOCKED → DARK
      3. Else → suggest zeo new
    """
    cwd = (cwd or pathlib.Path.cwd()).resolve()
    root = root.resolve() if root is not None else discover_corpus_root(cwd=cwd)
    if root is None:
        return NextAction(
            kind="init",
            summary="Initialize a ZEO corpus",
            detail="No corpus found from this directory.",
            command="zeo init",
        )

    ctx = _try_infer_stream_context(root, cwd, stream=stream)
    if ctx and ctx.kind == "stream" and ctx.stream:
        detail = build_stream_detail(root, ctx.stream)
        files_fm = _load_files_fm(root)
        aw = [r for r in awaiting_ruling(files_fm, root=root) if str(r["stream"]).lower() == ctx.stream.lower()]
        openq = [r for r in aw if not r.get("answered") and not r.get("resolved")]
        status = _status_base(str(detail.get("latest", {}).get("status") or ctx.status or ""))
        if status in _BLOCKED or openq:
            blocked = f"open question on SOW-{openq[0]['rev']}" if openq else "BLOCKED status"
            return NextAction(
                kind="blocked",
                summary="Nothing executable in this stream.",
                detail=f"Waiting for: {blocked}",
                command=f"zeo --inbox {ctx.stream}",
                stream=ctx.stream,
                project=ctx.project,
                blocked_on=blocked,
            )
        acts = detail.get("next_three_acts") or []
        summary = acts[0] if acts else detail.get("next", {}).get("summary") or "Continue current SOW"
        return NextAction(
            kind="continue_stream",
            summary=summary,
            detail=f"Current: {ctx.project}/{ctx.stream} SOW-{ctx.sow_n} · {ctx.status}",
            command=f"zeo work {ctx.stream}",
            stream=ctx.stream,
            project=ctx.project,
            verify="zeo doctor .",
        )

    # Corpus-level triage priority
    files_fm = _load_files_fm(root)
    rows = board_rows(files_fm)
    aw = awaiting_ruling(files_fm, root=root)
    openq = [r for r in aw if not r.get("answered") and not r.get("resolved")]
    ans, _ = needs_successor(aw, rows)

    def by_status(*want: str) -> list:
        return [r for r in rows if _status_base(r["status"]) in want]

    needs_master = by_status("RULING-REQUESTED")
    if needs_master or openq:
        if openq:
            q = openq[0]
            return NextAction(
                kind="ruling",
                summary=f"Ruling owed: {q['stream']} SOW-{q['rev']}",
                detail="NEEDS MASTER — a ruling is owed",
                command=f"zeo --inbox {q['stream']}",
                stream=str(q["stream"]),
            )
        r = needs_master[0]
        return NextAction(
            kind="ruling",
            summary=f"Ruling owed: {r['project']}/{r['stream']} SOW-{r['latest']}",
            detail="NEEDS MASTER",
            command=f"zeo --inbox {r['stream']}",
            stream=str(r["stream"]),
            project=str(r.get("project")),
        )

    if ans:
        r = ans[0]
        nnn, _upd = r["answered"]
        return NextAction(
            kind="successor",
            summary=f"File successor for {r['stream']} SOW-{r['rev']}",
            detail=f"Ruled by RULING-{nnn}; needs a successor SOW",
            command=f"zeo work {r['stream']}",
            stream=str(r["stream"]),
        )

    intakes = intake_open_rows(root)
    if intakes:
        x = intakes[0]
        path = f"intake/{x['file']}"
        return NextAction(
            kind="intake",
            summary=f"Investigate intake: {x['intake']}",
            detail="OPEN, no grounded proposal",
            command=f"zeo intake mission {path} --json",
            project=str(x.get("project") or "") or None,
        )

    blocked = by_status(*_BLOCKED)
    if blocked:
        r = blocked[0]
        return NextAction(
            kind="blocked",
            summary=f"Blocked: {r['project']}/{r['stream']}",
            detail="External obstruction — nothing executable until unblocked",
            command=f"zeo work {r['stream']}",
            stream=str(r["stream"]),
            project=str(r.get("project")),
            blocked_on="BLOCKED",
        )

    sow_roots = find_sow_roots(root)
    ug = [u for r in sow_roots for u in ungraded_streams(r)]
    flat = [x for r in sow_roots for x in flat_dark_files(r)]
    if ug or flat:
        target = ug[0] if ug else flat[0]
        label = f"{target.get('project')}/{target.get('stream') or target.get('file')}"
        return NextAction(
            kind="dark",
            summary=f"Migrate dark work: {label}",
            detail="Pre-schema / invisible to the board",
            command="zeo triage",
        )

    working = by_status(*_WORKING)
    if working:
        r = working[0]
        return NextAction(
            kind="continue_stream",
            summary=f"Continue {r['project']}/{r['stream']} SOW-{r['latest']}",
            detail=str(r.get("status") or ""),
            command=f"zeo work {r['stream']}",
            stream=str(r["stream"]),
            project=str(r.get("project")),
        )

    return NextAction(
        kind="new",
        summary="Nothing needs attention — start something new",
        detail="Corpus is quiet.",
        command="zeo new",
    )


def render_next_action_human(n: NextAction) -> str:
    lines = [
        "Highest-priority actionable item:",
        "",
        f"  {n.summary}",
    ]
    if n.detail:
        lines += ["", "  State:", f"    {n.detail}"]
    if n.blocked_on:
        lines += ["", "  Waiting for:", f"    {n.blocked_on}"]
    if n.command:
        lines += ["", "  Next:", f"    {n.command}"]
    if n.verify:
        lines += ["", "  Verify with:", f"    {n.verify}"]
    if n.kind == "blocked" and n.stream:
        lines += ["", "  Suggested:", f"    zeo --inbox {n.stream}"]
    return "\n".join(lines).rstrip() + "\n"


def next_action_to_dict(n: NextAction) -> dict[str, Any]:
    return asdict(n)


NEW_CHOICES = [
    {
        "id": 1,
        "key": "intake",
        "label": "An idea or problem that still needs investigation",
        "artifact": "Intake",
        "command": "zeo intake new",
        "command_json": "zeo intake new --json",
    },
    {
        "id": 2,
        "key": "sow",
        "label": "Work whose scope and destination are already known",
        "artifact": "SOW",
        "command": 'zeo sow new <project> <stream> --title "..."',
        "command_json": 'zeo sow new <project> <stream> --title "..." --json',
    },
    {
        "id": 3,
        "key": "project",
        "label": "A new project/workstream",
        "artifact": "Project + first SOW",
        "command": "zeo scaffold <project> <stream> [n] [title]",
        "command_json": "zeo scaffold <project> <stream>",
    },
]


def render_new_menu_human() -> str:
    lines = [
        "What are you starting?",
        "",
    ]
    for c in NEW_CHOICES:
        lines.append(f"  {c['id']}. {c['label']}")
        lines.append(f"     → {c['artifact']}")
        lines.append("")
    lines.append("Choose 1–3, or run the concrete command directly.")
    lines.append("Agents: zeo new --json")
    return "\n".join(lines).rstrip() + "\n"


def new_choices_to_dict() -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "prompt": "What are you starting?",
        "choices": NEW_CHOICES,
    }


HELP_TOPICS: dict[str, str] = {
    "intake": """ZEO HELP · intake

Capture intent before project/stream identity is known.

  zeo intake "idea title"          Create OPEN intake (no YAML)
  zeo intake new                   Create with prompts / --spec
  zeo intake open [--json]         List OPEN intakes
  zeo intake mission PATH --json   Investigation briefing
  zeo intake propose PATH --spec   Submit grounded proposal
  zeo intake promote PATH          Materialize SOW from proposal

See also: zeo new  ·  zeo help --all
""",
    "sow": """ZEO HELP · sow

Govern work after identity (project + stream) is known.

  zeo sow new <project> <stream> --title "..."
  zeo sow set|add|remove FILE KEY VALUE
  zeo sow draft <project> <stream> --title "..."
  zeo sow from-intake FILE          Alias for intake promote
  zeo scaffold <project> <stream>  Project CLAUDE.md + first SOW

See also: zeo new  ·  zeo doctor  ·  zeo help status  ·  zeo help --all
""",
    "rulings": """ZEO HELP · rulings

  zeo --inbox <stream>             Open questions + answering rulings + proactive binding rulings
  zeo mint ruling                  Next free org-scope ruling id
  zeo index rulings                Regenerate ruling-index.md
  zeo --mint ruling                Legacy flag form

Legacy aliases remain supported.

See also: zeo triage  ·  zeo help --all
""",
    "doctrine": """ZEO HELP · doctrine

  zeo <path>                       Lint SOW/ruling against canonical doctrine
  zeo --resync-check <upstream>    Inherited doctrine currency
  zeo --resync-apply <upstream>    Re-derive inherited files
  zeo --migrate <file>             Pre-schema → schema frontmatter

Canonical marker: claude-md/CLAUDE.md

See also: zeo orient --json  ·  zeo help --all
""",
    "corpus": """ZEO HELP · corpus

  zeo init [path]                  Scaffold corpus marker + dirs
  zeo hooks install                Install gate + session-start hooks
  zeo board                        Write local STATE.md
  zeo index streams                Write stream-index.md
  zeo digest                       Session summary

Discovery: walk up for claude-md/CLAUDE.md, or set ZEO_SOWS_ROOT.

See also: zeo  ·  zeo help --all
""",
    "hooks": """ZEO HELP · hooks

  zeo hooks install [path]         Write thin stubs + .git/hooks/pre-commit
  zeo hooks session-start          Orientation + local board refresh
  zeo hooks pre-commit             Commit gate
  zeo hooks stop                   Session cost + uncommitted advisory
  zeo hooks pretooluse-git         Advisory before git commit/push

See also: zeo orient  ·  zeo help --all
""",
    "cost": """ZEO HELP · cost

  zeo --kosten [stream]            Corpus artifact token estimate
  zeo --repo-cost [path]           Ahead-of-work repo estimate
  zeo --session-cost               Post-run transcript/log cost
  zeo --json                       Machine-readable for cost verbs

See also: zeo help --all
""",
    "index": """ZEO HELP · index

  zeo index streams                stream-index.md (id → path)
  zeo index rulings                ruling-index.md
  zeo --stream-index               Legacy alias
  zeo --ruling-index               Legacy alias

Indexes are navigation, not evidence. Legacy aliases remain supported.
""",
    "status": """ZEO HELP · status

The `status:` field names WHERE THE WORK IS. 13 values (schemas/common.py
STATUS_ENUM), split into two families:

WORKING — owed attention, may never be a chain's last word at a paused commit:
  DRAFT             Not yet real work — a placeholder or stub.
  DESIGN            Root-causing / proposing a shape; nothing built yet.
  PROGRESS          Actively being built.
  RULING-REQUESTED  A fork is posed to Master/Sparring; stream keeps working
                     in any direction the open question doesn't fence.

RESTING — terminal/done, not a stream's last WORKING word:
  HELD              A *chosen* wait on sequencing (e.g. "behind D1's merge").
                     Healthy, not stuck — distinct from BLOCKED.
  BLOCKED           An *external obstruction* (e.g. a foreign gate is red).
                     Needs attention, unlike HELD.
  SHIPPED           Code/work landed AND was verified (prefer this over "done").
  FINDING           A verified *observation* from a RECON, not a landed change.
  CLOSEOUT          The stream itself wound down — may carry no code of its
                     own (e.g. a stream that only ever produced findings).
  HANDOVER          Waiting to be picked up by a successor.
  SUPERSEDED        Superseded by a later rev or a different chain.
  VOIDED            Retracted; no longer operative.
  STALE             Aged out without a resolving action.

RESTING is not monolithic. HELD, HANDOVER, and BLOCKED are RESTING by the
schema's crude WORKING/RESTING binary, but all three still want eyes —
"paused," not "done." `zeo --triage` already draws the finer, operationally
correct line in production: it buckets HELD/HANDOVER as PAUSED and BLOCKED
as BLOCKED, separately from a true RESTING bucket (CLOSEOUT, SHIPPED,
SUPERSEDED, VOIDED, STALE, FINDING). This page teaches the SCHEMA's own
two-way split; `zeo --triage` (or `zeo triage`) is the more accurate
operational read of which streams actually need a look today — run that,
not this, when deciding whom to help next.

See also: zeo triage  ·  zeo help sow  ·  zeo help --all
""",
}


def render_help_root() -> str:
    return """ZEO HELP

Getting started
  zeo                 Orientation
  zeo new             Start work or capture an idea
  zeo work            Continue governed work
  zeo triage          See where intervention is needed
  zeo doctor          Check readiness
  zeo orient --json   Agent orientation
  zeo next            What should I do now?

Workflows
  zeo help intake
  zeo help sow
  zeo help status
  zeo help rulings
  zeo help doctrine

Administration
  zeo help corpus
  zeo help hooks
  zeo help cost
  zeo help index

All commands
  zeo help --all

Legacy flag forms (--board, --triage, …) remain supported.
"""


def dumps_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=False) + "\n"
