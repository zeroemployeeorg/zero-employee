"""Git worktree lifecycle + commit trailer helpers."""

from __future__ import annotations

import subprocess

from zero_employee.scaffold import init_corpus
from zero_employee.workspace import (
    branch_name,
    commit_message_has_required_trailers,
    create,
    list_workspaces,
    retire,
    sparring_may_stage,
)


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_worktree_create_list_retire(tmp_path):
    host = tmp_path / "code"
    host.mkdir()
    _git(host, "init", "-b", "main")
    _git(host, "config", "user.email", "t@example.com")
    _git(host, "config", "user.name", "t")
    (host / "f.txt").write_text("x\n", encoding="utf-8")
    _git(host, "add", "f.txt")
    _git(host, "commit", "-m", "root")
    corpus = tmp_path / "org"
    init_corpus(corpus)
    info = create(corpus, seat="sparring", instance_id="sparring-wt-1", host_repo=host)
    assert info["branch"] == branch_name("sparring", "sparring-wt-1")
    assert (host / ".zeo" / "worktrees" / "sparring-wt-1").is_dir()
    rows = list_workspaces(corpus)
    assert any(r["instance_id"] == "sparring-wt-1" for r in rows)
    retired = retire(corpus, "sparring-wt-1")
    assert retired["instance"]["status"] == "retired"


def test_trailers_and_sparring_paths(monkeypatch):
    monkeypatch.delenv("ZEO_SEAT", raising=False)
    monkeypatch.delenv("ZEO_INSTANCE_ID", raising=False)
    assert commit_message_has_required_trailers("no trailers") is True
    monkeypatch.setenv("ZEO_SEAT", "sparring")
    monkeypatch.setenv("ZEO_INSTANCE_ID", "sparring-1")
    assert commit_message_has_required_trailers("msg") is False
    assert commit_message_has_required_trailers("msg\n\nZEO-Seat: sparring\nZEO-Instance: sparring-1\n") is True
    assert sparring_may_stage(["ruling/X.md"]) is True
    assert sparring_may_stage(["src/foo.py"]) is False
