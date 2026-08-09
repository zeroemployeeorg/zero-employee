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
