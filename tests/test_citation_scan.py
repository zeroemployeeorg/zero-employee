"""RULING-016 s5: a rename breaks every citation pointing at the old name.

citation_scan finds them MECHANICALLY - no model. --migrate needs a claimant because it
synthesises fields from prose; a rename rewrites strings, and 553 documents is nothing
for a scan. The point is that the rename-scope decision is made on a NUMBER.
"""

from zero_employee.core import citation_scan, citation_totals

RMAP = {"GUIDE-SWEEP-SOW-04-request-for-relief.md": "guide-sweep-SOW-4-request-for-relief.md"}


def _w(root, rel, body):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_a_full_filename_citation_is_found(tmp_path):
    _w(
        tmp_path,
        "ruling/RULING-045.md",
        "requested_by: ducktyper/sow/guide-sweep/GUIDE-SWEEP-SOW-04-request-for-relief.md\n",
    )
    hits = citation_scan(tmp_path, RMAP)
    assert hits["ruling/RULING-045.md"][0]["with_ext"] == 1


def test_an_extensionless_stem_citation_is_found_SEPARATELY(tmp_path):
    """Citations appear both ways; the stem match is looser so it is counted apart."""
    _w(
        tmp_path,
        "sow/a.md",
        "as ruled in GUIDE-SWEEP-SOW-04-request-for-relief (see chain)\n",
    )
    e = citation_scan(tmp_path, RMAP)["sow/a.md"][0]
    assert e["with_ext"] == 0 and e["stem_only"] == 1


def test_a_stem_inside_a_full_name_is_NOT_double_counted(tmp_path):
    _w(tmp_path, "sow/a.md", "GUIDE-SWEEP-SOW-04-request-for-relief.md\n")
    e = citation_scan(tmp_path, RMAP)["sow/a.md"][0]
    assert (e["with_ext"], e["stem_only"]) == (1, 0)


def test_an_unrelated_file_is_not_reported(tmp_path):
    _w(tmp_path, "sow/b.md", "nothing to see\n")
    assert citation_scan(tmp_path, RMAP) == {}


def test_the_scan_writes_NOTHING(tmp_path):
    f = _w(tmp_path, "sow/a.md", "GUIDE-SWEEP-SOW-04-request-for-relief.md\n")
    before = f.read_bytes()
    citation_scan(tmp_path, RMAP)
    assert f.read_bytes() == before


def test_totals_give_the_two_numbers_a_decision_needs(tmp_path):
    _w(
        tmp_path,
        "a.md",
        "GUIDE-SWEEP-SOW-04-request-for-relief.md twice: GUIDE-SWEEP-SOW-04-request-for-relief.md\n",
    )
    _w(tmp_path, "b.md", "GUIDE-SWEEP-SOW-04-request-for-relief.md\n")
    assert citation_totals(citation_scan(tmp_path, RMAP)) == (2, 3)
