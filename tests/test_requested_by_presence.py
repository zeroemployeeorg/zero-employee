"""RULING-325: `requested_by:` is required by `zeo doctor`'s write-side model
(`SowWriteFrontmatter`, no default) but was never enforced on the read/lint side —
`check_requested_by` (tests: test_requested_by.py) grades the FORM of the field when
present and is silent when it is simply absent. `check_requested_by_presence` is the
new, separate check that closes that gap: era-aware (a pre-schema file gets no opinion),
WARN off the commit path, FAIL on it — matching `working-no-done-when`'s own severity
idiom and `doctor`'s long-standing requirement.

Also covers the regression check RULING-325 §7 explicitly asks for: re-running
`--commit-check`-equivalent lint (commit_mode=True) against real files from the ruling's
own ten-file list should FAIL them (they are schema-era, requested_by simply absent).
"""

from __future__ import annotations

from zero_employee.core import (
    ERROR,
    WARN,
    check_requested_by_presence,
    extract_frontmatter,
    lint_file,
)


def fm(s):
    return extract_frontmatter(s)


def sev(findings, code):
    return next((f.severity for f in findings if f.code == code), None)


SCHEMA_ERA_NO_RB = fm("---\nsow: worldprops\nn: 4\nschema_rev: 17\nstatus: DRAFT\n---\nx")
SCHEMA_ERA_WITH_RB = fm(
    "---\nsow: worldprops\nn: 4\nschema_rev: 17\nstatus: DRAFT\nrequested_by: other-stream#2\n---\nx"
)
PRE_SCHEMA_NO_RB = fm("---\nsow: docs-sort\nstatus: DONE\n---\nx")  # no n:, no schema_rev at all


def test_schema_era_file_missing_requested_by_warns_off_commit_path():
    out = check_requested_by_presence(SCHEMA_ERA_NO_RB, commit_mode=False)
    assert sev(out, "requested_by-missing") == WARN


def test_schema_era_file_missing_requested_by_fails_on_commit_path():
    out = check_requested_by_presence(SCHEMA_ERA_NO_RB, commit_mode=True)
    assert sev(out, "requested_by-missing") == ERROR


def test_pre_schema_file_no_n_no_schema_rev_is_silent_even_under_commit_mode():
    # A genuinely legacy file (no n:, no schema_rev: at all) predates the field's own
    # schema — same gate check_schema_rev's own "schema-missing" uses (n: is not None).
    out = check_requested_by_presence(PRE_SCHEMA_NO_RB, commit_mode=True)
    assert out == []


def test_present_requested_by_is_silent_regardless_of_form():
    # Form-grading is check_requested_by's job (test_requested_by.py), not this one's —
    # this check only asks "is the field there at all".
    assert check_requested_by_presence(SCHEMA_ERA_WITH_RB, commit_mode=True) == []


def test_present_but_whitespace_only_requested_by_is_treated_as_absent():
    fm_ws = fm('---\nsow: worldprops\nn: 4\nschema_rev: 17\nrequested_by: "   "\n---\nx')
    out = check_requested_by_presence(fm_ws, commit_mode=True)
    assert sev(out, "requested_by-missing") == ERROR


def test_n_present_without_schema_rev_still_counts_as_schema_era():
    # check_schema_rev's own "schema-missing" fires whenever n: is not None, even if
    # schema_rev: itself is absent — this check mirrors that exact era boundary.
    fm_n_only = {"sow": "x", "n": 4}
    out = check_requested_by_presence(fm_n_only, commit_mode=True)
    assert sev(out, "requested_by-missing") == ERROR


def test_lint_file_wires_the_check_in_and_fails_under_commit_mode(tmp_path):
    (tmp_path / "claude-md").mkdir(parents=True)
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("Rev 17\n")
    d = tmp_path / "zero-employee" / "sow" / "worldprops"
    d.mkdir(parents=True)
    f = d / "WORLDPROPS-SOW-04-x.md"
    f.write_text(
        "---\nsow: worldprops\nn: 4\nschema_rev: 17\nproject: zero-employee\n"
        "status: DRAFT\nlifecycle: DESIGN-MEMO\ngenre: sow\ncreated: 2026-08-20\n"
        "updated: 2026-08-20\nsow_repo: x/org\nwork_repo: x/zero-employee\n"
        "supersedes: RULING-100-some-governing-ruling.md\n"
        "---\nbody\n"
    )
    status, findings = lint_file(f, root=tmp_path, commit_mode=False)
    codes = {fi.code for fi in findings}
    assert "requested_by-missing" in codes
    assert sev(findings, "requested_by-missing") == WARN
    assert status != "FAIL", "off the commit path this must WARN, not FAIL"

    status2, findings2 = lint_file(f, root=tmp_path, commit_mode=True)
    assert sev(findings2, "requested_by-missing") == ERROR
    assert status2 == "FAIL", "on the commit path a schema-era file missing requested_by: must FAIL"


def test_lint_file_stays_green_when_requested_by_is_present(tmp_path):
    (tmp_path / "claude-md").mkdir(parents=True)
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("Rev 17\n")
    d = tmp_path / "zero-employee" / "sow" / "worldprops"
    d.mkdir(parents=True)
    f = d / "WORLDPROPS-SOW-04-x.md"
    f.write_text(
        "---\nsow: worldprops\nn: 4\nschema_rev: 17\nproject: zero-employee\n"
        "status: DRAFT\nlifecycle: DESIGN-MEMO\ngenre: sow\ncreated: 2026-08-20\n"
        "updated: 2026-08-20\nsow_repo: x/org\nwork_repo: x/zero-employee\n"
        "requested_by: other-stream#2\n"
        "---\nbody\n"
    )
    _status, findings = lint_file(f, root=tmp_path, commit_mode=True)
    assert "requested_by-missing" not in {fi.code for fi in findings}
