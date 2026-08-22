"""Corpus hooks: install thin stubs + run gate/orientation logic in-package."""

from __future__ import annotations

import contextlib
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import importlib.resources as resources


GENERATED_BOARD_FILES = ("STATE.md", "stream-index.md")
ZEO_LOCAL_CACHE_ENTRIES = (".zeo/",)

_TEMPLATE_NAMES = (
    "pre-commit",
    "cc-session-start.sh",
    "cc-stop.sh",
    "cc-pretooluse-git.sh",
    "install.sh",
)

_SOW_RULING_STAGED_RE = re.compile(r"(^|/)(sow|ruling)/.*\.md$")

# RULING-277: governance-class paths, hardcoded per the ruling's own scope boundary
# (no per-repo-declared list -- that is an explicitly OPEN cosign question, not
# settled by this build). Sized to the incident (RULING-277 s0: the offending
# commits touched exactly .claude/settings.json) plus the "natural adjacent set"
# RULING-277 s2/s4 names by INFERENCE, not independent observation this session:
# CLAUDE.md and tools/hooks/** were not seen drifting themselves, they were reasoned
# to be exactly as dangerous to hand-copy as the settings file that invokes them.
_GOVERNANCE_PATH_RE = re.compile(r"(^|/)(\.claude/.+|CLAUDE\.md|tools/hooks/.+)$")

# A SOW-shaped citation in a commit message: a path under sow/, or a bare
# "SOW-NN" token, or a "<stream>#<n>" token (RULING-277's own named citation shape,
# echoed verbatim in REPO-EQUIP-SOW-2 done_when item 1).
_SOW_CITATION_RE = re.compile(
    r"(^|[\s(])sow/[^\s)]+"  # a sow/ path
    r"|\bSOW-\d+\b"  # bare SOW-NN
    r"|\b[A-Za-z][A-Za-z0-9_-]*#\d+\b",  # <stream>#<n>
    re.IGNORECASE,
)

_GOVERNANCE_WARN_STATE_FILE = "zeo-governance-warns.json"
_ESCALATE_AT = 3


def _templates_dir() -> pathlib.Path:
    # Package data: zero_employee/hooks_templates/
    try:
        root = resources.files("zero_employee").joinpath("hooks_templates")
        # Traversable → Path when on disk (editable / wheel force-include)
        return pathlib.Path(str(root))
    except Exception:
        return pathlib.Path(__file__).parent / "hooks_templates"


def ensure_board_gitignore(corpus_root: pathlib.Path | str) -> bool:
    """Ensure generated board files are listed in .gitignore.

    Returns True if `.gitignore` was created or modified.
    """
    corpus_root = pathlib.Path(corpus_root).resolve()
    path = corpus_root / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    have = {ln.strip() for ln in existing.splitlines() if ln.strip() and not ln.strip().startswith("#")}
    missing = [name for name in GENERATED_BOARD_FILES if name not in have]
    cache_missing = [name for name in ZEO_LOCAL_CACHE_ENTRIES if name not in have]
    if not missing and not cache_missing:
        return False
    body = existing
    if body and not body.endswith("\n"):
        body += "\n"
    if body and not body.endswith("\n\n"):
        body += "\n"
    if missing and "# zeo generated boards" not in existing:
        body += "# zeo generated boards (local views — do not commit)\n"
    for name in missing:
        body += f"{name}\n"
    if cache_missing:
        if "# zeo local cache" not in body:
            body += "# zeo local cache (proposals — do not commit)\n"
        for name in cache_missing:
            body += f"{name}\n"
    path.write_text(body, encoding="utf-8")
    return True


def tracked_generated_boards(corpus_root: pathlib.Path | str) -> list[str]:
    """Return generated board filenames still tracked by git (if any)."""
    corpus_root = pathlib.Path(corpus_root).resolve()
    tracked: list[str] = []
    for name in GENERATED_BOARD_FILES:
        try:
            r = subprocess.run(
                ["git", "-C", str(corpus_root), "ls-files", "--error-unmatch", "--", name],
                capture_output=True,
                text=True,
            )
        except Exception:
            continue
        if r.returncode == 0 and r.stdout.strip():
            tracked.append(name)
    return tracked


def warn_tracked_boards(corpus_root: pathlib.Path | str) -> list[str]:
    """Print a beginner hint when board files are still tracked. Returns those names."""
    tracked = tracked_generated_boards(corpus_root)
    if tracked:
        joined = " ".join(tracked)
        print(
            f"NOTE: {joined} still tracked by git. For zero-friction boards:\n  git rm --cached {' '.join(tracked)}",
            file=sys.stderr,
        )
    return tracked


