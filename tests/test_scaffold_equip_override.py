"""Behavioral probes for the `zeo equip` override precedence chain and UPSTREAM-SHA
stamping (REPO-EQUIP-SOW-7, step 3 of REPO-EQUIP-SOW-1's charter).

4-level precedence, first match wins, for content of a file being WRITTEN (never for
a file already present -- that stays "kept", untouched, per step 2):

    1. <repo>/.claude/...              already present -- never clobbered (step 2, unchanged)
    2. $ZEO_TEMPLATES_DIR/...          env var, explicit
    3. ~/.config/zeo/templates/...     per-user
    4. <package>/scaffold_templates/...  shipped default

Every WRITTEN file is stamped with an UPSTREAM-SHA line hashing the CONTENT ACTUALLY
WRITTEN (the resolved override, if any -- not the packaged default), matching the hash
scope `core.py`'s `resync_apply`/`resync_check` already use: sha256 of the raw source
text, computed BEFORE the stamp/banner is added (core.py:1028-1029), never a hash of
the final stamped file.

NOT covered here (explicitly out of scope for this SOW): --gates, stack detection,
--resync-check visibility into .claude/ itself, --all sweep.
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess

import pytest

from zero_employee.core import _UPSTREAM_SHA_RE
from zero_employee.scaffold import equip_repo, resolve_template_content

_TEMPLATES_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src" / "zero_employee" / "scaffold_templates"


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


@pytest.fixture()
def fake_home(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """Fake $HOME so `~/.config/zeo/templates/` resolves under tmp_path, not the real
    machine's home dir. No existing test in this package fakes `~/.config` (checked:
    `grep -rn "Path.home|\\.home()" src/ tests/` found only this SOW's own new call site
    and one unrelated local variable named `home` in core.py) so this monkeypatches
    `pathlib.Path.home` directly, cleanly, per the SOW's own instruction for this case.
    """
    home = tmp_path / "fake-home"
    home.mkdir()
    monkeypatch.setattr(pathlib.Path, "home", lambda: home)
    # Also unset ZEO_TEMPLATES_DIR so tests that want ONLY the per-user level active
    # aren't accidentally polluted by the real environment.
    monkeypatch.delenv("ZEO_TEMPLATES_DIR", raising=False)
    return home


def _write_override(base: pathlib.Path, rel_path: str, content: str) -> pathlib.Path:
    dest = base / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# 1. No override present at any level: packaged default content is written,
#    stamped with the packaged default's OWN hash.
# ---------------------------------------------------------------------------


def test_no_override_writes_packaged_default_stamped_with_its_own_hash(work_repo, fake_home, monkeypatch):
    monkeypatch.delenv("ZEO_TEMPLATES_DIR", raising=False)

    info = equip_repo(work_repo)
    actions = {a["path"]: a for a in info["actions"]}
    assert actions["CLAUDE.md"]["source"] == "package"

    written = (work_repo / "CLAUDE.md").read_text(encoding="utf-8")
    package_body = (_TEMPLATES_ROOT / "CLAUDE.md").read_text(encoding="utf-8")

    m = _UPSTREAM_SHA_RE.search(written)
    assert m, "written file must carry a discoverable UPSTREAM-SHA stamp"
    recorded = m.group(1)
    expected = hashlib.sha256(package_body.encode("utf-8")).hexdigest()
    assert recorded == expected, "with no override, the stamp must hash the packaged default's own content"


# ---------------------------------------------------------------------------
# 2. $ZEO_TEMPLATES_DIR set, contains an override for ONE file: that file's
#    override content is written (stamped with the OVERRIDE's hash, not the
#    package's); every other file still falls through to the package default.
# ---------------------------------------------------------------------------


def test_env_var_override_for_one_file_others_stay_packaged_default(work_repo, fake_home, tmp_path, monkeypatch):
    env_dir = tmp_path / "env-templates"
    override_body = "# my org's own entrypoint override\n\noverride marker XYZ\n"
    _write_override(env_dir, "CLAUDE.md", override_body)
    monkeypatch.setenv("ZEO_TEMPLATES_DIR", str(env_dir))

    info = equip_repo(work_repo)
    actions = {a["path"]: a for a in info["actions"]}
    assert actions["CLAUDE.md"]["source"] == "env"
    assert actions[".claude/settings.json"]["source"] == "package"

    written = (work_repo / "CLAUDE.md").read_text(encoding="utf-8")
    assert "override marker XYZ" in written
    package_body = (_TEMPLATES_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "override marker XYZ" not in package_body  # sanity: real distinct content

    m = _UPSTREAM_SHA_RE.search(written)
    assert m
    recorded = m.group(1)
    override_hash = hashlib.sha256(override_body.encode("utf-8")).hexdigest()
    package_hash = hashlib.sha256(package_body.encode("utf-8")).hexdigest()
    assert recorded == override_hash, "stamp must hash the OVERRIDE's own content"
    assert recorded != package_hash, "override's stamp must differ from the package default's stamp"

    # settings.json (no override) is untouched by the CLAUDE.md-only override.
    settings_written = (work_repo / ".claude" / "settings.json").read_text(encoding="utf-8")
    package_settings = (_TEMPLATES_ROOT / "claude-settings.json").read_text(encoding="utf-8")
    assert "git reset --hard" in settings_written  # real package content, not a stub
    assert settings_written != package_settings  # differs only by the stamp key


# ---------------------------------------------------------------------------
# 3. Both $ZEO_TEMPLATES_DIR AND ~/.config/zeo/templates/ carry an override for
#    the SAME file: env var wins (level 2 before level 3). Falsified: proven
#    to fail if the fallback order were reversed.
# ---------------------------------------------------------------------------


def test_env_var_wins_over_per_user_path_when_both_set(work_repo, fake_home, tmp_path, monkeypatch):
    env_dir = tmp_path / "env-templates"
    env_body = "# ENV override wins\n"
    _write_override(env_dir, "CLAUDE.md", env_body)
    monkeypatch.setenv("ZEO_TEMPLATES_DIR", str(env_dir))

    user_body = "# per-user override, should NOT be chosen\n"
    _write_override(fake_home, ".config/zeo/templates/CLAUDE.md", user_body)

    content, source = resolve_template_content("CLAUDE.md")
    assert source == "env"
    assert content == env_body

    info = equip_repo(work_repo)
    actions = {a["path"]: a for a in info["actions"]}
    assert actions["CLAUDE.md"]["source"] == "env"
    written = (work_repo / "CLAUDE.md").read_text(encoding="utf-8")
    assert "ENV override wins" in written
    assert "should NOT be chosen" not in written


def test_falsify_precedence_order_would_fail_if_reversed(work_repo, fake_home, tmp_path, monkeypatch):
    """Falsification discipline (SOW-7 s3 item 7): confirm the precedence-order test
    above would actually FAIL if the fallback order were accidentally reversed, rather
    than trusting it passes for the right reason. Simulates the reversed order directly
    (checking per-user before env var) without touching production code, and asserts
    that reversed resolution picks the WRONG (per-user) content -- proving the real
    test above is sensitive to get-the-order-right, not vacuously true.
    """
    env_dir = tmp_path / "env-templates"
    env_body = "# ENV override wins\n"
    _write_override(env_dir, "CLAUDE.md", env_body)
    monkeypatch.setenv("ZEO_TEMPLATES_DIR", str(env_dir))

    user_body = "# per-user override, should NOT be chosen\n"
    _write_override(fake_home, ".config/zeo/templates/CLAUDE.md", user_body)

    # Real resolution: env wins.
    content, source = resolve_template_content("CLAUDE.md")
    assert source == "env"
    assert content == env_body

    # Reversed-order simulation (per-user checked BEFORE env var) -- the bug this test
    # exists to catch, reproduced locally rather than by mutating scaffold.py.
    user_path = fake_home / ".config" / "zeo" / "templates" / "CLAUDE.md"
    if user_path.is_file():
        reversed_content, reversed_source = user_path.read_text(encoding="utf-8"), "user"
    else:
        import os

        env_path = pathlib.Path(os.environ["ZEO_TEMPLATES_DIR"]) / "CLAUDE.md"
        reversed_content, reversed_source = env_path.read_text(encoding="utf-8"), "env"

    assert reversed_source == "user"
    assert reversed_content == user_body
    # The load-bearing falsification: reversed resolution disagrees with the real,
    # correctly-ordered resolution -- proving the real precedence test is not vacuous.
    assert reversed_content != content
    assert reversed_source != source


# ---------------------------------------------------------------------------
# 4. ~/.config/zeo/templates/ override alone (no env var set): falls to level 3.
# ---------------------------------------------------------------------------


def test_per_user_path_alone_no_env_var(work_repo, fake_home, monkeypatch):
    monkeypatch.delenv("ZEO_TEMPLATES_DIR", raising=False)
    user_body = "# per-user override, no env var involved\n"
    _write_override(fake_home, ".config/zeo/templates/CLAUDE.md", user_body)

    content, source = resolve_template_content("CLAUDE.md")
    assert source == "user"
    assert content == user_body

    info = equip_repo(work_repo)
    actions = {a["path"]: a for a in info["actions"]}
    assert actions["CLAUDE.md"]["source"] == "user"
    written = (work_repo / "CLAUDE.md").read_text(encoding="utf-8")
    assert "per-user override, no env var involved" in written

    m = _UPSTREAM_SHA_RE.search(written)
    assert m
    assert m.group(1) == hashlib.sha256(user_body.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 5. A file the repo already has: stays "kept" regardless of what ANY override
#    level contains -- never-clobber is untouched by the precedence chain.
# ---------------------------------------------------------------------------


def test_pre_existing_repo_file_stays_kept_regardless_of_any_override_level(
    work_repo, fake_home, tmp_path, monkeypatch
):
    existing_content = "# repo's own CLAUDE.md, must never be touched\n"
    (work_repo / "CLAUDE.md").write_text(existing_content, encoding="utf-8")

    env_dir = tmp_path / "env-templates"
    _write_override(env_dir, "CLAUDE.md", "# env override, must not apply either\n")
    monkeypatch.setenv("ZEO_TEMPLATES_DIR", str(env_dir))
    _write_override(fake_home, ".config/zeo/templates/CLAUDE.md", "# user override, must not apply either\n")

    info = equip_repo(work_repo)
    actions = {a["path"]: a for a in info["actions"]}
    assert actions["CLAUDE.md"]["action"] == "kept"
    assert "source" not in actions["CLAUDE.md"], (
        "a kept file's content is never resolved -- level 1 never reads FROM anything"
    )

    # Load-bearing: read back from disk, byte-identical to what was there before.
    assert (work_repo / "CLAUDE.md").read_text(encoding="utf-8") == existing_content


# ---------------------------------------------------------------------------
# 6. Stamp verification: extract UPSTREAM-SHA via the SAME regex core.py uses,
#    independently compute sha256, confirm match -- using the SAME hash scope
#    resync_check()/resync_apply() use (pre-stamp source content, not the final
#    stamped file's own bytes; see core.py:1028-1029).
# ---------------------------------------------------------------------------


def test_stamp_verification_matches_independently_computed_hash_of_resolved_content(
    work_repo, fake_home, tmp_path, monkeypatch
):
    env_dir = tmp_path / "env-templates"
    override_body = "#!/usr/bin/env bash\n# an overridden trunk-guard hook\nexit 0\n"
    _write_override(env_dir, "claude-hooks/check-trunk-guard.sh", override_body)
    monkeypatch.setenv("ZEO_TEMPLATES_DIR", str(env_dir))

    equip_repo(work_repo)
    written = (work_repo / ".claude" / "hooks" / "check-trunk-guard.sh").read_text(encoding="utf-8")

    m = _UPSTREAM_SHA_RE.search(written)
    assert m, "hook stamp must be discoverable via the same regex core.py's resync_check() uses"
    recorded = m.group(1)

    # Independently compute sha256 of the RESOLVED content (pre-stamp) -- the same
    # scope core.py's resync_apply() uses (hash `src` before the banner is inserted;
    # core.py:1028-1029), not a hash of the final written file (which would be
    # circular -- the stamp line is part of that file's bytes).
    independent = hashlib.sha256(override_body.encode("utf-8")).hexdigest()
    assert recorded == independent

    # Cross-check: hashing the file's OWN full body (stamp line included) must NOT
    # match -- proving the scope really is pre-stamp source, not the file as a whole.
    whole_file_hash = hashlib.sha256(written.encode("utf-8")).hexdigest()
    assert whole_file_hash != recorded


# ---------------------------------------------------------------------------
# Known, named gap: .claude/settings.json is strict JSON (Claude Code has no
# JSONC/comment tolerance), so its UPSTREAM-SHA marker lives inside a JSON
# string value and is NOT currently discoverable by `_UPSTREAM_SHA_RE`'s
# line-start anchor. The file must stay valid JSON regardless.
# ---------------------------------------------------------------------------


def test_settings_json_stays_valid_json_and_carries_a_greppable_marker(work_repo, fake_home, monkeypatch):
    import json

    monkeypatch.delenv("ZEO_TEMPLATES_DIR", raising=False)
    equip_repo(work_repo)
    written = (work_repo / ".claude" / "settings.json").read_text(encoding="utf-8")

    data = json.loads(written)  # must not raise -- settings.json is live-loaded by Claude Code
    assert "_upstreamSha" in data
    assert data["_upstreamSha"].startswith("UPSTREAM-SHA: ")
    assert "git reset --hard" in written  # still real content, not a stub

    # Named, honest gap: the shared regex does not currently discover this stamp,
    # because JSON can never place the marker text at true line-start.
    assert _UPSTREAM_SHA_RE.search(written) is None
