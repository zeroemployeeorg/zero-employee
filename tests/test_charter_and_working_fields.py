"""DS6-CHARTER-03 item 2 (RULING-202): the CHARTER genre was completely ungraded
(_SKIP_GENRES), which made done_when:/restaufwand: not merely unenforced on charters but
UNREACHABLE - measured live on ZEO-RELEASE-CHARTER-01, which lint as '1 skipped
(deliberate)' while carrying neither field. Two halves: grade the genre, then require
the fields on any WORKING-like status, genre-keyed rather than SOW-assumed."""

from zero_employee.core import check_charter, check_working_fields, lint_file, ERROR, WARN


def test_active_charter_needs_a_landing_commit():
    out = check_charter({"charter": "X-01", "status": "ACTIVE"})
    assert any(f.code == "charter-unlanded" and f.severity == ERROR for f in out)


def test_active_charter_with_landing_commit_self_is_clean():
    out = check_charter({"charter": "X-01", "status": "ACTIVE", "landing_commit": "self"})
    assert out == []


def test_superseded_charter_needs_a_superseded_by_pointer():
    out = check_charter({"charter": "X-01", "status": "SUPERSEDED"})
    assert any(f.code == "charter-nosuccessor" for f in out)


def test_charter_status_outside_the_ruling_shaped_enum_is_flagged():
    out = check_charter({"charter": "X-01", "status": "DRAFT"})
    assert any(f.code == "charter-status-enum" for f in out)


# ── check_working_fields ─────────────────────────────────────────────
def test_a_sow_in_PROGRESS_with_neither_field_is_flagged_twice():
    out = check_working_fields({"status": "PROGRESS"}, "sow")
    codes = {f.code for f in out}
    assert codes == {"working-no-done-when", "working-no-restaufwand"}
    assert all(f.severity == WARN for f in out)


def test_a_sow_in_PROGRESS_with_both_fields_is_clean():
    out = check_working_fields({"status": "PROGRESS", "done_when": "make verify -> 0", "restaufwand": 3}, "sow")
    assert out == []


def test_a_RESTING_sow_status_needs_neither_field():
    out = check_working_fields({"status": "SHIPPED"}, "sow")
    assert out == []


def test_a_charter_ACTIVE_with_neither_field_is_flagged():
    out = check_working_fields({"status": "ACTIVE"}, "charter")
    assert {f.code for f in out} == {"working-no-done-when", "working-no-restaufwand"}


def test_a_charter_SUPERSEDED_needs_neither_field_ACTIVE_is_charters_only_working_state():
    out = check_working_fields({"status": "SUPERSEDED"}, "charter")
    assert out == []


def test_a_sow_status_ACTIVE_is_not_working_like_for_the_sow_genre():
    # ACTIVE is charter's working state, never sow's - the sets are genre-keyed, not shared.
    out = check_working_fields({"status": "ACTIVE"}, "sow")
    assert out == []


def test_commit_mode_promotes_missing_fields_to_error():
    out = check_working_fields({"status": "DESIGN"}, "sow", commit_mode=True)
    assert out and all(f.severity == ERROR for f in out)


def test_no_status_at_all_is_silent_a_migration_concern_not_this_checks():
    assert check_working_fields({}, "sow") == []


# ── lint_file dispatch: the charter genre is no longer silently skipped ──
def test_lint_file_grades_a_charter_instead_of_skipping_it(tmp_path):
    f = tmp_path / "CHARTER-01.md"
    f.write_text(
        "---\ngenre: charter\ncharter: X-01\nsow: x\nstatus: ACTIVE\n"
        "landing_commit: self\nschema_rev: 17\n---\n\nbody\n",
        encoding="utf-8",
    )
    status, findings = lint_file(str(f))
    # missing fields are WARN outside commit_mode (gate-the-future idiom) - PASS, not SKIP,
    # which is the whole point: the genre is now GRADED, where it was invisible before.
    assert status == "PASS"
    codes = {fi.code for fi in findings}
    assert "working-no-done-when" in codes and "working-no-restaufwand" in codes


def test_lint_file_FAILS_a_charter_missing_fields_at_the_commit_path(tmp_path):
    f = tmp_path / "CHARTER-01.md"
    f.write_text(
        "---\ngenre: charter\ncharter: X-01\nsow: x\nstatus: ACTIVE\n"
        "landing_commit: self\nschema_rev: 17\n---\n\nbody\n",
        encoding="utf-8",
    )
    status, findings = lint_file(str(f), commit_mode=True)
    assert status == "FAIL"


def test_lint_file_passes_a_fully_conformant_charter(tmp_path):
    f = tmp_path / "CHARTER-01.md"
    f.write_text(
        "---\ngenre: charter\ncharter: X-01\nsow: x\nstatus: ACTIVE\n"
        "landing_commit: self\nschema_rev: 17\n"
        'done_when: "make verify -> 0 failures"\nrestaufwand: 2\n---\n\nbody\n',
        encoding="utf-8",
    )
    status, findings = lint_file(str(f))
    assert status == "PASS"
    assert findings == []
