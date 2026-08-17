"""Session-wide test fixtures and safety guards.

PAID INCIDENT, 2026-08-17 (priority-nwa stream + this session's own Master worktree,
independently hit the same corruption): git hooks set GIT_DIR (and sometimes
GIT_WORK_TREE/GIT_INDEX_FILE/GIT_OBJECT_DIRECTORY) in the environment of every
subprocess a hook spawns -- this is standard, documented git behavior, not a bug in
this repo. `.githooks/pre-push` runs `uv run python -m pytest -q` as that subprocess,
so under a `git push` invocation specifically (never a direct `make verify` or
`pytest` run in an interactive shell), every test file's own git-fixture helper
inherited a real GIT_DIR pointing at THIS repo's `.git`.

Reproduced in isolation: `git -C <tmp_path> config user.email t@t` under an inherited
GIT_DIR silently IGNORES `-C` (GIT_DIR wins over `-C` in git's own precedence) and
writes into the GIT_DIR-pointed repo instead of tmp_path. This corrupted TWO
independent working trees the same session — a spawned stream's own worktree (20+
fixture "seed" commits landed on its real HEAD) and this repo's own primary `.git`
(config only: `core.bare` flipped to `true`, `user.email`/`user.name` overwritten to
the fixture identity `t <t@t>`) — both traced to the identical mechanism, discovered
independently by two different sessions within the same hour.

The fix: clear the location-affecting GIT_* variables for the whole pytest session,
autouse, so no test file's own git subprocess calls can ever resolve against
whatever repository happens to be pointed at by an inherited environment — `-C`
(or an explicit cwd) becomes authoritative again, which is what every one of these
fixtures already assumed it was getting.
"""

from __future__ import annotations

import os

import pytest

# The full set of location-affecting GIT_* variables (git's own documented list,
# `git help environment` / `man git`): GIT_DIR and GIT_WORK_TREE together control
# which repository and working tree git resolves to, overriding any -C/cwd; GIT_INDEX_FILE
# and GIT_OBJECT_DIRECTORY are usually derived from GIT_DIR but can be set
# independently and would just as surely misdirect a fixture's git calls if inherited.
_GIT_LOCATION_ENV_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)


@pytest.fixture(autouse=True)
def _no_inherited_git_location(monkeypatch):
    """Strip GIT_DIR et al. before every test, session-wide, autouse.

    Every test file in this suite that shells out to `git` (directly or via a local
    `_git(path, *args)` helper) does so assuming `-C <path>` / an explicit `cwd=`
    argument is authoritative. It is NOT, if any of these variables are already set
    in the process environment — git's own documented precedence lets GIT_DIR win
    over -C. This fixture makes that assumption true for every test, regardless of
    what invoked pytest (an interactive shell, `make verify`, or a git hook's own
    subprocess, which is exactly the invocation path that exposed the gap).
    """
    for var in _GIT_LOCATION_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    # Belt-and-suspenders against a test that reads os.environ directly rather than
    # spawning a subprocess that would inherit it — monkeypatch.delenv already
    # mutates os.environ in place, so this loop is redundant in practice; kept as an
    # explicit assertion of intent, cheap, and it fails loudly if that assumption
    # about monkeypatch's own behavior ever stops holding.
    for var in _GIT_LOCATION_ENV_VARS:
        assert var not in os.environ, f"{var} survived the autouse guard"
