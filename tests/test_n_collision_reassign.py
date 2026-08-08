"""n-collision is the largest failure class (77). The declared n is the defect, not the truth.

MEASURED: 22 repo-hygiene files all declare n:1 because the legacy -RevN convention put the
revision in the FILENAME and left n static. Preserving that declaration preserves the defect.
"""

import subprocess
import pytest
from zero_employee.core import promote_plan


def _git(d, *a):
    subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "quackverse" / "sow" / "rh").mkdir(parents=True)
    return tmp_path


def _add(repo, rel, body):
    (repo / rel).write_text(body, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", f"add {rel}")


def test_a_colliding_GROUP_is_reassigned_in_birth_order(repo):
    """The real case: every -RevN file declares n:1."""
    for rev in (1, 2, 3):
        _add(
            repo,
            f"quackverse/sow/rh/SOW-RepoHygiene-baseline-Rev{rev}.md",
            f"---\nsow: rh\nn: 1\nrev: {rev}\n---\nbody {rev}\n",
        )
    plan = promote_plan(repo, repo / "quackverse" / "sow" / "rh", sow_id="rh")
    ns = [r["n"] for r in plan["rows"]]
    assert sorted(ns) == [1, 2, 3], f"a colliding group must be renumbered, got {ns}"
    assert len(plan["collided"]) == 3
    assert plan["preserved"] == []


def test_the_ELDEST_keeps_the_lowest_n(repo):
    for rev in (1, 2):
        _add(
            repo,
            f"quackverse/sow/rh/SOW-RepoHygiene-baseline-Rev{rev}.md",
            f"---\nsow: rh\nn: 1\nrev: {rev}\n---\nbody {rev}\n",
        )
    rows = {
        r["src"].split("/")[-1]: r["n"]
        for r in promote_plan(repo, repo / "quackverse" / "sow" / "rh", sow_id="rh")["rows"]
    }
    assert rows["SOW-RepoHygiene-baseline-Rev1.md"] == 1
    assert rows["SOW-RepoHygiene-baseline-Rev2.md"] == 2


def test_a_UNIQUE_n_is_still_never_touched(repo):
    """Renumbering a validly-numbered file breaks citations (RULING-016 s5)."""
    _add(repo, "quackverse/sow/rh/rh-SOW-7-a.md", "---\nsow: rh\nn: 7\n---\nb\n")
    _add(repo, "quackverse/sow/rh/rh-SOW-9-b.md", "---\nsow: rh\nn: 9\n---\nb\n")
    plan = promote_plan(repo, repo / "quackverse" / "sow" / "rh", sow_id="rh")
    assert sorted(r["n"] for r in plan["rows"]) == [7, 9]
    assert plan["collided"] == []


def test_a_MIX_preserves_the_unique_and_renumbers_the_rest_ABOVE_it(repo):
    _add(repo, "quackverse/sow/rh/rh-SOW-9-keep.md", "---\nsow: rh\nn: 9\n---\nb\n")
    for rev in (1, 2):
        _add(
            repo,
            f"quackverse/sow/rh/SOW-dup-Rev{rev}.md",
            f"---\nsow: rh\nn: 1\nrev: {rev}\n---\nb{rev}\n",
        )
    rows = {
        r["src"].split("/")[-1]: r["n"]
        for r in promote_plan(repo, repo / "quackverse" / "sow" / "rh", sow_id="rh")["rows"]
    }
    assert rows["rh-SOW-9-keep.md"] == 9, "the unique n survives"
    assert sorted([rows["SOW-dup-Rev1.md"], rows["SOW-dup-Rev2.md"]]) == [10, 11]
