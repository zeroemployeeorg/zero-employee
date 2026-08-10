"""Corpus hooks: install thin stubs + run gate/orientation logic in-package."""

from __future__ import annotations

import contextlib
import io
import json
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
_RULING_STAGED_RE = re.compile(r"(^|/)ruling/RULING-[0-9]+-")


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
    have = {
        ln.strip()
        for ln in existing.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    }
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
            f"NOTE: {joined} still tracked by git. For zero-friction boards:\n"
            f"  git rm --cached {' '.join(tracked)}",
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
    """Fail-open local board refresh. Never stages the files."""
    from . import cli

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["--board", str(corpus_root)])
    except Exception:
        pass
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["--stream-index", str(corpus_root)])
    except Exception:
        pass


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

    unstaged = unstage_generated_boards(root)
    if unstaged:
        print(
            f"zeo: unstaged generated board file(s) (local views, not committed): "
            f"{', '.join(unstaged)}",
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

    if any(_RULING_STAGED_RE.search(f) for f in staged):
        rc = cli.main(["--commit-check-corpus", str(root)])
        if rc != 0:
            print("-- zeo rejected: ruling-number collision, corpus-wide", file=sys.stderr)
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
        hits = [
            ln
            for ln in st.stdout.splitlines()
            if _SOW_RULING_STAGED_RE.search(ln)
        ]
        if hits:
            print(
                f"ZEO: {len(hits)} SOW/ruling file(s) UNCOMMITTED. "
                "Your context dies here; the chain is what survives.",
                file=sys.stderr,
            )
            for ln in hits[:5]:
                print(ln, file=sys.stderr)
    except Exception:
        pass
    return 0


def run_pretooluse_git(stdin_text: str | None = None) -> int:
    """Fail-open PreToolUse advisory before git commit/push."""
    raw = stdin_text if stdin_text is not None else (sys.stdin.read() if not sys.stdin.isatty() else "")
    if "git commit" not in raw and "git push" not in raw:
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
    streams = sorted(
        {
            m.group(0)
            for line in staged
            for m in [re.search(r"(^|/)sow/[^/]+/", line)]
            if m
        }
    )
    if len(streams) > 1:
        print(f"WARNING: staged set spans {len(streams)} stream directories.", file=sys.stderr)
        for line in staged[:8]:
            print(line, file=sys.stderr)
        print('Commit BY EXPLICIT PATHSPEC: git commit -m "..." -- <path>', file=sys.stderr)
    if "git commit" in raw and " -- " not in raw:
        print(
            "WARNING: no explicit pathspec (-- <path>). A bare commit ships the whole index.",
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
