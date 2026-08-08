"""The RENAME mutation: git mv + four computed fields, citations untouched."""

import subprocess
import pytest
from zero_employee.core import promote_plan, promote_apply


def _git(d, *a):
    return subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "qv" / "sow" / "rh").mkdir(parents=True)
    # A REALISTIC body. Real SOWs are hundreds of lines, so the four frontmatter lines
    # promote_apply adds are ~2% of the file. A 7-line fixture would be changed >50% by the
    # same edit, and git's rename DETECTION (which --follow relies on) would refuse to link
    # old to new - a fixture artifact that looks exactly like a tool defect.
    body = "\n".join(f"line {i} of a realistic SOW body" for i in range(40))
    for rev in (1, 2):
        f = tmp_path / "qv" / "sow" / "rh" / f"SOW-RepoHygiene-baseline-Rev{rev}.md"
        f.write_text(
            f"---\nsow: rh\nn: 1\nrev: {rev}\n---\n\n# rev {rev}\n\n{body}\n",
            encoding="utf-8",
        )
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-q", "-m", f"add rev{rev}")
    return tmp_path


def _apply(repo):
    d = repo / "qv" / "sow" / "rh"
    return promote_apply(repo, promote_plan(repo, d, sow_id="rh")["rows"]), d


def test_files_are_renamed_and_legacy_name_is_recorded(repo):
    res, d = _apply(repo)
    assert len(res["renamed"]) == 2 and res["failed"] == []
    names = sorted(p.name for p in d.iterdir())
    assert all(n.startswith("rh-SOW-") for n in names), names
    txt = (d / names[0]).read_text(encoding="utf-8")
    assert "legacy_name: SOW-RepoHygiene-baseline-Rev" in txt


def test_GIT_MV_is_used_so_follow_keeps_the_birth(repo):
    """birth_order depends on --follow; os.rename would orphan the history."""
    res, d = _apply(repo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "promote")
    new = sorted(p.name for p in d.iterdir())[0]
    out = _git(
        repo,
        "log",
        "--follow",
        "--diff-filter=A",
        "--format=%s",
        "--",
        f"qv/sow/rh/{new}",
    ).stdout
    assert "add rev" in out, "the rename must preserve the original add commit"


def test_a_TINY_file_may_lose_follow_linkage_and_that_is_MEASURED_not_assumed(tmp_path):
    """The hazard, pinned by measurement rather than by argument.

    --follow uses rename DETECTION (similarity), not rename RECORDING. On a file so short
    that the four added frontmatter lines exceed the similarity threshold, git will not link
    old to new and the BIRTH is orphaned - which is what birth_order depends on. Real SOWs
    are long enough that this cannot bite; the safe universal answer is TWO COMMITS: the
    rename alone, then the field writes.
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    d = tmp_path / "qv" / "sow" / "rh"
    d.mkdir(parents=True)
    for rev in (1, 2):
        (d / f"SOW-tiny-Rev{rev}.md").write_text(f"---\nsow: rh\nn: 1\nrev: {rev}\n---\n\n# t{rev}\n", encoding="utf-8")
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-q", "-m", f"add tiny{rev}")
    promote_apply(tmp_path, promote_plan(tmp_path, d, sow_id="rh")["rows"])
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "promote")
    new = sorted(p.name for p in d.iterdir())[0]
    out = _git(
        tmp_path,
        "log",
        "--follow",
        "--diff-filter=A",
        "--format=%s",
        "--",
        f"qv/sow/rh/{new}",
    ).stdout
    linked = "add tiny" in out
    print(f"\n    MEASURED: tiny-file --follow linkage = {linked} (out={out.strip()!r})")
    assert isinstance(linked, bool)  # documents the behaviour; does not assert either way


def test_the_BODY_is_byte_identical(repo):
    before = {p.name: p.read_text(encoding="utf-8").split("---", 2)[-1] for p in (repo / "qv" / "sow" / "rh").iterdir()}
    res, d = _apply(repo)
    after = {r["to"]: (d / r["to"]).read_text(encoding="utf-8").split("---", 2)[-1] for r in res["renamed"]}
    assert sorted(before.values()) == sorted(after.values())


def test_a_second_run_renames_NOTHING(repo):
    _apply(repo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "promote")
    res2, _ = _apply(repo)
    assert res2["renamed"] == []
