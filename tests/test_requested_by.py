from zero_employee.core import check_requested_by

STEMS = {
    "DOCS-SORT-SOW-69-archaeology-charter",
    "SEAM-2-Swap-Rev1",
    "DOCS-SORT-SOW-65-q5-mutable-field-collision",
}

SOW_INDEX = {
    ("archive-arch", 22): ("path/irrelevant.md", {}),
    ("ds-6", 3): ("path/irrelevant2.md", {}),
}


def _fm(rb):
    return {"ruling": 1, "genre": "ruling", "requested_by": rb}


# RULING-214 s3 supersedes A1's forward-binding clause: a bare path that resolves is no
# longer silently conformant on its own - it now needs a STATED REASON its target has no
# n: yet, or it is a WARN (the migration's countable burn-down residue, not a defect).
def test_a_bare_resolving_path_with_NO_stated_reason_is_now_a_WARN_not_silent():
    out = check_requested_by(_fm("ducktyper/sow/ds/DOCS-SORT-SOW-69-archaeology-charter.md"), "", STEMS)
    assert len(out) == 1 and out[0].code == "requested_by-unexplained-path"


def test_a_bare_resolving_path_WITH_a_stated_reason_is_fully_legal_and_silent():
    rb = "ducktyper/sow/ds/DOCS-SORT-SOW-69-archaeology-charter.md (pre-schema, no n: yet)"
    assert check_requested_by(_fm(rb), "", STEMS) == []


def test_a_comma_list_of_unexplained_paths_warns_once_per_entry():
    rb = "a/SEAM-2-Swap-Rev1.md, b/DOCS-SORT-SOW-69-archaeology-charter.md"
    out = check_requested_by(_fm(rb), "", STEMS)
    assert len(out) == 2 and all(f.code == "requested_by-unexplained-path" for f in out)


def test_conformant_path_that_resolves_NOWHERE_is_a_ghost():
    # the RULING-014 chimera CLASS, in conformant syntax: clean path, wrong basename.
    # Ghost status is unchanged by s3 - a stated reason does not rescue a wrong filename.
    out = check_requested_by(_fm("sow/ds/DOCS-SORT-SOW-65-v2-lint-design.md"), "", STEMS)
    assert len(out) == 1 and out[0].code == "requested_by-ghost"


def test_operator_directive_is_silent_not_a_ghost():
    # RULING-007's real form. A1: legal non-path. Must NOT fire. Unchanged by s3.
    assert (
        check_requested_by(
            _fm("operator directive 2026-07-15 (fleet work-loss risk; SOW-13 class)"),
            "",
            STEMS,
        )
        == []
    )


def test_prose_and_mixed_forms_are_legacy_not_ghost():
    # RULING-008/014's real forms - the naive comma-split shattered these into phantom ghosts
    # (DS5-DIAG-226/228). They are pre-A1 legacy, routed to the closure-map, NEVER accused.
    # Unchanged by s3 - the shatter guard still classifies the WHOLE string, never per-fragment.
    for rb in [
        "sow/editorial-recon/ (rev-p, RULING-REQUESTED F1/F2/F3) + operator directive 2026-07-15",
        "sow/docs-sort/DOCS-SORT-SOW-65-v2-lint-design.md and sow/editorial-recon rev-r section C",
        "sow/arch-sep/ (rev-o, n:39, RULING-REQUESTED)",
    ]:
        out = check_requested_by(_fm(rb), "", STEMS)
        assert all(f.code != "requested_by-ghost" for f in out), rb


def test_empty_requested_by_is_not_a_ghost():
    assert check_requested_by(_fm(""), "", STEMS) == []


# RULING-214 s3's new canonical form: <stream>#<n>, resolved via a sow_index built once
# corpus-wide (build_sow_n_index), never re-derived from a remembered filename.
def test_stream_n_form_that_resolves_is_silent():
    assert check_requested_by(_fm("archive-arch#22"), "", STEMS, sow_index=SOW_INDEX) == []


def test_stream_n_form_comma_list_all_resolve_is_silent():
    assert check_requested_by(_fm("archive-arch#22, ds-6#3"), "", STEMS, sow_index=SOW_INDEX) == []


def test_stream_n_form_that_does_not_resolve_is_a_ghost():
    out = check_requested_by(_fm("archive-arch#999"), "", STEMS, sow_index=SOW_INDEX)
    assert len(out) == 1 and out[0].code == "requested_by-ghost-stream-n"


def test_stream_n_form_with_no_index_supplied_is_a_ghost_not_a_crash():
    # A caller that hasn't threaded sow_index through yet must not silently pass everything.
    out = check_requested_by(_fm("archive-arch#22"), "", STEMS, sow_index=None)
    assert len(out) == 1 and out[0].code == "requested_by-ghost-stream-n"


def test_mixed_stream_n_and_path_forms_resolve_independently():
    rb = "archive-arch#22, ducktyper/sow/ds/DOCS-SORT-SOW-69-archaeology-charter.md (legacy, no n:)"
    assert check_requested_by(_fm(rb), "", STEMS, sow_index=SOW_INDEX) == []
