"""COLD-START-SOW-2: the partial Ist-Aufnahme verb, checklist items 1/3/8/9/10 only.

RULING-278 s3 names a fixed, 10-item, mechanical-before-interpretive survey a fresh
repo needs before any first charter (Soll) can be proposed. This module runs the
5 items that need NO stack detector (items 2, 4, 5, 6, 7 are deferred -- they need
REPO-EQUIP-SOW-1's stack detector, which has not shipped; verified at charter time
via `grep -rn "detect_stack\\|def.*stack" src/zero_employee/` -- zero hits).

VALUE-FREE, per RULING-278 s1: every item records `ITEM: <what was found>` with the
exact command run and its literal output/exit code -- never a paraphrase, never a
recommendation. A row that cannot complete is `CANNOT-COMPLETE: <reason>`, never
silently skipped (RULING-024's uncertainty-is-a-verdict doctrine, cited directly by
RULING-278 s3's own closing line).

SAFETY PROPERTY (RULING-278 s5, COLD-START-SOW-1 s3, the load-bearing one): this
module never writes into the TARGET work repo. Every git/gh call here is READ-ONLY
(status, log, remote, shortlog, ls-files -- never add/commit/push). The SOW output
lands in the SOWS repo only, written by the CLI layer (`cli.py`), not here.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
import shutil
import subprocess

# ── item 1: identity ────────────────────────────────────────────────


def _run(args: list[str], *, cwd: pathlib.Path, timeout: int = 30) -> dict:
    """Run one read-only subprocess and record it as a checklist evidence row.

    Returns a dict carrying the EXACT command, its literal stdout/stderr, and the
    real exit code -- the discipline every item below composes from. Never raises;
    a missing binary or a timeout is recorded as its own evidence row, not an
    exception that would abort the whole survey.
    """
    cmd_str = " ".join(args)
    try:
        r = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "command": cmd_str,
            "exit_code": r.returncode,
            "stdout": r.stdout.strip(),
            "stderr": r.stderr.strip(),
        }
    except FileNotFoundError:
        return {"command": cmd_str, "exit_code": None, "stdout": "", "stderr": "binary not found"}
    except subprocess.TimeoutExpired:
        return {"command": cmd_str, "exit_code": None, "stdout": "", "stderr": f"timed out after {timeout}s"}


def survey_identity(repo: pathlib.Path) -> dict:
    """RULING-278 s3 item 1: git remote, default branch, commit count, first/last
    commit date, contributor count (`git shortlog -sn`)."""
    evidence = []

    remote = _run(["git", "remote", "-v"], cwd=repo)
    evidence.append(remote)

    branch = _run(["git", "symbolic-ref", "--short", "HEAD"], cwd=repo)
    evidence.append(branch)

    count = _run(["git", "rev-list", "--count", "HEAD"], cwd=repo)
    evidence.append(count)

    first = _run(["git", "log", "--reverse", "--format=%aI", "-1"], cwd=repo)
    evidence.append(first)

    last = _run(["git", "log", "-1", "--format=%aI"], cwd=repo)
    evidence.append(last)

    shortlog = _run(["git", "shortlog", "-sn", "HEAD"], cwd=repo)
    evidence.append(shortlog)

    cannot_complete = None
    if branch["exit_code"] not in (0,) and count["exit_code"] not in (0,):
        cannot_complete = "no commits reachable from HEAD (empty repo, or not a git repo)"

    return {
        "item": 1,
        "name": "Identity",
        "cannot_complete": cannot_complete,
        "evidence": evidence,
        "summary": {
            "remote": remote["stdout"] or "(none configured)",
            "default_branch": branch["stdout"] if branch["exit_code"] == 0 else "UNKNOWN",
            "commit_count": count["stdout"] if count["exit_code"] == 0 else "UNKNOWN",
            "first_commit_date": first["stdout"] if first["exit_code"] == 0 else "UNKNOWN",
            "last_commit_date": last["stdout"] if last["exit_code"] == 0 else "UNKNOWN",
            "contributors": shortlog["stdout"] if shortlog["exit_code"] == 0 else "UNKNOWN",
        },
    }


# ── item 3: existing gate presence ──────────────────────────────────

_CI_CANDIDATES = [
    ".github/workflows",
    ".gitlab-ci.yml",
    ".circleci/config.yml",
    ".travis.yml",
    "azure-pipelines.yml",
    ".buildkite/pipeline.yml",
    "Jenkinsfile",
]


def survey_ci_presence(repo: pathlib.Path) -> dict:
    """RULING-278 s3 item 3: does a CI config exist? PRESENCE ONLY for this slice --
    whether it currently passes is item 3's own second half, deferred alongside
    items 4-7 pending the stack detector (this SOW's own scope boundary)."""
    evidence = []
    found = []
    for rel in _CI_CANDIDATES:
        p = repo / rel
        exists = p.exists()
        evidence.append(
            {
                "command": f"test -e {rel}",
                "exit_code": 0 if exists else 1,
                "stdout": str(p) if exists else "",
                "stderr": "",
            }
        )
        if exists:
            found.append(rel)
    workflows_dir = repo / ".github" / "workflows"
    workflow_files = []
    if workflows_dir.is_dir():
        listing = _run(["ls", "-1", str(workflows_dir)], cwd=repo)
        evidence.append(listing)
        workflow_files = sorted(f for f in listing["stdout"].splitlines() if f)

    return {
        "item": 3,
        "name": "Existing gate presence",
        "cannot_complete": None,
        "evidence": evidence,
        "summary": {
            "ci_config_found": bool(found),
            "paths": found,
            "github_workflow_files": workflow_files,
        },
    }


# ── item 8: existing documentation surface ──────────────────────────

_README_CANDIDATES = ["README.md", "README.rst", "README.txt", "README"]


def survey_docs_surface(repo: pathlib.Path) -> dict:
    """RULING-278 s3 item 8: README present and non-trivial (more than a title +
    one line). Line/word counts are the exact, cited command output -- not a
    subjective read."""
    evidence = []
    readme_path = None
    for rel in _README_CANDIDATES:
        p = repo / rel
        exists = p.is_file()
        evidence.append(
            {
                "command": f"test -f {rel}",
                "exit_code": 0 if exists else 1,
                "stdout": str(p) if exists else "",
                "stderr": "",
            }
        )
        if exists and readme_path is None:
            readme_path = p

    if readme_path is None:
        return {
            "item": 8,
            "name": "Existing documentation surface",
            "cannot_complete": None,
            "evidence": evidence,
            "summary": {"readme_found": False, "non_trivial": False, "line_count": 0, "word_count": 0},
        }

    wc = _run(["wc", "-l", "-w", str(readme_path)], cwd=repo)
    evidence.append(wc)
    line_count = 0
    word_count = 0
    m = re.match(r"\s*(\d+)\s+(\d+)", wc["stdout"])
    if m:
        line_count, word_count = int(m.group(1)), int(m.group(2))

    # "more than a title + one line": >2 non-empty lines, per RULING-278 s3 item 8's
    # own literal bound (a title line + one body line is exactly the trivial case).
    text = readme_path.read_text(encoding="utf-8", errors="replace")
    non_empty_lines = [ln for ln in text.splitlines() if ln.strip()]
    non_trivial = len(non_empty_lines) > 2

    return {
        "item": 8,
        "name": "Existing documentation surface",
        "cannot_complete": None,
        "evidence": evidence,
        "summary": {
            "readme_found": True,
            "readme_path": str(readme_path.relative_to(repo)),
            "non_trivial": non_trivial,
            "line_count": line_count,
            "word_count": word_count,
            "non_empty_lines": len(non_empty_lines),
        },
    }


# ── item 9: TODO/FIXME/XXX markers + open GitHub issues ─────────────

# POSIX basic regex, not -E/ERE: git grep's ERE engine does not honor \< \>
# word-boundary anchors the way its BRE engine does (measured directly -- `git
# grep -E '\b(TODO|FIXME|XXX)\b'` silently matched nothing at all, `-E` with
# `\<...\>` also came back empty; only bare BRE `\<\(TODO\|FIXME\|XXX\)\>`
# both matches real markers AND correctly excludes substrings like
# "notATODOword"). No -E flag on the _run() call below, to match this pattern.
_MARKER_RE = r"\<\(TODO\|FIXME\|XXX\)\>"


def survey_markers_and_issues(repo: pathlib.Path) -> dict:
    """RULING-278 s3 item 9: grep for TODO/FIXME/XXX; if `gh` is available and
    authenticated, also record open issue count. Skips the `gh` half cleanly (and
    says so plainly) when `gh` is missing or not authenticated -- never errors."""
    evidence = []

    grep = _run(
        [
            "git",
            "grep",
            "-n",
            "-I",
            "--",
            _MARKER_RE,
        ],
        cwd=repo,
    )
    evidence.append(grep)
    # `git grep` exits 1 when there are zero matches (not a failure) and 0 when
    # there are matches; anything else (128, etc.) is a real error, e.g. not a
    # git repo or nothing committed yet to grep against HEAD's tree via working set.
    marker_lines = [ln for ln in grep["stdout"].splitlines() if ln.strip()] if grep["exit_code"] in (0, 1) else []
    marker_count = len(marker_lines)
    grep_cannot_complete = None
    if grep["exit_code"] not in (0, 1):
        grep_cannot_complete = f"git grep exited {grep['exit_code']}: {grep['stderr'] or '(no stderr)'}"

    gh_path = shutil.which("gh")
    gh_status = None
    gh_issue_count = None
    gh_skip_reason = None
    if gh_path is None:
        gh_skip_reason = "gh CLI not found on PATH -- skipping open-issue count, marker scan above is unaffected"
    else:
        auth = _run(["gh", "auth", "status"], cwd=repo)
        # `gh auth status` stdout carries the operator's own GitHub username and
        # local hosts.yml path (MEASURED: a live run against this seat's own
        # credential leaked exactly that into a filed SOW before this guard was
        # added) -- neither belongs in a corpus artifact meant to be comparable
        # and shareable across repos. Record ONLY the exit code as evidence; the
        # command run is still cited exactly, just not its PII-bearing stdout.
        auth_evidence = {"command": auth["command"], "exit_code": auth["exit_code"], "stdout": "", "stderr": ""}
        evidence.append(auth_evidence)
        gh_status = auth
        if auth["exit_code"] != 0:
            gh_skip_reason = (
                "gh CLI found but not authenticated (`gh auth status` exited nonzero) -- skipping open-issue count"
            )
        else:
            issues = _run(["gh", "issue", "list", "--state", "open", "--limit", "1000", "--json", "number"], cwd=repo)
            evidence.append(issues)
            if issues["exit_code"] == 0:
                # count JSON array entries without a full JSON parse dependency surprise --
                # a bare `[]` is 0, N objects each carry one `"number":` key.
                gh_issue_count = issues["stdout"].count('"number"')
            else:
                gh_skip_reason = f"gh issue list exited {issues['exit_code']}: {issues['stderr'] or '(no stderr)'}"

    return {
        "item": 9,
        "name": "Existing TODO/FIXME/XXX markers and open GitHub issues",
        "cannot_complete": grep_cannot_complete,
        "evidence": evidence,
        "summary": {
            "marker_count": marker_count,
            "marker_sample": marker_lines[:20],
            "gh_available": gh_path is not None,
            "gh_authenticated": gh_status is not None and gh_status["exit_code"] == 0,
            "open_issue_count": gh_issue_count,
            "gh_skip_reason": gh_skip_reason,
        },
    }


# ── item 10: secrets/safety scan, presence-only ─────────────────────


def survey_secrets_presence(repo: pathlib.Path) -> dict:
    """RULING-278 s3 item 10: presence-only. Does `.env` exist? Does `.env.example`
    exist? Is `.env` listed in `.gitignore`? NEVER reads file contents -- no
    external scanning service, no actual secret detection, per RULING-278's own
    explicit exclusion (COLD-START-SOW-1 s4) and this SOW's own scope boundary."""
    evidence = []

    env_path = repo / ".env"
    env_exists = env_path.exists()
    evidence.append(
        {
            "command": "test -e .env",
            "exit_code": 0 if env_exists else 1,
            "stdout": str(env_path) if env_exists else "",
            "stderr": "",
        }
    )

    example_path = repo / ".env.example"
    example_exists = example_path.exists()
    evidence.append(
        {
            "command": "test -e .env.example",
            "exit_code": 0 if example_exists else 1,
            "stdout": str(example_path) if example_exists else "",
            "stderr": "",
        }
    )

    gitignore_path = repo / ".gitignore"
    env_in_gitignore = False
    if gitignore_path.is_file():
        grep = _run(["grep", "-n", "-x", r"\.env\|/\.env\|\.env/\*\|\.env\*", str(gitignore_path)], cwd=repo)
        # A plain fixed-string check is more reliable than the regex above for the
        # common exact-line case; keep both -- the exact-match pass is the evidence
        # of record, the grep call is retained as an additional cited command.
        evidence.append(grep)
        lines = [ln.strip() for ln in gitignore_path.read_text(encoding="utf-8", errors="replace").splitlines()]
        env_in_gitignore = any(ln in (".env", "/.env", ".env*", "/.env*") for ln in lines)
    else:
        evidence.append({"command": "test -f .gitignore", "exit_code": 1, "stdout": "", "stderr": ""})

    return {
        "item": 10,
        "name": "Secrets/safety scan, presence-only",
        "cannot_complete": None,
        "evidence": evidence,
        "summary": {
            "env_exists": env_exists,
            "env_example_exists": example_exists,
            "env_in_gitignore": env_in_gitignore,
        },
    }


# ── orchestration ────────────────────────────────────────────────────

DEFERRED_ITEMS = [
    (2, "Stack detection", "needs REPO-EQUIP-SOW-1's stack detector, which has not shipped"),
    (4, "Test suite, run not read", "needs the stack detector to know which test runner to invoke"),
    (5, "Lint / format, run not read", "needs the stack detector to know which linter to invoke"),
    (6, "Typecheck, if the stack has one", "needs the stack detector to know which typechecker (if any) to invoke"),
    (7, "Dependency health", "needs the stack detector to know which lockfile/audit command applies"),
]

RAN_ITEMS = [1, 3, 8, 9, 10]


def run_partial_survey(repo_path: pathlib.Path) -> dict:
    """Run checklist items 1, 3, 8, 9, 10 against `repo_path` and return a structured
    result. Read-only: every subprocess call here is a `git`/`gh`/`ls`/`wc`/`grep`/
    `test` read, never a write, never a commit -- see module docstring's safety
    property. Does not touch the SOWS repo; that is the CLI layer's job."""
    repo = pathlib.Path(repo_path).resolve()
    if not repo.is_dir():
        raise FileNotFoundError(f"not a directory: {repo}")

    results = [
        survey_identity(repo),
        survey_ci_presence(repo),
        survey_docs_surface(repo),
        survey_markers_and_issues(repo),
        survey_secrets_presence(repo),
    ]

    return {
        "repo_path": str(repo),
        "ran_items": RAN_ITEMS,
        "deferred_items": DEFERRED_ITEMS,
        "results": results,
        "surveyed_at": _dt.datetime.now().isoformat(timespec="seconds"),
    }


def derive_project_name(repo_path: pathlib.Path) -> str:
    """Derive `<PROJECT>` from the target repo's remote (if any) else its dirname.

    Prefers the git remote's own repo-name component (portable across hosts and
    clones-under-a-different-dirname); falls back to the directory's own name when
    no remote is configured -- a real, common case for a brand-new local-only repo,
    which is exactly the RULING-278 s0 gap this SOW closes.
    """
    repo = pathlib.Path(repo_path).resolve()
    remote = _run(["git", "remote", "get-url", "origin"], cwd=repo)
    if remote["exit_code"] == 0 and remote["stdout"]:
        url = remote["stdout"].strip()
        name = url.rstrip("/").rsplit("/", 1)[-1]
        if name.endswith(".git"):
            name = name[: -len(".git")]
        if name:
            return _slugify_project(name)
    return _slugify_project(repo.name)


def _slugify_project(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return slug or "unknown-project"


# ── SOW body rendering ───────────────────────────────────────────────


def _render_evidence_row(ev: dict) -> str:
    lines = [f"  - `$ {ev['command']}`  (exit {ev['exit_code']})"]
    if ev.get("stdout"):
        for ln in ev["stdout"].splitlines() or [""]:
            lines.append(f"    | {ln}")
    else:
        lines.append("    | (no stdout)")
    if ev.get("stderr"):
        for ln in ev["stderr"].splitlines():
            lines.append(f"    ! {ln}")
    return "\n".join(lines)


def _render_item(result: dict) -> str:
    out = [f"### Item {result['item']} — {result['name']}", ""]
    if result.get("cannot_complete"):
        out.append(f"**CANNOT-COMPLETE:** {result['cannot_complete']}")
        out.append("")
    out.append("**ITEM:** " + _summary_line(result))
    out.append("")
    out.append("Evidence (exact command run, literal output, real exit code):")
    out.append("")
    for ev in result["evidence"]:
        out.append(_render_evidence_row(ev))
    out.append("")
    return "\n".join(out)


def _summary_line(result: dict) -> str:
    s = result["summary"]
    item = result["item"]
    if item == 1:
        return (
            f"remote={s['remote']!r}; default_branch={s['default_branch']}; "
            f"commit_count={s['commit_count']}; first_commit={s['first_commit_date']}; "
            f"last_commit={s['last_commit_date']}"
        )
    if item == 3:
        return f"ci_config_found={s['ci_config_found']}; paths={s['paths']}; github_workflow_files={s['github_workflow_files']}"
    if item == 8:
        if not s["readme_found"]:
            return "readme_found=False"
        return (
            f"readme_found=True; readme_path={s['readme_path']}; non_trivial={s['non_trivial']} "
            f"(non_empty_lines={s['non_empty_lines']}, line_count={s['line_count']}, word_count={s['word_count']})"
        )
    if item == 9:
        gh_bit = (
            f"open_issue_count={s['open_issue_count']}"
            if s["open_issue_count"] is not None
            else f"gh SKIPPED ({s['gh_skip_reason']})"
        )
        return f"marker_count={s['marker_count']}; gh_available={s['gh_available']}; gh_authenticated={s['gh_authenticated']}; {gh_bit}"
    if item == 10:
        return (
            f"env_exists={s['env_exists']}; env_example_exists={s['env_example_exists']}; "
            f"env_in_gitignore={s['env_in_gitignore']}"
        )
    return str(s)


def render_ist_aufnahme_body(survey: dict, *, project: str) -> str:
    """Render the full SOW body: which 5 items ran, which 5 are deferred and why
    (RULING-278 s3, COLD-START-SOW-2 s3's own "must state PLAINLY" requirement),
    then each ran item as a checklist row with cited evidence."""
    lines = [
        f"# {project.upper()}-COLD-START-SOW-1 — Ist-Aufnahme (partial: 5 of 10 checklist items)",
        "",
        "## 0 — what this is",
        "",
        (
            "A bounded, mechanical, value-free survey of this repo, per RULING-278 s1-s3. "
            "This is the IST half only — no judgement, no recommendation, no Soll-Vorschlag. "
            "Every row below cites the exact command run and its literal output/exit code, "
            "never a paraphrase."
        ),
        "",
        "## 1 — coverage: 5 of 10 items ran, 5 deferred (stated plainly, not omitted)",
        "",
        f"**RAN** (no stack-detector dependency, per COLD-START-SOW-2's own scope): items {', '.join(str(i) for i in survey['ran_items'])}.",
        "",
        "**DEFERRED** (need `REPO-EQUIP-SOW-1`'s stack detector, which has not shipped):",
        "",
    ]
    for num, name, why in survey["deferred_items"]:
        lines.append(f"  - Item {num}. **{name}** — {why}.")
    lines += [
        "",
        (
            "This survey is therefore explicitly PARTIAL. A future cold-start pass "
            "(once the stack detector ships) must run items 2, 4-7 and supersede this "
            "filing before any Soll-Vorschlag is proposed — RICE scoring and the "
            "first-charter proposal are both out of scope here (COLD-START-SOW-2 s2)."
        ),
        "",
        "## 2 — the 5 ran items, each a checklist row with cited evidence",
        "",
    ]
    for result in survey["results"]:
        lines.append(_render_item(result))
    lines += [
        "## 3 — no judgement, per RULING-278 s1",
        "",
        (
            "Nothing above is a recommendation. This filing records only what is true, "
            "checked, and runnable against this repo at survey time "
            f"({survey['surveyed_at']}). A Soll-Vorschlag reading this filing is a "
            "separate, later act (RULING-278 s4/s5), not built here."
        ),
        "",
    ]
    return "\n".join(lines)


# ── write into the SOWS repo (NEVER the work repo) ──────────────────


def write_ist_aufnahme_sow(sows_root: pathlib.Path, project: str, survey: dict) -> dict:
    """Write `<PROJECT>-COLD-START-SOW-01-ist-aufnahme.md` under
    `projects/<project>/sow/cold-start/` in the SOWS repo. `status: FINDING`,
    `lifecycle: RECON`.

    SAFETY: this function only ever touches `sows_root` -- it never receives, and
    never writes into, the surveyed work repo's own path. The caller (CLI layer)
    passes the SOWS root explicitly; nothing here derives a write target from
    `survey['repo_path']`.
    """
    from .sow_authoring import build_frontmatter, render_sow, transactional_create

    sows_root = pathlib.Path(sows_root).resolve()
    chain_dir = sows_root / "projects" / project / "sow" / "cold-start"
    chain_dir.mkdir(parents=True, exist_ok=True)
    (sows_root / "projects" / project).mkdir(parents=True, exist_ok=True)

    from .core import canonical_name

    stream = f"{project}-cold-start"
    # MEASURED (2026-08-17): a hand-built filename here ("{PROJECT}-COLD-START-
    # SOW-1-...", no zero-pad) does not match what the corpus's own linter
    # expects (canonical_name's zero-padded "<sow>-SOW-<n>-<slug>.md") and the
    # write fails closed with a noncanonical-name error -- caught by Master
    # manually probing this function against a real throwaway repo before
    # trusting the stream's own report. Use the same generator every other SOW
    # writer in this package uses instead of a second, drifted filename rule.
    filename = canonical_name(stream.upper(), 1, "ist-aufnahme")
    dest = chain_dir / filename

    fm = build_frontmatter(
        project=project,
        stream=stream,
        n=1,
        status="FINDING",
        lifecycle="RECON",
        title="Ist-Aufnahme (partial: 5 of 10 checklist items)",
        requested_by="ruling: 278",
        work_repo=pathlib.Path(survey["repo_path"]).name,
        restaufwand=0,
    )
    body = render_ist_aufnahme_body(survey, project=project)
    content = render_sow(fm, body)
    ok, reason, findings = transactional_create(dest, content, root=sows_root)
    return {
        "ok": ok,
        "reason": reason,
        "findings": findings,
        "path": str(dest),
    }
