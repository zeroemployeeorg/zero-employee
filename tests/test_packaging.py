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
def built_wheel_members(tmp_path_factory) -> set[str]:
    """Build the real wheel via `uv build` and return its member paths.

    A real subprocess build, not a mock of hatchling's config resolution --
    the whole point of this guarantee is to catch what the BUILD actually
    does, not what the config merely claims to do.
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
    with zipfile.ZipFile(wheels[0]) as zf:
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