def unstage_generated_boards(corpus_root: pathlib.Path | str) -> list[str]:
    """Unstage generated board files if present in the index. Returns unstaged names."""
    corpus_root = pathlib.Path(corpus_root).resolve()
    unstaged: list[str] = []
    for name in GENERATED_BOARD_FILES:
        try:
            staged = subprocess.run(
                ["git", "-C", str(corpus_root), "diff", "--cached", "--name-only", "--", name],
                capture_output=True,
                text=True,
            )
        except Exception:
            continue
        if not staged.stdout.strip():
            continue
        # A staged DELETION of a board file is the untracking act, not an
        # attempt to commit board content - let it through. Paid live in
        # zeroemployeeorg/org 2026-08-16: both boards were listed in
        # .gitignore AND tracked (gitignore has no effect on tracked files),
        # so they sat permanently dirty and every commit of them was empty.
        # The fix is `git rm --cached`, and this function unstaged that
        # deletion too - so the hook blocked its own intended end state and
        # the cleanup could only land with --no-verify.
        status = subprocess.run(
            ["git", "-C", str(corpus_root), "diff", "--cached", "--name-status", "--", name],
            capture_output=True,
            text=True,
        )
        if status.stdout.strip().startswith("D"):
            continue
        # Prefer restore --staged (works before first commit); fall back to reset.
        r = subprocess.run(
            ["git", "-C", str(corpus_root), "restore", "--staged", "--", name],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            subprocess.run(
                ["git", "-C", str(corpus_root), "reset", "HEAD", "--", name],
                capture_output=True,
                text=True,
            )
        unstaged.append(name)
    return unstaged


def _staged_sow_ruling_files(corpus_root: pathlib.Path) -> list[str]:
    try:
        r = subprocess.run(
            ["git", "-C", str(corpus_root), "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return []
    out: list[str] = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if line and _SOW_RULING_STAGED_RE.search(line):
            out.append(line)
    return out


def _regen_local_boards(corpus_root: pathlib.Path) -> None:
    """Fail-open local board refresh. Never stages the files.

    Stays fail-open by design: a broken local cache file must never block a commit
    or a session start. But a malformed STATE.md fence (--board exits 2, the ONLY
    non-zero exit `_board()` has) was previously invisible even to a human running
    the hook by hand — stdout is redirected below, and nothing ever looked at the
    return code, so the exit-2 FATAL vanished silently and could persist through
    unbounded commits/sessions. This one case is now surfaced as a one-line warning
    to REAL stderr (not the redirected stream) naming the fix. Every OTHER failure
    mode — any exception `--board` or `--stream-index` might raise — is still
    silently swallowed here, unchanged; this is not a general "stop hiding errors"
    change, only this specific detectable and actionable case.
    """
    from . import cli

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            rc = cli.main(["--board", str(corpus_root)])
        if rc == 2:
            print(
                "zeo: local STATE.md fence is malformed and was NOT regenerated "
                "(cache only — nothing else is affected). Fix it with: "
                "zeo board --repair",
                file=sys.stderr,
            )
    except Exception:
        pass
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["--stream-index", str(corpus_root)])
    except Exception:
        pass


_TRUNK_BRANCH_ENV = "ZEO_TRUNK_BRANCH"


def check_trunk_only(corpus_root: pathlib.Path | str, trunk: str | None = None) -> str | None:
    """branch-gates charter item 2: WARN (not refuse, per RULING-360) on a commit
    in a CORPUS repo made on a non-trunk branch. Returns a human-readable warning
    string for the caller to print, or None if there is nothing to warn about (on
    trunk, or branch-state undeterminable — see below). The caller no longer
    treats a non-None return as a reason to block the commit — see RULING-360 and
    run_pre_commit's own call site comment.

    WHY THE UNDERLYING CONCERN IS STILL REAL: a SOW filed on a stray branch is
    invisible to every inbox — `board`, `--inbox`, `orient`, `next` all resolve
    the corpus from the CHECKED-OUT working tree (see `_discover_root`/
    `git_ref_state`'s own doctrine comment), which in this org's actual workflow
    is expected to BE trunk. A stream that commits its SOW on a feature branch
    and never merges it has produced a filing nothing downstream can see —
    `branch-gates` charter item 2's own words, not RULING-324 (RULING-324 is the
    ratified five-state branch taxonomy; its own §4 reception section names this
    hook as unblocked-and-proceed, but the rationale text itself is the charter
    item's, and RULING-360 corrects this docstring's prior bare-RULING-324
    citation to name that properly).

    WHY IT NO LONGER BLOCKS: RULING-359 (2026-08-22) made a session branch the
    MANDATORY working shape for Master/Sparring on every actively-protected
    corpus repo — commit repeatedly to one branch all session, one PR at the
    end. A fail-closed block here refused every one of those mandated commits,
    which left `--no-verify` (skipping every check in run_pre_commit, not just
    this one) as the only way to follow the cadence at all. RULING-360 ruled the
    cadence stands and this gate yields to a warning instead.

    FAIL-OPEN ON UNDETERMINABLE, not fail-closed: a detached HEAD or a repo
    with no branch concept (rare, e.g. a fresh repo before its first branch)
    reports None (proceed) rather than guessing a refusal — this check only
    fires on a POSITIVE, confirmed "you are on a non-trunk branch" read, same
    fail-closed-on-the-refusal / fail-open-on-the-unknown shape `git_ref_state`
    already uses for `contained_in_trunk`. (This is the ONE place in this
    module that intentionally fails open on an unknown, because the ALTERNATIVE
    failure mode — blocking every commit on a corpus with a detached HEAD or a
    checkout tool this repo doesn't recognize — is worse than the gap it closes.)

    Trunk name: `ZEO_TRUNK_BRANCH` env var if set (a repo may not use `main`),
    else `main` — the name every real corpus in this org actually uses
    (branch-gates SOW-2's own four-repo survey, RULING-324's own examples).
    """
    root = pathlib.Path(corpus_root).resolve()
    trunk = trunk or os.environ.get(_TRUNK_BRANCH_ENV) or "main"
    r = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return None  # can't read HEAD at all — fail open, not this check's call
    branch = r.stdout.strip()
    if not branch or branch == "HEAD":
        return None  # detached HEAD — no branch to be "non-trunk" on; fail open
    if branch == trunk:
        return None
    return (
        f"zeo: this is a CORPUS repo and HEAD is on branch '{branch}', not trunk "
        f"('{trunk}') — this is a WARNING, not a block (RULING-360).\n"
        "  A SOW/ruling filed here and never merged back to trunk is invisible to "
        "every inbox — board, --inbox, orient, and next all read the checked-out "
        "corpus, which this org's workflow expects to be trunk (branch-gates "
        "charter item 2).\n"
        "  If you're on a session branch under RULING-359's cadence, this is "
        "expected — commit here freely, then rebase/push/open one PR at session "
        f"end. If you did not mean to be off trunk: git checkout {trunk}"
    )


def run_pre_commit(corpus_root: pathlib.Path | str | None = None) -> int:
    """Fail-closed pre-commit gate + unstage/regen local boards."""
    from . import cli

    root = pathlib.Path(corpus_root).resolve() if corpus_root else None
    if root is None:
        root = cli._discover_root(None)
    if root is None:
        print(
            "COMMIT BLOCKED: couldn't find a corpus (claude-md/CLAUDE.md). "
            "Run from inside the corpus, or set ZEO_SOWS_ROOT.",
            file=sys.stderr,
        )
        return 1
    root = pathlib.Path(root).resolve()

    # RULING-360: demoted from fail-closed refusal to a warning. RULING-359's
    # session-branch cadence mandates repeated commits to a non-trunk branch for a
    # whole session on every corpus repo this org actively operates in - a
    # fail-closed block here refused every one of those commits, forcing
    # --no-verify (which skips every check below too, not just this one) as the
    # only way to follow the cadence at all. The off-trunk condition is still
    # real and still worth surfacing (a filing dying invisible on a branch is a
    # real risk - branch-gates charter item 2's own rationale, unchanged) so it
    # prints to stderr and the real gates below still run fail-closed regardless
    # of branch.
    trunk_warning = check_trunk_only(root)
    if trunk_warning is not None:
        print(trunk_warning, file=sys.stderr)

    unstaged = unstage_generated_boards(root)
    if unstaged:
        print(
            f"zeo: unstaged generated board file(s) (local views, not committed): {', '.join(unstaged)}",
            file=sys.stderr,
        )

    print("--> Auto-regenerating local fleet board...", file=sys.stderr)
    _regen_local_boards(root)

    staged = _staged_sow_ruling_files(root)
    if not staged:
        return 0

    failed = False
    for rel in staged:
        path = root / rel
        if not path.is_file():
            continue
        rc = cli.main(["--commit-check", str(path)])
        if rc != 0:
            print(f"-- zeo rejected: {rel}", file=sys.stderr)
            failed = True

    # --commit-check-corpus now covers BOTH ruling-number collisions and SOW
    # n-collisions in one pass (extended 2026-08-16, same day the SOW half of this
    # gap was found live in two separate corpora - see cli.py's _commit_check_corpus
    # docstring). It must run on EVERY staged SOW/ruling commit, not only when a
    # ruling file is among them: an n-collision is a SOW-namespace defect and can
    # land from a commit that touches no ruling/ file at all - the previous
    # ruling-only gate would have missed exactly that shape, which is how
    # MOTION-ELEMENTS-SOW-1 and quackverse-coverage-90 SOW-10 both slipped through.
    rc = cli.main(["--commit-check-corpus", str(root)])
    if rc != 0:
        print("-- zeo rejected: a ruling-number or SOW n-collision, corpus-wide", file=sys.stderr)
        failed = True

    if failed:
        print(
            "COMMIT BLOCKED: staged SOW/ruling file(s) failed zeo. Fix and re-stage.",
            file=sys.stderr,
        )
        return 1
    return 0


def run_session_start(corpus_root: pathlib.Path | str | None = None) -> int:
    """Fail-open SessionStart orientation; refresh local boards."""
    from . import cli
    from .orient import build_orientation, render_orientation_human

    root = pathlib.Path(corpus_root).resolve() if corpus_root else cli._discover_root(None)
    if root is None:
        print("zeo not oriented — run from inside a corpus (or set ZEO_SOWS_ROOT).")
        return 0
    root = pathlib.Path(root).resolve()
    print("=== ZEO SESSION START ===")
    try:
        o = build_orientation(root=root)
        print(render_orientation_human(o), end="")
    except Exception:
        try:
            cli.main(["--triage", str(root)])
        except Exception:
            pass
    print("--- streams not at rest, oldest idle first ---")
    try:
        cli.main(["--progress", str(root)])
    except Exception:
        pass
    print("--- distance to done ---")
    try:
        cli.main(["--restaufwand", str(root)])
    except Exception:
        pass
    print("--> Refreshing local fleet board...")
    _regen_local_boards(root)
    print("If you are a STREAM: run 'zeo work <your-stream>' and 'zeo --inbox <your-stream>'.")
    print("Agent first command: zeo orient --json")
    print("The tool reads DISK. A spawn message that disagrees with it is WRONG.")
    return 0


def run_stop(corpus_root: pathlib.Path | str | None = None, stdin_text: str | None = None) -> int:
    """Fail-open Stop hook: session cost + uncommitted SOW/ruling advisory."""
    from . import cli

    root = pathlib.Path(corpus_root).resolve() if corpus_root else cli._discover_root(None)
    if root is None:
        return 0
    root = pathlib.Path(root).resolve()
    log = root / "tools" / "stream-instruments" / "session-costs.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)

    raw = stdin_text if stdin_text is not None else (sys.stdin.read() if not sys.stdin.isatty() else "")
    transcript = ""
    try:
        data = json.loads(raw or "{}")
        if isinstance(data, dict):
            transcript = str(data.get("transcript_path") or "")
    except Exception:
        transcript = ""

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            if transcript and pathlib.Path(transcript).is_file():
                cli.main(
                    [
                        "--session-cost",
                        "--transcript",
                        transcript,
                        "--append-cost-log",
                        str(log),
                    ]
                )
            elif log.is_file():
                cli.main(["--session-cost", "--cost-log", str(log)])
    except Exception:
        pass

    try:
        st = subprocess.run(
            ["git", "-C", str(root), "status", "--short"],
            capture_output=True,
            text=True,
        )
        hits = [ln for ln in st.stdout.splitlines() if _SOW_RULING_STAGED_RE.search(ln)]
        if hits:
            print(
                f"ZEO: {len(hits)} SOW/ruling file(s) UNCOMMITTED. Your context dies here; the chain is what survives.",
                file=sys.stderr,
            )
            for ln in hits[:5]:
                print(ln, file=sys.stderr)
    except Exception:
        pass
    return 0


def _extract_tool_command(raw: str) -> str:
    """Best-effort pull of tool_input.command from a PreToolUse JSON payload.

    Falls back to the raw text itself (matches this hook's pre-existing
    convention of substring-matching "git commit"/"git push" directly on
    stdin, for callers that pass a bare command string instead of full JSON --
    see run_pretooluse_git's own docstring history and its tests).
    """
    try:
        data = json.loads(raw or "{}")
        if isinstance(data, dict):
            cmd = data.get("tool_input", {}).get("command")
            if isinstance(cmd, str) and cmd:
                return cmd
    except Exception:
        pass
    return raw


def _extract_commit_message(command: str) -> str:
    """Pull the intended commit message out of a pending `git commit` command.

    The PreToolUse hook fires BEFORE the tool runs, so there is no committed
    message to read from git yet -- only the proposed command line. Handles
    repeated -m (git concatenates them with blank lines) and -F/--file=.
    Best-effort: a message zeo can't parse is treated as uncited, which is the
    fail-safe direction for a WARN-only advisory.
    """
    msgs = []
    for m in re.finditer(r"(?:^|\s)(?:-m|--message)(?:=|\s+)(\"([^\"]*)\"|'([^']*)'|(\S+))", command):
        msgs.append(m.group(2) or m.group(3) or m.group(4) or "")
    for m in re.finditer(r"(?:^|\s)(?:-F|--file)(?:=|\s+)(\S+)", command):
        fpath = m.group(1).strip("\"'")
        try:
            msgs.append(pathlib.Path(fpath).read_text(encoding="utf-8", errors="replace"))
        except Exception:
            pass
    return "\n".join(msgs)


def _governance_paths_touched(staged: list[str]) -> list[str]:
    return [line for line in staged if _GOVERNANCE_PATH_RE.search(line)]


def _has_sow_citation(message: str) -> bool:
    return bool(_SOW_CITATION_RE.search(message or ""))


def _git_dir(cwd: pathlib.Path | None = None) -> pathlib.Path | None:
    """Resolve the real .git dir (worktree-safe) via git itself."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
        )
        if r.returncode != 0:
            return None
        p = pathlib.Path(r.stdout.strip())
        if not p.is_absolute():
            p = (pathlib.Path(cwd) if cwd else pathlib.Path.cwd()) / p
        return p.resolve()
    except Exception:
        return None


def _git_author(cwd: pathlib.Path | None = None) -> str:
    try:
        r = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
        )
        email = r.stdout.strip()
        if email:
            return email
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
        )
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _bump_governance_warn_count(git_dir: pathlib.Path | None, session_id: str, author: str) -> int:
    """Persist + increment the uncited-governance-path-commit count.

    RULING-277 s3's escalation ("three unSOWed governance-path commits from the
    same author within one session") needs SOME memory across otherwise-stateless
    PreToolUse invocations (SOW s2's own named gap). Chosen mechanism: a small
    JSON state file at <git-dir>/zeo-governance-warns.json, keyed by the real
    Claude Code `session_id` field (confirmed present on every PreToolUse
    payload per Claude Code's own hook docs -- session_id is a COMMON field,
    not PreToolUse-specific, so it needs no derivation from transcript_path the
    way run_stop's cost logic does). This is deliberately NOT the flat
    never-resets counter the SOW's s2 named as "probably wrong" (a long-lived
    repo would escalate once and never again), and NOT a git-log-window
    heuristic (which would redefine "session" as "recent history" and could
    over/under-fire relative to what RULING-277 s3 actually asked for). Keying
    by session_id means a new Claude Code session starts this count at zero
    automatically -- the file can grow unboundedly across many sessions over
    time, but each entry is tiny (author -> int) and this is advisory state,
    not doctrine; pruning is a future cheap follow-up, not a correctness gap.
    Fails open (returns 1, i.e. "treat as first warning") if the state file
    can't be read or written, matching this hook's overall fail-open contract.
    """
    if not git_dir or not session_id:
        return 1
    state_path = git_dir / _GOVERNANCE_WARN_STATE_FILE
    try:
        data = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    session_bucket = data.get(session_id)
    if not isinstance(session_bucket, dict):
        session_bucket = {}
    count = int(session_bucket.get(author, 0)) + 1
    session_bucket[author] = count
    data[session_id] = session_bucket
    try:
        state_path.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass
    return count


def run_pretooluse_git(stdin_text: str | None = None) -> int:
    """Fail-open PreToolUse advisory before git commit/push."""
    raw = stdin_text if stdin_text is not None else (sys.stdin.read() if not sys.stdin.isatty() else "")
    command = _extract_tool_command(raw)
    if "git commit" not in command and "git push" not in command:
        return 0
    print("--- ZEO pre-git check ---", file=sys.stderr)
    try:
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    except Exception:
        staged = []
    streams = sorted({m.group(0) for line in staged for m in [re.search(r"(^|/)sow/[^/]+/", line)] if m})
    if len(streams) > 1:
        print(f"WARNING: staged set spans {len(streams)} stream directories.", file=sys.stderr)
        for line in staged[:8]:
            print(line, file=sys.stderr)
        print('Commit BY EXPLICIT PATHSPEC: git commit -m "..." -- <path>', file=sys.stderr)
    if "git commit" in command and " -- " not in command:
        print(
            "WARNING: no explicit pathspec (-- <path>). A bare commit ships the whole index.",
            file=sys.stderr,
        )

    # RULING-277: governance-class path gate. WARN only -- never block. See
    # REPO-EQUIP-SOW-2 done_when items 1-2. Only meaningful on an actual commit
    # (a `git push` has nothing new staged and no pending commit message to
    # check citation against).
    if "git commit" in command:
        gov_hits = _governance_paths_touched(staged)
        if gov_hits:
            message = _extract_commit_message(command)
            if not _has_sow_citation(message):
                print(
                    "WARN [RULING-277]: this commit touches governance-class path(s) with "
                    "no SOW-shaped citation (a sow/ path, 'SOW-NN', or '<stream>#<n>') in "
                    "the commit message:",
                    file=sys.stderr,
                )
                for hit in gov_hits:
                    print(f"  {hit}", file=sys.stderr)
                print(
                    "Governance-class config (.claude/**, CLAUDE.md, tools/hooks/**) hand-copied "
                    "across repos with no SOW filed is the exact RULING-277 s0 incident shape. "
                    "If this is a real fix, cite the SOW in the commit message; if there is none "
                    "yet, file one first.",
                    file=sys.stderr,
                )
                try:
                    data = json.loads(raw or "{}")
                    session_id = str(data.get("session_id") or "") if isinstance(data, dict) else ""
                except Exception:
                    session_id = ""
                author = _git_author()
                count = _bump_governance_warn_count(_git_dir(), session_id, author)
                if count >= _ESCALATE_AT:
                    print(
                        f"ESCALATE [RULING-277]: uncited governance-path commit #{count} by "
                        f"{author} in this session (threshold: {_ESCALATE_AT}). STOP and file a "
                        "SOW before continuing -- do not keep committing past this warning.",
                        file=sys.stderr,
                    )
    return 0


def hooks_install(
    corpus_root: pathlib.Path | str,
    *,
    install_git_hook: bool = True,
) -> dict:
    """Write thin hook stubs into <corpus>/tools/hooks/ and optionally .git/hooks/pre-commit.

    Also ensures generated board files are gitignored.

    Returns {written, git_hook, hooks_dir, gitignore_updated, tracked_boards}.
    """
    corpus_root = pathlib.Path(corpus_root).resolve()
    hooks_dir = corpus_root / "tools" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    src_dir = _templates_dir()
    written = []
    for name in _TEMPLATE_NAMES:
        src = src_dir / name
        if not src.is_file():
            raise FileNotFoundError(f"missing hook template: {src}")
        dest = hooks_dir / name
        shutil.copyfile(src, dest)
        dest.chmod(dest.stat().st_mode | 0o111)
        written.append(str(dest.relative_to(corpus_root)))

    gitignore_updated = ensure_board_gitignore(corpus_root)
    tracked_boards = tracked_generated_boards(corpus_root)

    git_hook = None
    if install_git_hook:
        git_dir = corpus_root / ".git"
        if git_dir.is_dir() or git_dir.is_file():  # file = worktree gitfile
            dst = corpus_root / ".git" / "hooks" / "pre-commit"
            # When .git is a file (worktree), resolve the real git dir
            if git_dir.is_file():
                text = git_dir.read_text(encoding="utf-8", errors="replace").strip()
                if text.startswith("gitdir:"):
                    real = (corpus_root / text.split(":", 1)[1].strip()).resolve()
                    dst = real / "hooks" / "pre-commit"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(hooks_dir / "pre-commit", dst)
            dst.chmod(dst.stat().st_mode | 0o111)
            git_hook = str(dst)

    return {
        "written": written,
        "git_hook": git_hook,
        "hooks_dir": str(hooks_dir),
        "gitignore_updated": gitignore_updated,
        "tracked_boards": tracked_boards,
    }
