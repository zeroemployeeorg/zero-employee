"""The two input defects the FIRST LIVE RENAME exposed (GM-DS6-165).

The mechanism was right and the inputs were wrong - the same family as every other
live-run defect in this build. Both are pinned so a plan can never again propose a name
that contradicts the frontmatter, or stamp a corpus that is really a directory.
"""

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
    d = tmp_path / "quackverse" / "sow" / "repo-hygiene"
    d.mkdir(parents=True)
    body = "\n".join(f"line {i}" for i in range(30))
    for rev in (1, 2):
        (d / f"SOW-RepoHygiene-baseline-Rev{rev}.md").write_text(
            f"---\nsow: quackverse-repo-hygiene\nn: 1\nrev: {rev}\n---\n\n{body}\n",
            encoding="utf-8",
        )
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "seed")
    return tmp_path, d


def test_sow_id_comes_from_FRONTMATTER_not_the_directory_name(corpus):
    """The dir is `repo-hygiene`; the stream is `quackverse-repo-hygiene`. The live rename
    proposed repo-hygiene-SOW-12-... and created an [n-stream] finding."""
    root, d = corpus
    rows = promote_plan(root, d)["rows"]
    assert all(r["target"].startswith("quackverse-repo-hygiene-SOW-") for r in rows), [r["target"] for r in rows]


def test_corpus_is_the_REPO_not_the_stream_dir(corpus):
    """The live rename wrote `corpus: repo-hygiene`, which is a directory, not a corpus."""
    root, d = corpus
    assert {r["corpus"] for r in promote_plan(root, d)["rows"]} == {root.resolve().name}


def test_an_explicit_sow_id_still_wins(corpus):
    root, d = corpus
    rows = promote_plan(root, d, sow_id="override")["rows"]
    assert all(r["target"].startswith("override-SOW-") for r in rows)
