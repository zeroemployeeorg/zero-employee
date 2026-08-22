#!/usr/bin/env python3
"""Fail CI when public CLI/schema/template/hook/API paths change without a release fragment.

A6: patch | minor | breaking | no-user-change. Pre-1.0 breaking changes are still
`breaking` (not silently `minor`).
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess
import sys

KIND_RE = re.compile(r"(?im)^kind:\s*(patch|minor|breaking|no-user-change)\s*$")

PUBLIC_PREFIXES = (
    "src/zero_employee/cli.py",
    "src/zero_employee/__init__.py",
    "src/zero_employee/hooks.py",
    "src/zero_employee/execution.py",
    "src/zero_employee/dispatch.py",
    "src/zero_employee/schemas/",
    "src/zero_employee/scaffold_templates/",
    "src/zero_employee/hooks_templates/",
    "src/zero_employee/adapters/",
)

_REPO = pathlib.Path(__file__).resolve().parents[1]


def is_public(path: str) -> bool:
    posix = path.replace("\\", "/")
    return any(posix == p or posix.startswith(p) for p in PUBLIC_PREFIXES)


def fragment_kind(release_dir: pathlib.Path) -> str | None:
    if not release_dir.is_dir():
        return None
    for path in sorted(release_dir.iterdir()):
        if path.suffix not in {".md", ".toml"}:
            continue
        text = path.read_text(encoding="utf-8")
        m = KIND_RE.search(text)
        if m:
            return m.group(1).lower()
    return None


def git_changed(base: str) -> list[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        proc = subprocess.run(
            ["git", "diff", "--name-only", base, "HEAD"],
            cwd=_REPO,
            capture_output=True,
            text=True,
        )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"git diff failed against {base}")
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def check(changed: list[str], release_dir: pathlib.Path) -> int:
    public = [p for p in changed if is_public(p)]
    if not public:
        print("release-fragment: no public-surface paths in the diff")
        return 0
    kind = fragment_kind(release_dir)
    if kind is None:
        print(
            "release-fragment: public paths changed without a .release/ fragment "
            f"(kind: patch|minor|breaking|no-user-change). Files: {public}",
            file=sys.stderr,
        )
        return 1
    print(f"release-fragment: {kind} covers {len(public)} public path(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", nargs="+", help="Changed paths (skip git).")
    parser.add_argument("--release-dir", type=pathlib.Path, default=_REPO / ".release")
    parser.add_argument("--base", default="")
    args = parser.parse_args(argv)
    if args.files is not None:
        changed = list(args.files)
    else:
        base = args.base or os.environ.get("ZEO_RELEASE_BASE") or os.environ.get("GITHUB_BASE_SHA") or ""
        if not base:
            base = "origin/main"
        try:
            changed = git_changed(base)
        except RuntimeError as exc:
            if os.environ.get("GITHUB_ACTIONS"):
                print(f"release-fragment: {exc}", file=sys.stderr)
                return 1
            print(f"release-fragment: skip ({exc})")
            return 0
    return check(changed, args.release_dir)


if __name__ == "__main__":
    raise SystemExit(main())
