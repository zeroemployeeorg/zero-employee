"""RULING-093: promote_plan COMPUTES the rename plan and writes nothing.

A dry run exists so a bad slug or a collision is visible BEFORE 313 renames, not after.
"""

import subprocess
import pytest
from zero_employee.core import promote_plan, slug_from


def _git(d, *a):
    subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "sow" / "seam").mkdir(parents=True)
    return tmp_path


def _commit(repo, rel, body=None):
    (repo / rel).write_text(body or f"# {rel}\nunique {rel}\n", encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", f"add {rel}")


def test_slug_strips_rev_suffix_and_sow_lead():
    assert slug_from("SOW-TrackA-core-fs-completion-Rev18.md").endswith("core-fs-completion")
    assert "rev" not in slug_from("sow-phase-fx-6-addendum-rev-c.md").split("-")[-1]


def test_plan_assigns_n_in_birth_order_and_writes_NOTHING(repo):
    _commit(repo, "sow/seam/SEAM-second.md")  # born FIRST
    _commit(repo, "sow/seam/AAA-first.md")  # born SECOND, sorts first by name
    before = sorted(p.name for p in (repo / "sow" / "seam").iterdir())
    plan = promote_plan(repo, repo / "sow" / "seam", sow_id="seam")
    assert [r["n"] for r in plan["rows"]] == [1, 2]
    assert plan["rows"][0]["src"].endswith("SEAM-second.md"), "birth order, not alphabetical"
    assert sorted(p.name for p in (repo / "sow" / "seam").iterdir()) == before, "NOTHING written"


def test_predecessor_rides_the_same_pass_and_genesis_is_explicit(repo):
    _commit(repo, "sow/seam/a.md")
    _commit(repo, "sow/seam/b.md")
    rows = promote_plan(repo, repo / "sow" / "seam", sow_id="seam")["rows"]
    assert rows[0]["predecessor"] == "none"
    # SUPERSEDED by this seat's own fix (GM-DS6-170): predecessor named the
    # pre-rename SRC PATH, so after a promote every link pointed at a file the
    # same run had renamed away. It now names the predecessor's FINAL basename.
    assert rows[1]["predecessor"] == rows[0]["target"]


def test_corpus_is_the_repo_the_file_lives_in(repo):
    _commit(repo, "sow/seam/a.md")
    assert promote_plan(repo, repo / "sow" / "seam", sow_id="seam")["rows"][0]["corpus"] == repo.name


def test_a_collision_is_REPORTED_and_the_plan_still_writes_nothing(repo, monkeypatch):
    import zero_employee.core as core

    monkeypatch.setattr(core, "canonical_name", lambda s, n, sl: "same-SOW-1-x.md")
    _commit(repo, "sow/seam/a.md")
    _commit(repo, "sow/seam/b.md")
    plan = promote_plan(repo, repo / "sow" / "seam", sow_id="seam")
    assert len(plan["collisions"]) == 1
    assert sorted(next(iter(plan["collisions"].values()))) == sorted([r["src"] for r in plan["rows"]])


def test_an_untracked_file_is_named_because_git_has_no_birth_for_it(repo):
    _commit(repo, "sow/seam/tracked.md")
    (repo / "sow" / "seam" / "loose.md").write_text("# loose\nunique\n", encoding="utf-8")
    plan = promote_plan(repo, repo / "sow" / "seam", sow_id="seam")
    assert [u.split("/")[-1] for u in plan["untracked"]] == ["loose.md"]
