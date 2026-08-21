"""check_resolved_by must find a ruling wherever the corpus keeps them (GM-DS6-203).

It globbed root/"ducktyper"/"ruling" - hardcoded and PRE-RESTRUCTURE. Proven before the fix:
`ruling: 046` returned "no such ruling on disk" while projects/ducktyper/ruling EXISTED and
ducktyper/ruling did not. So every resolved_by closed NOTHING while looking like a fail-closed
verdict - the worst shape a gate can take. Org-scope rulings at root ruling/ were never
findable at all, even before the move.

RULING-214 s6 item 1: the `superseded-by` kind had the SAME hardcoded-`ducktyper` bug,
unfixed when the `ruling` kind above it was. Proven before the fix: docs-sort/SOW-46's
`resolved_by: "superseded-by: SOW-49"` returned "no such SOW in stream" while
projects/governance-layer/sow/docs-sort/DOCS-SORT-SOW-49-v1-shipped.md existed on disk.
Also: a lexically-relative root (`Path(".")`, what `zeo --triage .` passes) broke the
`commit:` kind's `root.parent / <repo>` sibling-repo lookup, because `Path(".").parent`
is `"."` again, not the real parent directory - fixed by resolving root once at entry.
"""

import subprocess
from zero_employee.core import check_resolved_by


def _mk(root, rel):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\nruling: '046'\n---\nbody\n", encoding="utf-8")
    return p


def test_a_PROJECT_scoped_ruling_resolves(tmp_path):
    _mk(tmp_path, "projects/ducktyper/ruling/RULING-046-sequencing.md")
    kind, target, ok, _ = check_resolved_by({"resolved_by": "ruling: 046"}, tmp_path)
    assert (kind, ok) == ("ruling", True)


def test_an_ORG_scoped_ruling_at_root_resolves(tmp_path):
    _mk(tmp_path, "ruling/RULING-099-layout-resync.md")
    _, _, ok, _ = check_resolved_by({"resolved_by": "ruling: 099"}, tmp_path)
    assert ok is True


def test_the_LEGACY_flat_layout_still_resolves(tmp_path):
    _mk(tmp_path, "ducktyper/ruling/RULING-046-x.md")
    _, _, ok, _ = check_resolved_by({"resolved_by": "ruling: 046"}, tmp_path)
    assert ok is True


def test_the_RULING_prefixed_form_resolves(tmp_path):
    _mk(tmp_path, "projects/quackverse/ruling/RULING-025-banner.md")
    _, _, ok, _ = check_resolved_by({"resolved_by": "ruling: RULING-025"}, tmp_path)
    assert ok is True


def test_a_GENUINELY_absent_ruling_still_FAILS_closed(tmp_path):
    _mk(tmp_path, "ruling/RULING-001-x.md")
    _, _, ok, detail = check_resolved_by({"resolved_by": "ruling: 999"}, tmp_path)
    assert ok is False and "no such ruling" in detail


def test_a_REAL_ruling_with_trailing_prose_still_resolves_and_says_so(tmp_path):
    """worldprops-SOW-24, 2026-08-17: `ruling: RULING-272 (backfilled ...)` globbed for a
    literal file named "RULING-272 (backfilled..." and reported "no such ruling on disk"
    for a ruling that WAS on disk — a false detail message, not just a missed match."""
    _mk(tmp_path, "projects/ducktyper/ruling/RULING-272-skyline-float.md")
    _, _, ok, detail = check_resolved_by(
        {"resolved_by": "ruling: RULING-272 (backfilled 2026-08-17 by Master)"}, tmp_path
    )
    assert ok is True
    assert "no such ruling" not in detail
    assert "trailing text after the number ignored" in detail


def test_a_ruling_target_with_no_leading_number_FAILS_closed_with_a_distinct_reason(tmp_path):
    _mk(tmp_path, "ruling/RULING-001-x.md")
    _, _, ok, detail = check_resolved_by({"resolved_by": "ruling: see the discussion"}, tmp_path)
    assert ok is False and "no leading number" in detail


def _mk_sparring(root, rel, stem):
    p = root / rel / f"{stem}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\nruling: 'x'\n---\nbody\n", encoding="utf-8")
    return p


def test_a_SPARRING_RULING_slug_dated_target_resolves(tmp_path):
    """SPARRING-RULING-CITATION-TRACE SOW-1 §4: SPARRING-RULING-<SLUG>-<DATE> has no
    leading digit at all, so the numeric regex never matched it — a real, on-disk
    Sparring ruling reported ok=False, "no leading number" for all such targets."""
    stem = "SPARRING-RULING-CAST-ART-PIPELINE-2026-08-20"
    _mk_sparring(tmp_path, "projects/ducktyper/ruling", stem)
    kind, target, ok, detail = check_resolved_by({"resolved_by": f"ruling: {stem}"}, tmp_path)
    assert (kind, ok) == ("ruling", True), detail
    assert "no leading number" not in detail


