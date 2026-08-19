"""The s4 packaging guarantee (REPO-EQUIP-SOW-1 s4 / SOW-4).

`pyproject.toml`'s wheel target used to enumerate every scaffold/hook template
file BY HAND in `force-include`. A new template file added to
`scaffold_templates/` or `hooks_templates/` on disk would silently NOT ship in
the built wheel unless someone remembered to add a line for it -- a
silent, install-time-only failure that works for the developer (editable
install reads straight off disk) and is broken for every `pip install` user.

The charter's own words: "Prefer replacing the hand-list with a directory-
level include if hatchling supports it cleanly; keep the test regardless --
the test is the guarantee, the config is the implementation." This module IS
that guarantee. It does not trust that `pyproject.toml` is configured
correctly -- it BUILDS the real wheel with the real build backend and diffs
its actual contents against the real template directories on disk. If a
future edit to `pyproject.toml` (an `include`/`only-include` restriction, a
reintroduced hand-list that falls out of date, anything) makes a template
file stop shipping, this test fails -- it does not matter why.

Slower than the rest of the suite (invokes `uv build`), so the wheel is built
once per test session and cached across the module's tests.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import zipfile

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover -- py3.11+ ships tomllib; floor is 3.11
    import tomli as tomllib  # type: ignore[no-redef]

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# The two on-disk template trees this guarantee covers. Both are walked by
# hatchling's default project-file inclusion today (see the comment above
# `[tool.hatch.build.targets.wheel]` in pyproject.toml) -- this test does not
# assume that stays true, it PROVES it stays true, every run.
_TEMPLATE_DIRS = ("scaffold_templates", "hooks_templates")


def _walk_template_files(root: pathlib.Path) -> set[str]:
    """Every file under src/zero_employee/<dir>, as a package-relative posix path."""
    out: set[str] = set()
    for dirname in _TEMPLATE_DIRS:
        base = root / "src" / "zero_employee" / dirname
        assert base.is_dir(), f"expected template dir missing on disk: {base}"
        for p in base.rglob("*"):
            if p.is_file():
                rel = p.relative_to(root / "src").as_posix()
                out.add(rel)
    return out


@pytest.fixture(scope="module")
def built_wheel_path(tmp_path_factory) -> pathlib.Path:
    """Build the real wheel via `uv build` once per module and return its path.

    A real subprocess build, not a mock of hatchling's config resolution --
    the whole point of this guarantee is to catch what the BUILD actually
    does, not what the config merely claims to do. Other fixtures/tests that
    need the wheel's bytes (not just its member list) depend on this instead
    of re-shelling a second build.
    """
    out_dir = tmp_path_factory.mktemp("wheel-out")
    result = subprocess.run(
        ["uv", "build", "--wheel", "-o", str(out_dir)],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"uv build failed (rc={result.returncode}):\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    wheels = sorted(out_dir.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one built wheel, found {wheels}"
    return wheels[0]


@pytest.fixture(scope="module")
def built_wheel_members(built_wheel_path) -> set[str]:
    """The built wheel's member paths (filenames only, no content)."""
    with zipfile.ZipFile(built_wheel_path) as zf:
        return set(zf.namelist())


def test_uv_and_python_available():
    """Sanity precondition -- fail with a clear reason, not a cryptic subprocess error."""
    assert subprocess.run(["uv", "--version"], capture_output=True).returncode == 0
    assert sys.version_info >= (3, 11)


def test_every_disk_template_file_ships_in_the_wheel(built_wheel_members):
    """The guarantee: nothing under scaffold_templates/ or hooks_templates/ on
    disk is missing from the built wheel.

    This is deliberately the inverse framing of "the config lists these
    files" -- it starts from disk (ground truth for what a maintainer added)
    and demands the wheel contain it, rather than starting from the config
    and demanding disk match the config. A stub or hand-list can lie by
    omission; disk cannot.
    """
    on_disk = _walk_template_files(_REPO_ROOT)
    assert on_disk, "expected at least one template file on disk to test against"

    missing = sorted(rel for rel in on_disk if f"zero_employee/{rel.split('/', 1)[1]}" not in built_wheel_members)
    assert not missing, (
        f"{len(missing)} template file(s) on disk are NOT in the built wheel "
        f"(this is the exact s4 packaging trap): {missing}"
    )


def test_the_new_trunk_guard_hook_specifically_ships(built_wheel_members):
    """Named regression guard for the exact file this SOW step added.

    Belt-and-suspenders on top of the general walk above: if someone narrows
    `pyproject.toml`'s wheel inclusion in a way that happens to keep every
    CURRENT template but would silently drop a class of file this test
    doesn't enumerate by name, this still catches the one file s5's entire
    behavioral backlog depends on shipping.
    """
    assert "zero_employee/scaffold_templates/claude-hooks/check-trunk-guard.sh" in built_wheel_members


def test_py_typed_marker_ships_so_the_typed_classifier_is_actually_true(built_wheel_members):
    """`pyproject.toml`'s classifiers claim `"Typing :: Typed"`, and the README badges
    that claim too -- but a classifier is metadata a type checker never reads. What a
    type checker (mypy/pyright) actually looks for is `zero_employee/py.typed` inside
    the installed package; without it, every downstream user importing this package
    silently gets untyped stubs regardless of what PyPI's page says. MEASURED before
    this test existed: the marker file was absent from `src/`, so the classifier was
    already false. This is the guarantee that stays true going forward."""
    assert "zero_employee/py.typed" in built_wheel_members


