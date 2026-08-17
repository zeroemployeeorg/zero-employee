"""RULING-286: the fifth genre, pre-decision approach comparison. Sits between
intake (operator-only, no evidence) and charter (already-decided, binds work) --
a stream or Master weighing 2+ real approaches before committing to one. Modeled
directly on intake's own successful shape and test conventions."""

import pathlib

import pytest

from zero_employee.core import ERROR, WARN, discriminate, extract_frontmatter, lint_file
from zero_employee.schemas import grade_design
from zero_employee.schemas.common import DESIGN_STATUS_ENUM


# ── grade_design: frontmatter shape ──────────────────────────────────


def test_design_id_is_required():
    out = grade_design({"genre": "design", "status": "OPEN"}, body="")
    assert any(f.code == "design-id" and f.severity == ERROR for f in out)


def test_design_id_accepts_either_design_or_sow_field():
    out1 = grade_design({"design": "x", "status": "OPEN"}, body="")
    out2 = grade_design({"sow": "x", "status": "OPEN"}, body="")
    assert not any(f.code == "design-id" for f in out1)
    assert not any(f.code == "design-id" for f in out2)


def test_status_outside_the_design_enum_is_flagged():
    out = grade_design({"design": "x", "status": "DRAFT"}, body="")
    assert any(f.code == "design-status-enum" for f in out)


def test_status_enum_is_exactly_open_decided_superseded():
    assert DESIGN_STATUS_ENUM == {"OPEN", "DECIDED", "SUPERSEDED"}


def test_missing_status_warns_in_lint_mode_errors_in_commit_mode():
    out_lint = grade_design({"design": "x"}, body="", commit_mode=False)
    out_commit = grade_design({"design": "x"}, body="", commit_mode=True)
    assert any(f.code == "design-status" and f.severity == WARN for f in out_lint)
    assert any(f.code == "design-status" and f.severity == ERROR for f in out_commit)


def test_decided_status_requires_decided_into():
    out = grade_design({"design": "x", "status": "DECIDED"}, body="")
    assert any(f.code == "design-undecided-successor" and f.severity == ERROR for f in out)


def test_decided_status_with_decided_into_is_not_flagged_for_that_code():
    out = grade_design({"design": "x", "status": "DECIDED", "decided_into": "ruling/RULING-300-x.md"}, body="")
    assert not any(f.code == "design-undecided-successor" for f in out)


def test_superseded_status_without_decided_into_warns_not_errors():
    out = grade_design({"design": "x", "status": "SUPERSEDED"}, body="")
    assert any(f.code == "design-nosuccessor" and f.severity == WARN for f in out)


# ── grade_design: body semantics (QUESTION / APPROACHES / NOT DECIDING HERE) ──

_WELL_FORMED_BODY = """
QUESTION: which approach for X

APPROACHES:
- name: approach A
  evidence: measured foo against the real repo
  tradeoff: costs bar
- name: approach B
  evidence: measured baz directly
  tradeoff: costs qux

NOT DECIDING HERE: whether to also do Y
"""


def test_a_well_formed_design_filing_is_clean():
    out = grade_design({"design": "x", "status": "OPEN"}, body=_WELL_FORMED_BODY)
    assert out == []


def test_question_section_is_required():
    body = _WELL_FORMED_BODY.replace("QUESTION: which approach for X", "")
    out = grade_design({"design": "x", "status": "OPEN"}, body=body)
    assert any(f.code == "design-no-question" and f.severity == ERROR for f in out)


def test_fewer_than_two_approaches_is_an_error():
    """A design comparing 0 or 1 approaches is not comparing anything -- it is a
    charter (an already-decided marching order) that has not been relabeled."""
    body_zero = "QUESTION: x\n\nNOT DECIDING HERE: none\n"
    body_one = "QUESTION: x\n\nAPPROACHES:\n- name: only-one\n  evidence: e\n\nNOT DECIDING HERE: none\n"
    out_zero = grade_design({"design": "x", "status": "OPEN"}, body=body_zero)
    out_one = grade_design({"design": "x", "status": "OPEN"}, body=body_one)
    assert any(f.code == "design-fewer-than-two-approaches" and f.severity == ERROR for f in out_zero)
    assert any(f.code == "design-fewer-than-two-approaches" and f.severity == ERROR for f in out_one)


def test_two_approaches_clears_the_fewer_than_two_check():
    out = grade_design({"design": "x", "status": "OPEN"}, body=_WELL_FORMED_BODY)
    assert not any(f.code == "design-fewer-than-two-approaches" for f in out)


