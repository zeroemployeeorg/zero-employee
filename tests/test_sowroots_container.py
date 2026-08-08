"""find_sow_roots must see BOTH layouts, including the MIXED state of a live restructure.

MEASURED (GM-DS6-183): glob('*/sow') is single-level -> example-org `0 projects`. The count is
the least of it: ungraded_streams and flat_dark_files iterate sow_roots, so an empty list
means the DARK migration meter reports zero and reads green because it cannot see.
"""

from zero_employee.core import find_sow_roots, ungraded_streams, flat_dark_files


def _mk(root, rel, body="no frontmatter\n"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_the_FLAT_layout_is_still_found(tmp_path):
    _mk(tmp_path, "ducktyper/sow/acting/a.md")
    assert [r.name for r in find_sow_roots(tmp_path)] == ["sow"]
    assert len(find_sow_roots(tmp_path)) == 1


def test_the_CONTAINER_layout_is_found(tmp_path):
    _mk(tmp_path, "projects/ducktyper/sow/acting/a.md")
    roots = find_sow_roots(tmp_path)
    assert len(roots) == 1 and roots[0].parent.name == "ducktyper"


def test_the_MIXED_state_of_a_live_restructure_sees_BOTH(tmp_path):
    """The restructure moves projects one at a time; a half-moved corpus must stay visible."""
    _mk(tmp_path, "ducktyper/sow/acting/a.md")
    _mk(tmp_path, "projects/quackverse/sow/rh/b.md")
    roots = find_sow_roots(tmp_path)
    assert sorted(r.parent.name for r in roots) == ["ducktyper", "quackverse"]


def test_no_double_counting(tmp_path):
    _mk(tmp_path, "projects/ducktyper/sow/acting/a.md")
    assert len(find_sow_roots(tmp_path)) == len(set(find_sow_roots(tmp_path)))


def test_the_DARK_meter_still_sees_pre_schema_streams_under_the_container(tmp_path):
    """The load-bearing consequence: an empty sow_roots blinds the burn-down meter."""
    _mk(tmp_path, "projects/ducktyper/sow/legacy-stream/a.md")
    ug = [u for r in find_sow_roots(tmp_path) for u in ungraded_streams(r)]
    assert [u["stream"] for u in ug] == ["legacy-stream"]
    assert ug[0]["project"] == "ducktyper"


def test_the_DARK_meter_still_sees_FLAT_dark_files_under_the_container(tmp_path):
    _mk(tmp_path, "projects/quackresearch/sow/loose-note.md")
    flat = [x for r in find_sow_roots(tmp_path) for x in flat_dark_files(r)]
    assert len(flat) == 1
