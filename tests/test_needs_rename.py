"""Rename only what the grader rejects.

MEASURED at GM-DS6-152: renaming six already-numbered SOWs would rewrite 8 references in
6 files, including two landed rulings' `requested_by` - an IMMUTABLE field (RULING-004) -
and a landed SOW (append-don't-revert). Cosmetic conformance does not earn that.
"""

from zero_employee.core import needs_rename


def test_a_conformant_name_KEEPS_itself():
    need, why = needs_rename("guide-sweep-SOW-4-request-for-relief.md", 4)
    assert need is False and "kept" in why


def test_an_uppercase_stream_name_that_still_PARSES_is_kept():
    """GUIDE-SWEEP-SOW-04-... parses as <sow>-SOW-<n>-<slug>; the grader accepts it."""
    need, _ = needs_rename("GUIDE-SWEEP-SOW-04-request-for-relief.md", 4)
    assert need is False


def test_a_rev_suffix_EARNS_a_rename():
    need, why = needs_rename("seam-SOW-9-brand-engine-Rev9.md", 9)
    assert need is True and "Rev" in why


def test_a_disagreeing_n_EARNS_a_rename():
    need, why = needs_rename("gs-SOW-4-a.md", 7)
    assert need is True and "disagrees" in why


def test_a_legacy_name_with_no_pattern_EARNS_a_rename():
    need, why = needs_rename("SOW-TrackA-core-fs-completion.md", 18)
    assert need is True and "does not match" in why
