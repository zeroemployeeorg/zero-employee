from zero_employee.core import (
    discriminate,
    check_ruling,
    check_ruling_corpus,
    ERROR,
    WARN,
)


def test_explicit_genre_wins_over_filename_shape():
    assert discriminate("ruling/RULING-004-x.md", {"genre": "ruling"}) == "ruling"
    assert discriminate("sow/x/DOCS-SORT-SOW-60-y.md", {"genre": "learnings"}) == "learnings"


def test_filename_shape_fallback_for_untagged_rulings():
    assert discriminate("ruling/RULING-001-comic.md", {}) == "ruling"
    assert discriminate("ruling/RULING-002-adj.md", {}) == "ruling"


def test_non_rulings_in_ruling_dir_are_relay_not_sow():
    for name in [
        "SPARRING-COSIGN-002-005.md",
        "LANDING-NOTE-x.md",
        "Sparring-to-Master-Directive-1-y.md",
        "Motion-Grammar-Lexicon-v1.md",
    ]:
        assert discriminate("ruling/" + name, {}) == "relay", name


def test_sow_and_learnings_classify():
    assert discriminate("sow/docs-sort/DOCS-SORT-SOW-63-x.md", {}) == "sow"
    assert discriminate("learnings/docs-sort/2026-07-14-docs-sort.md", {}) == "learnings"


def test_active_ruling_without_landing_commit_FAILS():
    out = check_ruling({"ruling": 4, "status": "ACTIVE", "genre": "ruling"})
    assert any(f.code == "ruling-unlanded" and f.severity == ERROR for f in out)


def test_amended_also_requires_landing_commit():
    out = check_ruling({"ruling": 5, "status": "AMENDED", "genre": "ruling"})
    assert any(f.code == "ruling-unlanded" for f in out)


def test_landing_commit_self_is_valid():
    out = check_ruling({"ruling": 4, "status": "ACTIVE", "landing_commit": "self", "genre": "ruling"})
    assert not [f for f in out if f.severity == ERROR]


def test_superseded_needs_successor():
    out = check_ruling({"ruling": 1, "status": "SUPERSEDED", "genre": "ruling"})
    assert any(f.code == "ruling-nosuccessor" and f.severity == ERROR for f in out)


def test_untagged_ruling_warns_but_does_not_fail():
    out = check_ruling({"ruling": 1, "status": "ACTIVE", "landing_commit": "3c2783d"})
    assert any(f.code == "ruling-genre-missing" and f.severity == WARN for f in out)
    assert not [f for f in out if f.severity == ERROR]


def test_identity_comes_from_BYTES_not_from_yamls_octal_reading():
    # YAML 1.1: `ruling: 016` -> 14, `012` -> 10, `010` -> 8 (leading zero = OCTAL).
    # Padding the PARSED value made the wrong id look right: check_ruling reported
    # RULING-016's file as "RULING-014" — a real, different, correctly-landed
    # ruling. A manufactured ghost citation (DS5-DIAG-175). Read the bytes.
    raw = "---\nruling: 016\nstatus: ACTIVE\ngenre: ruling\nlanding_commit:\n---\nbody"
    out = check_ruling({"ruling": 14, "status": "ACTIVE", "genre": "ruling"}, raw_text=raw)
    assert any("RULING-016" in f.message for f in out)
    assert not any("RULING-014" in f.message for f in out)


def test_octal_ids_across_the_live_range():
    for literal in ("008", "009", "010", "012", "016"):
        raw = f"---\nruling: {literal}\nstatus: ACTIVE\ngenre: ruling\nlanding_commit:\n---\n"
        out = check_ruling({"status": "ACTIVE", "genre": "ruling"}, raw_text=raw)
        assert any(f"RULING-{literal}" in f.message for f in out), literal


def test_flat_namespace_collision_is_ERROR():
    # RULING-200 s1/s2 (landed 2026-08-02): only ORG-SCOPE rulings share one flat
    # counter - project-scope reuse across namespaces is LEGAL. Both sides here must
    # declare scope: org for a collision to be real (RULING-216 s1's own correction).
    ff = [
        ("ruling/RULING-004-a.md", {"scope": "org"}),
        ("ruling/RULING-004-b.md", {"scope": "org"}),
    ]
    out = check_ruling_corpus(ff)
    assert out and all(f.code == "ruling-collision" for v in out.values() for f in v)


def test_distinct_nnn_do_not_collide():
    ff = [
        ("ruling/RULING-004-a.md", {"scope": "org"}),
        ("ruling/RULING-005-b.md", {"scope": "org"}),
    ]
    assert check_ruling_corpus(ff) == {}


def test_same_nnn_across_project_scopes_is_LEGAL_not_a_collision():
    """RULING-200 s2's own paradigm case (the 93/95/96/97 quartet): per-project counters
    are legal, so the SAME integer in TWO different scopes must NOT collide."""
    ff = [
        ("ruling/RULING-093-org.md", {"scope": "org"}),
        ("projects/ducktyper/ruling/RULING-093-dt.md", {"scope": "project:ducktyper"}),
    ]
    assert check_ruling_corpus(ff) == {}


def test_a_bare_missing_scope_is_not_treated_as_org():
    """A file with no scope: field at all must not accidentally collide with a real
    org-scope file - silence is not scope: org."""
    ff = [("ruling/RULING-050-a.md", {"scope": "org"}), ("ruling/RULING-050-b.md", {})]
    assert check_ruling_corpus(ff) == {}


def test_amendment_marker_status_still_hits_the_keystone_R014():
    # THE HOLE (DS5-DIAG-119): RULING-014 s3 legalised an open-ended marker
    # (ACTIVE-AMENDED-SEE-EOF). An exact-match enum skipped the keystone entirely,
    # so an unlanded amended ruling PASSED. Prefix-match, never enumerate.
    fm = {"ruling": 10, "status": "ACTIVE-AMENDED-SEE-EOF", "genre": "ruling"}
    out = check_ruling(fm)
    assert any(f.code == "ruling-unlanded" and f.severity == ERROR for f in out)


def test_amendment_marker_status_with_landing_commit_is_clean():
    fm = {
        "ruling": 10,
        "status": "ACTIVE-AMENDED-SEE-EOF",
        "landing_commit": "d0370ab",
        "genre": "ruling",
    }
    assert not [f for f in check_ruling(fm) if f.severity == ERROR]


def test_future_unknown_markers_also_gated():
    for st in ["ACTIVE-AMENDED-2026-07-16", "AMENDED-SEE-EOF", "SUPERSEDED-BY-014"]:
        out = check_ruling({"ruling": 9, "status": st, "genre": "ruling"})
        assert out, st
