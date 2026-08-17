"""Charter Phase 1 item 3 / DoD's load-bearing regression test: a file with NO
open_questions: field is byte-identical in every existing check's output before and
after this feature. This is not a nice-to-have — it is what makes the field additive
rather than a corpus-wide behavior change (RULING-268 s2's no-backfill rule depends on
existing files being completely unaffected).

Method: run the real grading/inbox paths against ordinary SOW fixtures that carry no
open_questions: anywhere, and assert the outputs match the exact strings the existing
suite (test_keystone.py, test_triage.py, test_ruling_receipts.py) already asserts on —
i.e. this is a same-corpus rerun, not a new baseline invented for this test.
"""

from zero_employee import cli
from zero_employee.core import check_keystone, check_resolves, extract_frontmatter, lint_file, open_questions_summary
from zero_employee.schemas import grade_sow


def _fm(s):
    return extract_frontmatter(s)


# Verbatim copy of test_keystone.py's GOOD fixture — no open_questions: field anywhere.
GOOD = """---
sow: docs-sort
status: SHIPPED
ledger:
  - claim: a
    state: SHIPPED
    commit: repo@abc1234
    check: "wc -l file → 686"
---
body
"""


def test_keystone_output_unchanged_for_a_file_without_open_questions():
    # identical to test_keystone.py::test_good_passes — same fixture, same assertion.
    assert check_keystone(_fm(GOOD)) == []


def test_grade_sow_produces_no_open_questions_findings_when_field_absent():
    findings = grade_sow(_fm(GOOD))
    assert not any(f.code == "open-questions-shape" for f in findings)


def test_lint_file_status_unchanged_for_ordinary_sow(tmp_path):
    p = tmp_path / "docs-sort-SOW-1-x.md"
    p.write_text(GOOD, encoding="utf-8")
    status, findings = lint_file(p)
    assert status == "PASS"
    assert not any(f.code == "open-questions-shape" for f in findings)


def test_open_questions_summary_is_none_for_every_field_shape_that_omits_it():
    assert open_questions_summary(_fm(GOOD)) is None
    # a bare empty ledger sibling field, still no open_questions: anywhere
    no_ledger = "---\nsow: t\nstatus: DRAFT\ndone_when: x\nrestaufwand: 1\n---\nbody\n"
    assert open_questions_summary(_fm(no_ledger)) is None


def test_check_resolves_is_silent_when_no_file_carries_resolves_or_open_questions(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("Rev 17\n", encoding="utf-8")
    d = tmp_path / "p" / "sow" / "docs-sort"
    d.mkdir(parents=True)
    f = d / "docs-sort-SOW-1-x.md"
    f.write_text(GOOD, encoding="utf-8")
    files_fm = [(str(f), _fm(GOOD))]
    assert check_resolves(files_fm, tmp_path) == {}


def test_inbox_open_questions_section_prints_none_for_a_stream_with_no_field(tmp_path, capsys):
    """The literal charter wording: 'A file with zero open_questions: rows behaves
    exactly as it does today.' Reproduces test_triage.py's resolved_by-precedence
    fixture verbatim (a real pre-existing corpus shape) and asserts the NEW section
    this stream added prints '(none)' while every pre-existing line is untouched."""
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("Rev 17\n", encoding="utf-8")
    d = tmp_path / "ducktyper" / "sow" / "s1"
    d.mkdir(parents=True)
    (d / "s1-SOW-01-x.md").write_text(
        "---\nsow: s1\nn: 1\nschema_rev: 16\nstatus: RULING-REQUESTED\n"
        'resolved_by: "ruling: RULING-001"\n'
        "project: ducktyper\ncreated: 2026-07-01\nupdated: 2026-07-01\n---\n\nb\n",
        encoding="utf-8",
    )
    rulings = tmp_path / "ducktyper" / "ruling"
    rulings.mkdir(parents=True)
    (rulings / "RULING-001-x.md").write_text(
        "---\nruling: 001\nstatus: ACTIVE\nlanding_commit: self\n"
        "requested_by: ducktyper/sow/s1/s1-SOW-01-x.md\n---\n\nb\n",
        encoding="utf-8",
    )
    rc = cli.main(["--inbox", "s1", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    # every pre-existing assertion from test_triage.py's
    # test_inbox_a_valid_resolved_by_promotes_past_answered_by_ruling, verbatim:
    assert "0 truly open · 0 answered-by-ruling · 1 resolved · 0 by-supersession" in out
    assert "ANSWERED-BY-RULING (cite it in your next SOW to close the loop):\n  (none)" in out
    assert "RESOLVED (closed by implementation/doctrine, verified resolver — not awaiting anything):\n  SOW-1" in out
    # plus the new section, silent as documented:
    assert "OPEN QUESTIONS (per-file open_questions: rollup — RULING-268):\n  (none)" in out
