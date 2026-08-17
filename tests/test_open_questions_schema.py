"""RULING-268 s1 / charter Phase 1 item 1: open_questions: shape validation.

`open_questions:` is a ledger-shaped, per-question closure field: a list of
{id, claim, status, resolved_by} rows. status is OPEN or RESOLVED only — no third
state, no free text. Malformed shape (missing id, unknown status, duplicate id) is a
lint FAIL, not a silent skip (the ruling is exact about the shape).
"""

from zero_employee.core import extract_frontmatter
from zero_employee.schemas import grade_sow, open_questions_messages


def _fm(s):
    return extract_frontmatter(s)


GOOD = """---
sow: archive-arch
status: RULING-REQUESTED
open_questions:
  - id: q1-seat
    claim: "which seat owns the RULING-098 collision"
    status: OPEN
    resolved_by: null
  - id: q2-acceptance-test
    claim: "what acceptance test proves the migration complete"
    status: RESOLVED
    resolved_by: "ruling: RULING-210"
---
body
"""

NO_FIELD = """---
sow: archive-arch
status: SHIPPED
---
body
"""

MISSING_ID = """---
sow: t
open_questions:
  - claim: "no id on this row"
    status: OPEN
---
body
"""

BAD_STATUS = """---
sow: t
open_questions:
  - id: q1
    claim: "third state invented"
    status: PENDING
---
body
"""

FREE_TEXT_STATUS = """---
sow: t
open_questions:
  - id: q1
    claim: "free text instead of the enum"
    status: "waiting on Master, see chat"
---
body
"""

DUPLICATE_ID = """---
sow: t
open_questions:
  - id: q1-seat
    claim: "first"
    status: OPEN
  - id: q1-seat
    claim: "second, same id"
    status: OPEN
---
body
"""

NOT_A_LIST = """---
sow: t
open_questions: "not a list"
---
body
"""

ROW_NOT_A_MAPPING = """---
sow: t
open_questions:
  - "just a string, not a mapping"
---
body
"""


def test_good_shape_passes_silently():
    assert open_questions_messages(_fm(GOOD)) == []


def test_absent_field_is_legal_and_silent():
    # additive (RULING-268 s2 no-backfill): a file with no open_questions: at all must
    # produce ZERO messages from this function, matching every file in the existing
    # ~1000+ file corpus.
    assert open_questions_messages(_fm(NO_FIELD)) == []


def test_missing_id_is_a_fail():
    findings = open_questions_messages(_fm(MISSING_ID))
    assert any("no id" in f for f in findings)


def test_unknown_status_value_is_a_fail():
    findings = open_questions_messages(_fm(BAD_STATUS))
    assert any("PENDING" in f and "OPEN or RESOLVED" in f for f in findings)


def test_free_text_status_is_a_fail_no_third_state():
    findings = open_questions_messages(_fm(FREE_TEXT_STATUS))
    assert any("OPEN or RESOLVED" in f for f in findings)


def test_duplicate_id_within_one_file_is_a_fail():
    findings = open_questions_messages(_fm(DUPLICATE_ID))
    assert any("duplicates" in f for f in findings)


def test_non_list_shape_is_a_fail():
    findings = open_questions_messages(_fm(NOT_A_LIST))
    assert any("not a list" in f for f in findings)


def test_row_not_a_mapping_is_a_fail():
    findings = open_questions_messages(_fm(ROW_NOT_A_MAPPING))
    assert any("not a mapping" in f for f in findings)


def test_grade_sow_surfaces_open_questions_shape_as_error():
    # end-to-end through the real dispatch point (grade_sow), not just the helper —
    # this is what lint_file actually calls.
    findings = grade_sow(_fm(MISSING_ID))
    assert any(f.code == "open-questions-shape" and f.severity == "ERROR" for f in findings)


def test_grade_sow_good_shape_has_no_open_questions_findings():
    findings = grade_sow(_fm(GOOD))
    assert not any(f.code == "open-questions-shape" for f in findings)
