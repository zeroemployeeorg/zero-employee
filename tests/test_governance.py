"""Fold 1 acceptance — skill staleness (governance-docs-first). Both directions.
The header fixture is the EXACT live line from DS3-FOLD1-RECON-20 S1."""

from zero_employee.core import parse_skill_rev, check_skill_staleness, ERROR, WARN

# exact live header line (platform docs/authoring/sow-authoring-SKILL.md, line 8)
SKILL_REV11 = (
    "# Authoring a canonical SOW\n"
    "> **Teaches CLAUDE.md Rev 11** \u00b7 synced 2026-07-11. This skill encodes the SOW "
    "schema as of canonical CLAUDE.md Rev 11 (\u00a714/\u00a715). If canonical is past Rev 11 "
    "and this line has not moved, treat the skill as STALE and re-sync before authoring.\n"
    "body...\n"
)
SKILL_REV12 = SKILL_REV11.replace("Teaches CLAUDE.md Rev 11", "Teaches CLAUDE.md Rev 12")
SKILL_NO_HEADER = "# Authoring a canonical SOW\nno era declared here\n"


def sev(findings, code):
    return next((f.severity for f in findings if f.code == code), None)


def test_parse_skill_rev_from_real_header():
    # must NOT be fooled by the 'canonical CLAUDE.md Rev 11' later in the same line
    assert parse_skill_rev(SKILL_REV11) == 11


def test_G1_stale_skill_warns_not_errors():
    # Rev 11 skill vs canonical Rev 12 -> STALE WARN (the real post-Rev-12 situation)
    out = check_skill_staleness(SKILL_REV11, 12)
    assert sev(out, "skill-stale") == WARN
    assert all(f.severity != ERROR for f in out)


def test_G2_current_skill_clean():
    assert check_skill_staleness(SKILL_REV12, 12) == []


def test_G3_ahead_skill_errors():
    assert sev(check_skill_staleness(SKILL_REV12, 11), "skill-ahead") == ERROR


def test_G4_no_header_warns_indeterminate():
    assert sev(check_skill_staleness(SKILL_NO_HEADER, 12), "skill-rev-missing") == WARN


def test_G5_no_canonical_warns():
    assert sev(check_skill_staleness(SKILL_REV11, None), "skill-nocanon") == WARN
