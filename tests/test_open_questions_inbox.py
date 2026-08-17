"""RULING-268 s1 / charter Phase 1 item 3: --inbox <stream> reports PARTIAL (n/m) for a
file with a mix of OPEN/RESOLVED open_questions: rows, not just OPEN or RESOLVED.

The load-bearing regression half of this charter item lives in
test_open_questions_byte_identical.py: a file with ZERO open_questions: rows must be
byte-identical in every existing check's output before and after this field exists.
"""

from zero_employee import cli
from zero_employee.core import extract_frontmatter, open_questions_summary


def _fm(s):
    return extract_frontmatter(s)


ALL_OPEN = """---
sow: t
open_questions:
  - id: q1
    claim: a
    status: OPEN
  - id: q2
    claim: b
    status: OPEN
---
body
"""

ALL_RESOLVED = """---
sow: t
open_questions:
  - id: q1
    claim: a
    status: RESOLVED
    resolved_by: "ruling: RULING-1"
  - id: q2
    claim: b
    status: RESOLVED
    resolved_by: "ruling: RULING-1"
---
body
"""

MIXED = """---
sow: t
open_questions:
  - id: q1
    claim: a
    status: RESOLVED
    resolved_by: "ruling: RULING-1"
  - id: q2
    claim: b
    status: OPEN
  - id: q3
    claim: c
    status: OPEN
---
body
"""

NO_FIELD = """---
sow: t
status: SHIPPED
---
body
"""

EMPTY_LIST = """---
sow: t
open_questions: []
---
body
"""


def test_all_open_tag():
    s = open_questions_summary(_fm(ALL_OPEN))
    assert s == {"tag": "OPEN", "resolved": 0, "total": 2}


def test_all_resolved_tag():
    s = open_questions_summary(_fm(ALL_RESOLVED))
    assert s == {"tag": "RESOLVED", "resolved": 2, "total": 2}


def test_mixed_is_partial_with_correct_fraction():
    s = open_questions_summary(_fm(MIXED))
    assert s == {"tag": "PARTIAL", "resolved": 1, "total": 3}


def test_absent_field_returns_none():
    assert open_questions_summary(_fm(NO_FIELD)) is None


def test_empty_list_returns_none():
    assert open_questions_summary(_fm(EMPTY_LIST)) is None


def _sows_repo(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("Rev 17\n", encoding="utf-8")
    return tmp_path


def test_inbox_cli_prints_partial_fraction_for_mixed_file(tmp_path, capsys):
    """End-to-end through the real `zeo --inbox <stream>` CLI path, RULING-268's own
    worked example shape: SOW-25 with three questions, one ruling landing two answers,
    the third still open — the exact acceptance fixture the charter names."""
    root = _sows_repo(tmp_path)
    d = root / "p" / "sow" / "archive-arch"
    d.mkdir(parents=True)
    (d / "archive-arch-SOW-25-x.md").write_text(
        "---\nsow: archive-arch\nn: 25\nstatus: PROGRESS\nupdated: 2026-08-01\n"
        "done_when: x\nrestaufwand: 1\nopen_questions:\n"
        "  - id: q1-seat\n    claim: a\n    status: RESOLVED\n    resolved_by: 'ruling: RULING-210'\n"
        "  - id: q2-acceptance-test\n    claim: b\n    status: RESOLVED\n    resolved_by: 'ruling: RULING-210'\n"
        "  - id: q3-queue-block\n    claim: c\n    status: OPEN\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )
    rc = cli.main(["--inbox", "archive-arch", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "PARTIAL (2/3)" in out, out
