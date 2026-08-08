"""V1-B acceptance — B1 project: checksum, era-aware (mirrors N-series discipline).
Fixtures use real path shapes; canonical vs flat-legacy vs disagreement."""

from zero_employee.core import check_project, lint_file, ERROR, WARN

ROOT = "/Users/riverar/repos/profrodai/sovereignagents/sovereignagents-sows"


def sev(findings, code):
    return next((f.severity for f in findings if f.code == code), None)


def test_B1_canonical_agrees_ok():
    assert (
        check_project(
            f"{ROOT}/sovereignagents/sow/docs-sort/x.md",
            {"project": "sovereignagents"},
            root=ROOT,
        )
        == []
    )


def test_B2_canonical_disagrees_errors():
    out = check_project(
        f"{ROOT}/sovereignagents/sow/docs-sort/x.md",
        {"project": "quackverse"},
        root=ROOT,
    )
    assert sev(out, "project-mismatch") == ERROR


def test_B3_canonical_missing_project_errors():
    out = check_project(f"{ROOT}/sovereignagents/sow/docs-sort/x.md", {}, root=ROOT)
    assert sev(out, "project-missing") == ERROR


def test_B4_flat_legacy_missing_warns_not_errors():
    out = check_project(f"{ROOT}/sow/docs-sort/x.md", {}, root=ROOT)
    assert sev(out, "project-backfill") == WARN
    assert all(f.severity != ERROR for f in out)


def test_B5_flat_legacy_early_backfilled_ok():
    assert check_project(f"{ROOT}/sow/docs-sort/x.md", {"project": "sovereignagents"}, root=ROOT) == []


def test_B6_flat_legacy_spaced_task_warns():
    out = check_project(f"{ROOT}/sow/directional facing/z.md", {}, root=ROOT)
    assert sev(out, "project-backfill") == WARN


def test_B7_wired_into_lint_file_canonical_mismatch_fails(tmp_path):
    # integration: a canonical-shape file with wrong project: FAILs through lint_file
    proj = tmp_path / "sovereignagents" / "sow" / "docs-sort"
    proj.mkdir(parents=True)
    p = proj / "DOCS-SORT-SOW-50-x.md"
    p.write_text("---\nsow: docs-sort\nn: 50\nschema_rev: 12\nproject: quackverse\n---\nbody")
    status, findings = lint_file(p, current_rev=12, root=tmp_path)
    assert status == "FAIL"
    assert any(f.code == "project-mismatch" for f in findings)