def test_a_SPARRING_RULING_target_at_ORG_scope_root_resolves(tmp_path):
    stem = "SPARRING-RULING-Voice-Casting-Round"
    _mk_sparring(tmp_path, "ruling", stem)
    _, _, ok, _ = check_resolved_by({"resolved_by": f"ruling: {stem}"}, tmp_path)
    assert ok is True


def test_a_SPARRING_RULING_target_with_trailing_prose_still_resolves_and_says_so(tmp_path):
    """profrod-logo-normalize's real citation on disk: 'SPARRING-RULING-PROFROD-LOGO-
    2026-08-20 (including its own s8 amendment, landed same day)' — the stem is the
    whole slug+date, so trailing prose must be split off the same way the numeric
    branch already does, keeping the two failure/success details distinguishable."""
    stem = "SPARRING-RULING-PROFROD-LOGO-2026-08-20"
    _mk_sparring(tmp_path, "projects/ducktyper/ruling", stem)
    _, _, ok, detail = check_resolved_by(
        {"resolved_by": f"ruling: {stem} (including its own s8 amendment, landed same day)"},
        tmp_path,
    )
    assert ok is True
    assert "no such ruling" not in detail
    assert "trailing text after the stem ignored" in detail


def test_a_GENUINELY_absent_SPARRING_RULING_target_still_FAILS_closed(tmp_path):
    _mk(tmp_path, "ruling/RULING-001-x.md")
    _, _, ok, detail = check_resolved_by({"resolved_by": "ruling: SPARRING-RULING-DOES-NOT-EXIST-2026-01-01"}, tmp_path)
    assert ok is False
    assert "no such ruling on disk" in detail
    assert "no leading number" not in detail  # distinguishable from the unrecognized-shape failure


def test_numeric_ruling_targets_are_unaffected_by_the_SPARRING_branch(tmp_path):
    _mk(tmp_path, "projects/ducktyper/ruling/RULING-046-sequencing.md")
    kind, target, ok, _ = check_resolved_by({"resolved_by": "ruling: 046"}, tmp_path)
    assert (kind, ok) == ("ruling", True)


def test_no_resolved_by_returns_all_None(tmp_path):
    assert check_resolved_by({}, tmp_path) == (None, None, None, None)


def _mk_sow(root, rel):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\nsow: docs-sort\n---\nbody\n", encoding="utf-8")
    return p


def test_a_PROJECT_scoped_superseded_by_resolves(tmp_path):
    _mk_sow(
        tmp_path,
        "projects/governance-layer/sow/docs-sort/DOCS-SORT-SOW-49-v1-shipped.md",
    )
    kind, target, ok, detail = check_resolved_by({"sow": "docs-sort", "resolved_by": "superseded-by: SOW-49"}, tmp_path)
    assert (kind, ok) == ("superseded-by", True), detail


def test_the_LEGACY_flat_superseded_by_still_resolves(tmp_path):
    _mk_sow(tmp_path, "docs-sort/sow/docs-sort/DOCS-SORT-SOW-49-v1-shipped.md")
    _, _, ok, _ = check_resolved_by({"sow": "docs-sort", "resolved_by": "superseded-by: SOW-49"}, tmp_path)
    assert ok is True


def test_a_GENUINELY_absent_superseded_by_target_still_FAILS_closed(tmp_path):
    _mk_sow(tmp_path, "projects/governance-layer/sow/docs-sort/DOCS-SORT-SOW-1-x.md")
    _, _, ok, detail = check_resolved_by({"sow": "docs-sort", "resolved_by": "superseded-by: SOW-99"}, tmp_path)
    assert ok is False and "no such SOW in stream" in detail


def test_commit_kind_resolves_with_a_RELATIVE_root(tmp_path, monkeypatch):
    # Path(".").parent == "." — the sibling-repo lookup silently missed every commit
    # unless root is resolved to absolute first. Reproduce the exact shape:
    # <tmp_path>/org (the sow_repo, cwd) beside <tmp_path>/sibling-repo (the work_repo).
    org = tmp_path / "org"
    org.mkdir()
    sibling = tmp_path / "sibling-repo"
    sibling.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=sibling, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@t.co",
            "-c",
            "user.name=t",
            "commit",
            "--allow-empty",
            "-q",
            "-m",
            "x",
        ],
        cwd=sibling,
        check=True,
    )
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=sibling,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.chdir(org)
    import pathlib

    kind, target, ok, detail = check_resolved_by({"resolved_by": f"commit: sibling-repo@{sha}"}, pathlib.Path("."))
    assert ok is True, detail
