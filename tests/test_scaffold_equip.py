"""Behavioral probes for `zeo equip <repo>` (REPO-EQUIP-SOW-5, step 2 of
REPO-EQUIP-SOW-1's charter).

`equip_repo()` installs the ALWAYS-tier files SOW-1 s1 names --
`.claude/settings.json`, `.claude/hooks/check-trunk-guard.sh`, `CLAUDE.md`,
`.claude/agents/zeo-{master,stream,sparring}.md` -- into an arbitrary WORK
repo (never a corpus). Never-clobber by default (reports "kept"); `--force`
overwrites; `--diff` previews without writing.

Every probe runs against a REAL throwaway git repo fixture (tmp_path +
`git init`), and asserts by READING FILES BACK, not by trusting the
function's return value alone -- matching this corpus's own falsification
discipline (SOW-5 s3) and the precedent set by test_scaffold_bridges.py /
test_trunk_guard_hook.py for this same charter.

NOT covered here (explicitly out of scope for this SOW): --gates, stack
detection, the override layer, --resync-check visibility, --all sweep.
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest

from zero_employee.scaffold import _stamp_content, equip_repo

_ALWAYS_PATHS = (
    ".claude/settings.json",
    ".claude/hooks/check-trunk-guard.sh",
    "CLAUDE.md",
    ".claude/agents/zeo-master.md",
    ".claude/agents/zeo-stream.md",
    ".claude/agents/zeo-sparring.md",
)

_TEMPLATES_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src" / "zero_employee" / "scaffold_templates"


def _template_text(rel_path: str) -> str:
    """Read the real shipped template content for a given ALWAYS-tier dest path."""
    mapping = {
        ".claude/settings.json": _TEMPLATES_ROOT / "claude-settings.json",
        ".claude/hooks/check-trunk-guard.sh": _TEMPLATES_ROOT / "claude-hooks" / "check-trunk-guard.sh",
        "CLAUDE.md": _TEMPLATES_ROOT / "CLAUDE.md",
        ".claude/agents/zeo-master.md": _TEMPLATES_ROOT / "agents" / "zeo-master.md",
        ".claude/agents/zeo-stream.md": _TEMPLATES_ROOT / "agents" / "zeo-stream.md",
        ".claude/agents/zeo-sparring.md": _TEMPLATES_ROOT / "agents" / "zeo-sparring.md",
    }
    return mapping[rel_path].read_text(encoding="utf-8")


def _stamped_template_text(rel_path: str) -> str:
    """The real shipped template content, stamped the same way `equip_repo()` stamps it
    when writing from the packaged default (REPO-EQUIP-SOW-7, step 3) -- what a fresh
    write actually produces on disk today, as opposed to the bare unstamped template.
    """
    return _stamp_content(rel_path, _template_text(rel_path))


def _git(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture()
def work_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A real, throwaway git repo standing in for an arbitrary work repo (not a corpus)."""
    repo = tmp_path / "work-repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    return repo


# ---------------------------------------------------------------------------
# 1. Fresh repo, no .claude/ at all: every ALWAYS-tier file is written, with
#    REAL content matching the shipped template (not a stub).
# ---------------------------------------------------------------------------


