"""The first LIVE plan renamed a charter and renumbered numbered SOWs. Both pinned here."""

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
    (tmp_path / "sow" / "gs").mkdir(parents=True)
    return tmp_path


def _add(repo, rel, body):
    (repo / rel).write_text(body, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", f"add {rel}")


def test_a_CHARTER_is_excluded_and_never_consumes_an_n(repo):
    """The live defect: the charter took n=1 and shifted every real SOW by one."""
    _add(repo, "sow/gs/Charter-GS-guide.md", "---\ngenre: charter\n---\nassigns work\n")
    _add(repo, "sow/gs/GS-SOW-01-recon.md", "---\ngenre: sow\nn: 1\n---\nbody\n")
    plan = promote_plan(repo, repo / "sow" / "gs", sow_id="gs")
    assert [e["file"].split("/")[-1] for e in plan["excluded"]] == ["Charter-GS-guide.md"]
    assert [r["n"] for r in plan["rows"]] == [1], "the SOW keeps n=1; the charter took nothing"


def test_a_DECLARED_n_is_PRESERVED_not_renumbered(repo):
    """RULING-016 s5: a rename breaks citations. SOW-04 must not become SOW-5."""
    _add(repo, "sow/gs/GS-SOW-01-a.md", "---\ngenre: sow\nn: 1\n---\nb\n")
    _add(repo, "sow/gs/GS-SOW-04-relief.md", "---\ngenre: sow\nn: 4\n---\nb\n")
    rows = {r["src"].split("/")[-1]: r["n"] for r in promote_plan(repo, repo / "sow" / "gs", sow_id="gs")["rows"]}
    assert rows["GS-SOW-04-relief.md"] == 4, "citations point at 04; it stays 04"
    assert rows["GS-SOW-01-a.md"] == 1


def test_an_UNMARKED_file_is_INCLUDED_because_exclusion_needs_evidence(repo):
    """The first cut required proof of SOW-ness and silently dropped every unmarked file.
    A migration that drops files without printing them cannot be reviewed."""
    _add(repo, "sow/gs/a.md", "no frontmatter, no sow in the name\n")
    plan = promote_plan(repo, repo / "sow" / "gs", sow_id="gs")
    assert plan["excluded"] == []
    assert [r["src"].split("/")[-1] for r in plan["rows"]] == ["a.md"]


def test_a_charter_with_NO_frontmatter_is_still_excluded_by_its_name(repo):
    _add(repo, "sow/gs/Charter-GS-guide.md", "assigns work, no frontmatter\n")
    _add(repo, "sow/gs/GS-SOW-01-a.md", "---\ngenre: sow\nn: 1\n---\nb\n")
    plan = promote_plan(repo, repo / "sow" / "gs", sow_id="gs")
    assert [e["file"].split("/")[-1] for e in plan["excluded"]] == ["Charter-GS-guide.md"]


def test_n_is_read_from_the_FILENAME_when_frontmatter_has_none(repo):
    _add(repo, "sow/gs/GS-SOW-07-legacy.md", "no frontmatter at all\n")
    rows = promote_plan(repo, repo / "sow" / "gs", sow_id="gs")["rows"]
    assert rows[0]["n"] == 7


def test_an_UNNUMBERED_sow_is_assigned_AFTER_the_highest_declared(repo):
    _add(repo, "sow/gs/GS-SOW-04-a.md", "---\ngenre: sow\nn: 4\n---\nb\n")
    _add(repo, "sow/gs/SOW-phase-legacy-no-number.md", "no frontmatter\n")
    plan = promote_plan(repo, repo / "sow" / "gs", sow_id="gs")
    ns = {r["src"].split("/")[-1]: r["n"] for r in plan["rows"]}
    assert ns["GS-SOW-04-a.md"] == 4
    assert ns["SOW-phase-legacy-no-number.md"] == 5, "assigned into the gap, not from 1"
    assert plan["assigned"] and plan["preserved"]
