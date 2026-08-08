"""--resync-apply: re-derive inherited doctrine; never overwrite locally authored files."""

from __future__ import annotations

import hashlib
import subprocess

from zero_employee.core import resync_apply, resync_check
from zero_employee import cli


def _corpus(tmp_path):
    up = tmp_path / "up"
    dn = tmp_path / "dn"
    for r in (up, dn):
        (r / "authoring").mkdir(parents=True)
        (r / "roles").mkdir(parents=True)
        subprocess.run(["git", "init"], cwd=r, check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(r), "config", "user.email", "t@example.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(r), "config", "user.name", "t"],
            check=True,
            capture_output=True,
        )
    return up, dn


def _commit_all(root, msg="seed"):
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "--allow-empty", "-m", msg],
        check=True,
        capture_output=True,
    )


def _write(root, rel, body):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_resync_apply_writes_banner_and_sha(tmp_path):
    up, dn = _corpus(tmp_path)
    src = _write(up, "authoring/a-SKILL.md", "hello from upstream\n")
    _commit_all(up)
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    _write(dn, "authoring/a-SKILL.md", f"UPSTREAM-SHA: {'0' * 64}\nstale body\n")
    _commit_all(dn)
    results = resync_apply(dn, up)
    by = {r["path"]: r for r in results}
    assert by["authoring/a-SKILL.md"]["action"] == "WRITTEN"
    assert by["authoring/a-SKILL.md"]["sha"] == sha
    text = (dn / "authoring/a-SKILL.md").read_text(encoding="utf-8")
    assert f"UPSTREAM-SHA: {sha}" in text
    assert "INHERITED DOCTRINE" in text
    assert "hello from upstream" in text
    assert resync_check(dn, up)[0][1] == "CURRENT"


def test_resync_apply_skips_locally_authored(tmp_path):
    up, dn = _corpus(tmp_path)
    _write(up, "roles/BOOT-SPARRING.md", "upstream version\n")
    _commit_all(up)
    _write(dn, "roles/BOOT-SPARRING.md", "# local only, no marker\n")
    _commit_all(dn)
    results = resync_apply(dn, up)
    by = {r["path"]: r for r in results}
    assert by["roles/BOOT-SPARRING.md"]["action"] == "SKIP"
    assert (dn / "roles/BOOT-SPARRING.md").read_text(encoding="utf-8").startswith("# local")


def test_resync_apply_creates_missing_target(tmp_path):
    up, dn = _corpus(tmp_path)
    _write(up, "authoring/new-SKILL.md", "brand new\n")
    _commit_all(up)
    _commit_all(dn)
    results = resync_apply(dn, up)
    by = {r["path"]: r for r in results}
    assert by["authoring/new-SKILL.md"]["action"] == "WRITTEN"
    assert (dn / "authoring/new-SKILL.md").is_file()


def test_resync_apply_uses_org_transforms_toml(tmp_path):
    up, dn = _corpus(tmp_path)
    _write(up, "authoring/a-SKILL.md", "corpus: sovereignagents\n")
    _commit_all(up)
    _write(dn, "authoring/a-SKILL.md", f"UPSTREAM-SHA: {'0' * 64}\n")
    conf = dn / "tools" / "doctrine" / "resync-transforms.toml"
    conf.parent.mkdir(parents=True)
    conf.write_text(
        '[substitutions]\n"corpus: sovereignagents" = "corpus: exampleorg"\n',
        encoding="utf-8",
    )
    _commit_all(dn)
    resync_apply(dn, up)
    text = (dn / "authoring/a-SKILL.md").read_text(encoding="utf-8")
    assert "corpus: exampleorg" in text
    assert "corpus: sovereignagents" not in text


def test_resync_apply_refuses_dirty_upstream(tmp_path):
    up, dn = _corpus(tmp_path)
    _write(up, "authoring/a-SKILL.md", "x\n")
    # no commit → dirty
    try:
        resync_apply(dn, up)
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "DIRTY" in str(e)


def test_cli_resync_apply(tmp_path, capsys):
    up, dn = _corpus(tmp_path)
    _write(up, "authoring/a-SKILL.md", "body\n")
    _commit_all(up)
    _write(dn, "authoring/a-SKILL.md", f"UPSTREAM-SHA: {'0' * 64}\nold\n")
    _commit_all(dn)
    rc = cli.main(["--resync-apply", str(up), str(dn)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "WRITTEN" in out
    assert "NOT COMMITTED" in out