def test_equip_fresh_repo_writes_every_file_with_real_content(work_repo):
    assert not (work_repo / ".claude").exists()
    info = equip_repo(work_repo)

    actions = {a["path"]: a["action"] for a in info["actions"]}
    assert set(actions) == set(_ALWAYS_PATHS)
    assert all(action == "written" for action in actions.values())

    for rel in _ALWAYS_PATHS:
        dest = work_repo / rel
        assert dest.is_file(), f"{rel} was not written"
        assert dest.read_text(encoding="utf-8") == _stamped_template_text(rel), (
            f"{rel} content does not match the stamped shipped template"
        )

    # Sanity: content is real, not stub-shaped.
    settings_text = (work_repo / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert settings_text.strip() != '{\n  "permissions": {}\n}'
    assert "git reset --hard" in settings_text
    master_text = (work_repo / ".claude" / "agents" / "zeo-master.md").read_text(encoding="utf-8")
    assert "YOU SPAWN, YOU DO NOT EXECUTE" in master_text


# ---------------------------------------------------------------------------
# 2. Repo with an existing .claude/settings.json (different content than the
#    template): equip reports it "kept", does NOT overwrite -- read back.
# ---------------------------------------------------------------------------


def test_equip_never_clobbers_existing_file_by_default(work_repo):
    custom_dir = work_repo / ".claude"
    custom_dir.mkdir(parents=True)
    custom_settings = custom_dir / "settings.json"
    custom_content = '{"custom": "do-not-touch-me"}'
    custom_settings.write_text(custom_content, encoding="utf-8")

    info = equip_repo(work_repo)

    actions = {a["path"]: a["action"] for a in info["actions"]}
    assert actions[".claude/settings.json"] == "kept"
    # Every other ALWAYS-tier file (fresh) still gets written.
    assert actions["CLAUDE.md"] == "written"

    # The load-bearing assertion: read the file back, unchanged.
    assert custom_settings.read_text(encoding="utf-8") == custom_content


# ---------------------------------------------------------------------------
# 3. Same repo, --force: now overwrites -- read back, confirm it now matches
#    the template.
# ---------------------------------------------------------------------------


def test_equip_force_overwrites_existing_file(work_repo):
    custom_dir = work_repo / ".claude"
    custom_dir.mkdir(parents=True)
    custom_settings = custom_dir / "settings.json"
    custom_content = '{"custom": "do-not-touch-me"}'
    custom_settings.write_text(custom_content, encoding="utf-8")

    info = equip_repo(work_repo, force=True)

    actions = {a["path"]: a["action"] for a in info["actions"]}
    assert actions[".claude/settings.json"] == "overwritten"

    # The load-bearing assertion: read the file back, now matches the stamped template.
    assert custom_settings.read_text(encoding="utf-8") == _stamped_template_text(".claude/settings.json")
    assert custom_settings.read_text(encoding="utf-8") != custom_content


# ---------------------------------------------------------------------------
# 4. --diff against a repo with a modified .claude/settings.json: prints a
#    real diff, writes NOTHING -- confirmed via before/after file content
#    comparison, not just exit code.
# ---------------------------------------------------------------------------


def test_equip_diff_shows_real_diff_and_writes_nothing(work_repo):
    custom_dir = work_repo / ".claude"
    custom_dir.mkdir(parents=True)
    custom_settings = custom_dir / "settings.json"
    custom_content = '{"custom": "do-not-touch-me"}'
    custom_settings.write_text(custom_content, encoding="utf-8")

    before = {
        p: ((work_repo / p).read_text(encoding="utf-8") if (work_repo / p).exists() else None) for p in _ALWAYS_PATHS
    }

    info = equip_repo(work_repo, diff=True)

    actions = {a["path"]: a for a in info["actions"]}
    changed = actions[".claude/settings.json"]
    assert changed["action"] == "would-change"
    assert changed["diff"], "expected a real unified diff, got empty/falsy"
    assert "custom" in changed["diff"]
    assert "-{" in changed["diff"] or "-" in changed["diff"]  # unified diff has removal lines
    assert "+" in changed["diff"]  # and addition lines

    # New (not-yet-existing) files are reported as "would-create", not diffed.
    assert actions["CLAUDE.md"]["action"] == "would-create"

    # The load-bearing assertion: NOTHING was written to disk.
    after = {
        p: ((work_repo / p).read_text(encoding="utf-8") if (work_repo / p).exists() else None) for p in _ALWAYS_PATHS
    }
    assert after == before
    assert not (work_repo / "CLAUDE.md").exists()
    assert custom_settings.read_text(encoding="utf-8") == custom_content


def test_equip_diff_against_fresh_repo_all_would_create_and_writes_nothing(work_repo):
    info = equip_repo(work_repo, diff=True)
    actions = {a["path"]: a["action"] for a in info["actions"]}
    assert all(action == "would-create" for action in actions.values())
    assert not (work_repo / ".claude").exists()


# ---------------------------------------------------------------------------
# 5. Regression: the installed trunk-guard hook file is executable.
# ---------------------------------------------------------------------------


def test_equip_installed_hook_is_executable(work_repo):
    equip_repo(work_repo)
    guard = work_repo / ".claude" / "hooks" / "check-trunk-guard.sh"
    assert guard.is_file()
    assert guard.stat().st_mode & 0o111, "trunk-guard hook must be installed executable by zeo equip"


def test_equip_force_preserves_executable_bit_on_overwrite(work_repo):
    hooks_dir = work_repo / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)
    guard = hooks_dir / "check-trunk-guard.sh"
    guard.write_text("#!/usr/bin/env bash\n# CUSTOM, non-executable\nexit 0\n", encoding="utf-8")
    # Deliberately NOT chmod'd executable, to prove --force re-asserts it.
    assert not (guard.stat().st_mode & 0o111)

    equip_repo(work_repo, force=True)

    assert guard.stat().st_mode & 0o111, "force-overwrite must (re)install the hook executable"
    assert guard.read_text(encoding="utf-8") == _stamped_template_text(".claude/hooks/check-trunk-guard.sh")


# ---------------------------------------------------------------------------
# Non-.claude files (CLAUDE.md) are also covered by kept/force, not just settings.json.
# ---------------------------------------------------------------------------


def test_equip_kept_applies_to_claude_md_too(work_repo):
    custom = work_repo / "CLAUDE.md"
    custom.write_text("# my own entrypoint\n", encoding="utf-8")

    info = equip_repo(work_repo)
    actions = {a["path"]: a["action"] for a in info["actions"]}
    assert actions["CLAUDE.md"] == "kept"
    assert custom.read_text(encoding="utf-8") == "# my own entrypoint\n"
