"""Relative invocation - the normal way an operator runs it - must work.

PAID (GM-DS6-166): `sow-lint --promote quackverse/sow/repo-hygiene` raised
ValueError: not in the subpath. Every fixture uses tmp_path, which is ALWAYS absolute, so
229 tests were green against a CLI that crashed on its first real relative invocation.
"""

import subprocess
import pytest
from zero_employee.core import promote_plan, project_backfill_plan, citation_scan


def _git(d, *a):
    subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True)


@pytest.fixture
def corpus(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    d = tmp_path / "quackverse" / "sow" / "rh"
    d.mkdir(parents=True)
    body = "\n".join(f"line {i}" for i in range(30))
    for rev in (1, 2):
        (d / f"SOW-RepoHygiene-baseline-Rev{rev}.md").write_text(
            f"---\nsow: quackverse-repo-hygiene\nn: 1\nrev: {rev}\n---\n\n{body}\n",
            encoding="utf-8",
        )
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "seed")
    return tmp_path


def test_promote_plan_accepts_a_RELATIVE_stream_dir(corpus, monkeypatch):
    """The exact live invocation: cwd = corpus root, path = relative."""
    monkeypatch.chdir(corpus)
    rows = promote_plan(".", "quackverse/sow/rh")["rows"]
    assert len(rows) == 2
    assert all(r["target"].startswith("quackverse-repo-hygiene-SOW-") for r in rows)


def test_project_backfill_plan_accepts_a_RELATIVE_root(corpus, monkeypatch):
    monkeypatch.chdir(corpus)
    assert isinstance(project_backfill_plan(".")["rows"], list)


def test_citation_scan_accepts_RELATIVE_roots(corpus, monkeypatch):
    monkeypatch.chdir(corpus)
    assert isinstance(citation_scan(".", {"a.md": "b.md"}), dict)


def test_a_MIXED_absolute_root_and_relative_stream_dir_works(corpus, monkeypatch):
    """The live case exactly: root absolute (from corpus_root), stream_dir relative."""
    monkeypatch.chdir(corpus)
    rows = promote_plan(str(corpus), "quackverse/sow/rh")["rows"]
    assert len(rows) == 2
