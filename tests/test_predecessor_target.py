"""predecessor must name the file that will EXIST after the promote (GM-DS6-168)."""

import subprocess
import pytest
from zero_employee.core import promote_plan


def _git(d, *a):
    subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True)


@pytest.fixture
def corpus(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    d = tmp_path / "qv" / "sow" / "rh"
    d.mkdir(parents=True)
    body = "\n".join(f"line {i}" for i in range(30))
    for rev in (1, 2, 3):
        (d / f"SOW-RH-baseline-Rev{rev}.md").write_text(
            f"---\nsow: qv-rh\nn: 1\nrev: {rev}\n---\n\n{body}\n", encoding="utf-8"
        )
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-q", "-m", f"add rev{rev}")
    return tmp_path, d


def test_predecessor_names_the_TARGET_not_the_old_path(corpus):
    root, d = corpus
    rows = promote_plan(root, d)["rows"]
    targets = {r["target"] for r in rows}
    for r in rows[1:]:
        assert r["predecessor"] in targets, f"{r['predecessor']} will not exist after the promote"


def test_predecessor_is_a_BASENAME_like_legacy_name(corpus):
    root, d = corpus
    for r in promote_plan(root, d)["rows"][1:]:
        assert "/" not in r["predecessor"], r["predecessor"]


def test_genesis_is_still_none(corpus):
    root, d = corpus
    assert promote_plan(root, d)["rows"][0]["predecessor"] == "none"


def test_a_KEPT_name_is_referenced_by_its_CURRENT_name(corpus):
    """A file that keeps its name must be referenced by that name, not a proposed one."""
    root, d = corpus
    (d / "qv-rh-SOW-9-keep.md").write_text(
        "---\nsow: qv-rh\nn: 9\n---\n\n" + "\n".join(f"l{i}" for i in range(30)) + "\n",
        encoding="utf-8",
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "add keeper")
    rows = promote_plan(root, d)["rows"]
    succ = [r for r in rows if r["predecessor"] == "qv-rh-SOW-9-keep.md"]
    assert succ or rows[-1]["src"].endswith("qv-rh-SOW-9-keep.md")