def test_zeo_stream_template_does_not_cite_the_nonexistent_boot_little_claude():
    """Regression guard for a real, live bug shipped in v0.1.7 through v0.3.1: the
    stream seat template's @import list named `roles/BOOT-LITTLE-CLAUDE.md`, a file
    that has never existed under that name in any corpus this tool's doctrine came
    from -- the real file is `roles/BOOT-SUBAGENT.md`. `zeroemployeeorg/org`'s own
    canonical CLAUDE.md already corrected this exact ghost-precedent IN PROSE on
    2026-08-16 (`claude-md/CLAUDE.md` names it explicitly), but the shipped package
    template that `zeo equip` actually writes into every work repo was never updated
    to match -- so every `zeo equip` since kept carrying the stale reference forward,
    silently: `scaffold.py`'s missing-import handling degrades to a
    `<!-- @import missing: ... -->` comment rather than an error, so a booting stream
    seat got a quietly doctrine-less boot instead of a loud failure. MEASURED live:
    found while equipping a brand-new org (ducktyper-ai/org, 2026-08-17) and
    confirmed by grep against this exact file before this test existed."""
    path = _REPO_ROOT / "src" / "zero_employee" / "scaffold_templates" / "agents" / "zeo-stream.md"
    text = path.read_text(encoding="utf-8")
    assert "BOOT-LITTLE-CLAUDE" not in text, "the stream template must not cite the nonexistent BOOT-LITTLE-CLAUDE.md"
    assert "@roles/BOOT-SUBAGENT.md" in text, "the stream template must import the real file, BOOT-SUBAGENT.md"


def test_pyproject_declares_both_zeo_and_sow_lint_entry_points_at_the_same_target():
    """RULING-251 s3 / ZEO-RELEASE-CHARTER-01 s2.1 / RULING-319: `sow-lint` is RETAINED,
    never deprecated -- 227+ immutable corpus references (landed rulings, filed SOWs)
    name it in their `check:` fields, and RULING-004 s5's append-dont-revert means those
    checks must stay RUNNABLE forever. It was silently dropped from
    `[project.scripts]` at 09bbbf2 (2026-08-09, "clean-cut rebranding") along with its
    own explanatory comment -- a regression the charter's own DoD explicitly forbids
    ("sow-lint working after install is part of your DoD too"). This is the static,
    fast half of the guarantee: parse the real `pyproject.toml` directly (not a copy,
    not an assumption) and demand both names resolve to the SAME entry function, so
    a future edit cannot reintroduce the old `main` target for one name and the new
    `cli_entry` for the other and have them silently diverge in behavior.
    """
    data = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = data["project"]["scripts"]
    assert "zeo" in scripts, "the zeo entry point is missing from [project.scripts]"
    assert "sow-lint" in scripts, (
        "sow-lint entry point is missing from [project.scripts] -- it is RETAINED, "
        "never deprecated (ZEO-RELEASE-CHARTER-01 s2.1, RULING-251 s3 remediation); "
        "227+ immutable corpus references depend on it staying runnable"
    )
    assert scripts["zeo"] == scripts["sow-lint"], (
        f"zeo ({scripts['zeo']!r}) and sow-lint ({scripts['sow-lint']!r}) must point at "
        "the identical entry function so both names run the same CLI"
    )


def test_built_wheel_metadata_exposes_both_console_scripts(built_wheel_path, built_wheel_members):
    """The behavioral half of the same guarantee: not just that `pyproject.toml`
    SAYS both names exist, but that a real `uv build` actually produced a wheel
    whose installed `entry_points.txt` (the file `pip`/`uv tool install` actually
    reads to create the `~/.local/bin/{zeo,sow-lint}` shims) carries BOTH console
    scripts, each resolving to `zero_employee.cli:cli_entry`. Presence of the
    metadata file alone would only prove SOME entry_points.txt shipped -- this
    reads its real bytes so a build that ships the file but drops one script
    (or points it at the wrong/dead `main` target) still fails here. This
    project's own packaging doctrine (see the module docstring above) is
    "prove the wheel, not the config."
    """
    dist_info_names = {n for n in built_wheel_members if n.endswith(".dist-info/entry_points.txt")}
    assert len(dist_info_names) == 1, f"expected exactly one dist-info entry_points.txt, found {dist_info_names}"
    (member,) = dist_info_names
    with zipfile.ZipFile(built_wheel_path) as zf:
        text = zf.read(member).decode("utf-8")
    assert "zeo = zero_employee.cli:cli_entry" in text, (
        f"zeo console script missing/wrong target in built wheel metadata:\n{text}"
    )
    assert "sow-lint = zero_employee.cli:cli_entry" in text, (
        f"sow-lint console script missing/wrong target in built wheel metadata -- "
        f"RULING-251 s3 remediation regressed:\n{text}"
    )


def test_claude_settings_template_is_no_longer_the_empty_stub():
    """Regression guard for the charter's own headline finding.

    src/zero_employee/scaffold_templates/claude-settings.json used to be
    literally `{"permissions": {}}` -- an empty stub that (per s5 item 1)
    would silently un-deny `git reset --hard`, `rm -rf`, publish/deploy, and
    `.env` reads for any repo scaffolded with it.
    """
    path = _REPO_ROOT / "src" / "zero_employee" / "scaffold_templates" / "claude-settings.json"
    text = path.read_text(encoding="utf-8")
    assert text.strip() != '{\n  "permissions": {}\n}'
    for needed in (
        '"Bash(git reset --hard:*)"',
        '"Bash(rm -rf:*)"',
        '"Read(./.env)"',
        '"Read(./**/.env)"',
        '"Bash(npm publish:*)"',
        '"Bash(uv publish:*)"',
        '"Bash(vercel:*)"',
    ):
        assert needed in text, f"deny list missing {needed!r}"
    assert "check-trunk-guard.sh" in text, "settings.json must wire the trunk-guard hook"