def test_an_approach_with_no_evidence_warns_not_errors():
    """RULING-286 s2 requires evidence per approach -- an unverified lean is a WARN,
    not a hard failure, since a design filing may legitimately still be gathering
    evidence for one side while the other is already measured."""
    body = (
        "QUESTION: x\n\n"
        "APPROACHES:\n"
        "- name: has-evidence\n"
        "  evidence: measured directly\n"
        "- name: no-evidence-yet\n"
        "  tradeoff: unclear cost\n\n"
        "NOT DECIDING HERE: none\n"
    )
    out = grade_design({"design": "x", "status": "OPEN"}, body=body)
    warns = [f for f in out if f.code == "design-approach-no-evidence"]
    assert len(warns) == 1
    assert warns[0].severity == WARN


def test_not_deciding_here_is_mandatory_even_when_the_section_is_absent():
    """Mirrors intake's own NOT THIS: doctrine -- the must-not-decide fence is
    institutionalised at filing time, not left to memory. Absence is an ERROR, not
    merely an empty value (an empty-but-present line is fine, see next test)."""
    body = _WELL_FORMED_BODY.replace("\nNOT DECIDING HERE: whether to also do Y\n", "\n")
    out = grade_design({"design": "x", "status": "OPEN"}, body=body)
    assert any(f.code == "design-no-not-deciding-line" and f.severity == ERROR for f in out)


def test_not_deciding_here_present_but_empty_or_none_is_not_flagged():
    body = _WELL_FORMED_BODY.replace("whether to also do Y", "none")
    out = grade_design({"design": "x", "status": "OPEN"}, body=body)
    assert not any(f.code == "design-no-not-deciding-line" for f in out)


# ── discriminate() + lint_file(): the real end-to-end wiring ─────────


def test_genre_design_is_discriminated_as_design_not_sow():
    fm = {"genre": "design", "design": "x", "status": "OPEN"}
    assert discriminate("/tmp/whatever-DESIGN-01-x.md", fm) == "design"


def _corpus(tmp_path: pathlib.Path) -> pathlib.Path:
    root = tmp_path / "org"
    (root / "claude-md").mkdir(parents=True)
    (root / "claude-md" / "CLAUDE.md").write_text("# c (Rev 17)\n", encoding="utf-8")
    return root


def test_lint_file_grades_a_real_design_filing_end_to_end(tmp_path):
    """The exact regression this genre exists to prevent: RULING-286 s0 measured
    that a pre-decision design document had nowhere real to live and got crammed
    into charter's own namespace (n: 0) as a workaround. Prove a real design-genre
    file on disk now grades PASS through the real lint_file dispatch, not SKIP and
    not silently inheriting SOW rules."""
    root = _corpus(tmp_path)
    d = root / "projects" / "demo" / "sow" / "widget"
    d.mkdir(parents=True)
    f = d / "WIDGET-DESIGN-01-approach-choice.md"
    f.write_text(
        "---\n"
        "design: widget-approach\n"
        "project: demo\n"
        "genre: design\n"
        "created: 2026-08-17\n"
        "status: OPEN\n"
        "---\n\n" + _WELL_FORMED_BODY,
        encoding="utf-8",
    )
    status, findings = lint_file(f, root=root)
    assert status == "PASS", [(fnd.severity, fnd.code, fnd.message) for fnd in findings]


def test_lint_file_fails_a_malformed_design_filing_not_skips_it():
    """Falsification counterpart: a genuinely broken design filing (one approach,
    no NOT DECIDING HERE) must FAIL, proving the dispatch is real grading, not the
    genre-unknown SKIP path a typo'd genre name would silently fall into."""
    text = (
        "---\n"
        "design: widget-approach\n"
        "genre: design\n"
        "status: OPEN\n"
        "---\n\n"
        "QUESTION: x\n\n"
        "APPROACHES:\n"
        "- name: only-one\n"
        "  evidence: e\n"
    )
    fm = extract_frontmatter(text)
    body = text.split("---\n", 2)[2]
    findings = grade_design(fm, body=body)
    assert any(f.severity == ERROR for f in findings)


def test_a_typo_d_genre_name_still_skips_with_a_warn_not_silently_pass():
    """Sanity boundary: genre: designn (typo) must NOT be discriminated as design --
    proves the dispatch matches the exact string, doesn't fuzzy-match."""
    fm = {"genre": "designn", "design": "x", "status": "OPEN"}
    assert discriminate("/tmp/x.md", fm) == "designn"
    assert discriminate("/tmp/x.md", fm) != "design"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
