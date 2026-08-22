"""A5: exclusive ownership, remote-advancement detection, failed-state preservation."""

from __future__ import annotations

import subprocess

import pytest

from zero_employee import dispatch
from zero_employee.cli import main


def _git(repo, *args, check=True):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _bare_remote(tmp_path, name="remote.git"):
    remote = tmp_path / name
    _git(tmp_path, "init", "--bare", "-b", "main", str(remote))
    return remote


def _repo_with_remote(tmp_path):
    remote = _bare_remote(tmp_path)
    repo = tmp_path / "work"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "remote", "add", "origin", str(remote))
    (repo / "f.txt").write_text("root\n", encoding="utf-8")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-q", "-m", "root")
    _git(repo, "push", "-q", "origin", "main")
    return repo


def test_second_live_owner_is_refused_with_receipt(tmp_path):
    repo = _repo_with_remote(tmp_path)
    key = dispatch.ownership_key(repository="work", branch="agent/a")
    first = dispatch.acquire(repo, key=key, execution_id="exec_1", branch="agent/a")
    assert first.acquired is True
    second = dispatch.acquire(repo, key=key, execution_id="exec_2", branch="agent/a")
    assert second.acquired is False
    assert second.receipt_path is not None
    assert second.receipt_path.is_file()
    text = second.receipt_path.read_text(encoding="utf-8")
    assert "duplicate live ownership" in text
    assert '"termination": "aborted"' in text


def test_cli_acquire_contention(tmp_path):
    repo = _repo_with_remote(tmp_path)
    assert main(["dispatch", "acquire", "--repo", str(repo), "--branch", "agent/a", "--execution-id", "e1"]) == 0
    assert main(["dispatch", "acquire", "--repo", str(repo), "--branch", "agent/a", "--execution-id", "e2"]) == 1


def test_remote_branch_advancement_is_detected(tmp_path):
    repo = _repo_with_remote(tmp_path)
    _git(repo, "checkout", "-q", "-b", "agent/a")
    (repo / "f.txt").write_text("one\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "one")
    _git(repo, "push", "-q", "-u", "origin", "agent/a")
    pinned = dispatch.pin_head_sha(repo)

    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", str(tmp_path / "remote.git"), str(other))
    _git(other, "checkout", "-q", "agent/a")
    _git(other, "config", "user.email", "t@example.com")
    _git(other, "config", "user.name", "Test")
    (other / "f.txt").write_text("two\n", encoding="utf-8")
    _git(other, "commit", "-q", "-am", "two")
    _git(other, "push", "-q", "origin", "agent/a")

    with pytest.raises(dispatch.DispatchError, match="advanced"):
        dispatch.check_remote_advancement(repo, "agent/a", pinned)

    with pytest.raises(dispatch.DispatchError):
        dispatch.push_with_lease(repo, "agent/a", pinned)


def test_failed_lock_preserved_until_authorized_cleanup(tmp_path):
    repo = _repo_with_remote(tmp_path)
    key = dispatch.ownership_key(repository="work", branch="agent/a")
    dispatch.acquire(repo, key=key, execution_id="exec_fail", branch="agent/a")
    dispatch.set_status(repo, key, dispatch.FAILED)
    with pytest.raises(dispatch.DispatchError, match="preserved"):
        dispatch.cleanup(repo, key, authorize=False)
    lock = dispatch.cleanup(repo, key, authorize=True)
    assert lock["status"] == dispatch.CLEANED


def test_label_is_not_a_lock_key():
    with pytest.raises(dispatch.DispatchError, match="branch"):
        dispatch.ownership_key(repository="work")
    k = dispatch.ownership_key(repository="work", stream="example")
    assert "stream:example" in k
