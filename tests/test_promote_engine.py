"""RULING-093 s3/s4/s6: the --promote engine.

Proven against a real git repo because the whole claim is that BIRTH ORDER is git ground,
not a heuristic - and because ordering by NAME has now failed three ways in this corpus
(lexical: RULING-063 s5.4; parsed-Rev: RULING-066 s4; the rev-matcher: defect (c)).
"""

import subprocess
import pytest
from zero_employee.core import (
    birth_order,
    assign_n,
    canonical_name,
    collisions,
    predecessor_map,
)


def _git(d, *a):
    subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q") if False else subprocess.run(
        ["git", "init", "-q", str(tmp_path)], check=True, capture_output=True
    )
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    return tmp_path


def _commit(repo, name, body=None):
    # DISTINCT bytes per file: identical content makes --follow's rename detection link
    # unrelated files and report the elder's birth for both (GM-DIAG-137). That is a real
    # git property; a fixture must not simulate it by accident.
    (repo / name).write_text(body or f"# {name}\n\nunique body for {name}\n", encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", f"add {name}")
    return name


def test_birth_order_is_COMMIT_order_not_alphabetical(repo):
    """The defect this kills: 'Rev18' sorts before 'Rev7' lexically and before 'Rev9'
    under a naive parsed sort when families mix. Git knows which came first."""
    _commit(repo, "zebra-SOW.md")  # born FIRST, sorts LAST alphabetically
    _commit(repo, "alpha-SOW.md")  # born SECOND, sorts FIRST alphabetically
    assert birth_order(repo, ["alpha-SOW.md", "zebra-SOW.md"]) == [
        "zebra-SOW.md",
        "alpha-SOW.md",
    ]


def test_same_commit_files_tie_break_by_NAME_and_that_is_DECLARED(repo):
    """Git records no order WITHIN a commit. The restructure moved 313 files in one commit,
    so this is the common case, not an edge - the tie-break must be stated, not accidental."""
    (repo / "z-SOW.md").write_text("# z\nunique z\n", encoding="utf-8")
    (repo / "a-SOW.md").write_text("# a\nunique a\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "both in ONE commit")
    assert birth_order(repo, ["z-SOW.md", "a-SOW.md"]) == ["a-SOW.md", "z-SOW.md"]


def test_ordering_survives_commits_made_in_the_SAME_SECOND(repo):
    """Commit topology, not the clock: two commits in one wall-clock second still order."""
    _commit(repo, "zzz-SOW.md")
    _commit(repo, "aaa-SOW.md")
    assert birth_order(repo, ["aaa-SOW.md", "zzz-SOW.md"]) == [
        "zzz-SOW.md",
        "aaa-SOW.md",
    ]


def test_a_MOVED_file_keeps_its_TRUE_birth_which_is_why_follow_is_load_bearing(repo):
    """Without --follow a moved file's birth is the MOVE commit. The restructure moved 313
    files in one commit, so dropping --follow would tie all of them and collapse to
    alphabetical - passing a naive test while being wrong on the corpus."""
    _commit(repo, "elder-SOW.md")
    _commit(repo, "younger-SOW.md")
    (repo / "projects").mkdir()
    _git(repo, "mv", "elder-SOW.md", "projects/elder-SOW.md")
    _git(repo, "commit", "-q", "-m", "the restructure: move the ELDER file")
    order = birth_order(repo, ["projects/elder-SOW.md", "younger-SOW.md"])
    assert order == ["projects/elder-SOW.md", "younger-SOW.md"], (
        "the moved file must keep its true birth, not inherit the move commit's position"
    )


def test_IDENTICAL_content_is_a_known_follow_hazard_documented_not_endorsed(repo):
    """GM-DIAG-137: git's rename detection links same-byte files and reports the elder's
    birth for both. Pinned so the next reader meets it as a documented git property rather
    than as an ordering bug - which is exactly how this seat misread it, twice."""
    _commit(repo, "first-SOW.md", body="same bytes\n")
    _commit(repo, "second-SOW.md", body="same bytes\n")
    order = birth_order(repo, ["second-SOW.md", "first-SOW.md"])
    assert order[0] == "first-SOW.md", "documents --follow's behaviour, it does not endorse it"


def test_an_untracked_file_sorts_first_and_is_visible(repo):
    _commit(repo, "tracked-SOW.md")
    (repo / "untracked-SOW.md").write_text("# untracked\nunique\n", encoding="utf-8")
    assert birth_order(repo, ["tracked-SOW.md", "untracked-SOW.md"])[0] == "untracked-SOW.md"


def test_assign_n_is_one_based_in_birth_order(repo):
    _commit(repo, "b-SOW.md")
    _commit(repo, "a-SOW.md")
    order = birth_order(repo, ["a-SOW.md", "b-SOW.md"])
    assert assign_n(order) == {"b-SOW.md": 1, "a-SOW.md": 2}


def test_rev_pairs_get_DISTINCT_n_so_the_collision_dissolves(repo):
    """RULING-093 s4: Rev1/Rev2 are distinct filings under append-don't-revert."""
    _commit(repo, "DOCS-SORT-SOW-02-classification-Rev1.md")
    _commit(repo, "DOCS-SORT-SOW-02-classification-Rev2.md")
    order = birth_order(
        repo,
        [
            "DOCS-SORT-SOW-02-classification-Rev2.md",
            "DOCS-SORT-SOW-02-classification-Rev1.md",
        ],
    )
    n = assign_n(order)
    assert n["DOCS-SORT-SOW-02-classification-Rev1.md"] == 1
    assert n["DOCS-SORT-SOW-02-classification-Rev2.md"] == 2
    targets = {p: canonical_name("docs-sort", n[p], "classification") for p in n}
    assert collisions(targets) == {}, "distinct n must yield distinct names"


def test_a_REAL_collision_is_reported_never_resolved():
    """When two sources DO claim one target, --promote must refuse with both named."""
    assert collisions({"a.md": "x-SOW-1-s.md", "b.md": "x-SOW-1-s.md"}) == {"x-SOW-1-s.md": ["a.md", "b.md"]}


def test_canonical_name_strips_the_rev_suffix():
    assert canonical_name("seam", 9, "brand-engine-seam-Rev9") == "seam-SOW-09-brand-engine-seam.md"
    assert canonical_name("d2", 3, "watcher-rev-b") == "d2-SOW-03-watcher.md"


def test_predecessor_is_SEQUENCE_not_supersession():
    """C's predecessor is B even when C supersedes A - the operator's distinction."""
    assert predecessor_map(["A.md", "B.md", "C.md"]) == {
        "A.md": "none",
        "B.md": "A.md",
        "C.md": "B.md",
    }


def test_genesis_is_explicit_so_first_differs_from_forgot():
    assert predecessor_map(["only.md"])["only.md"] == "none"
