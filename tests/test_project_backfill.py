"""guide-sweep failed on [project-missing], not on its filename.

project: is DERIVED from the path, so this is a field repair: no model, no rename, no
citation breakage - the cheapest possible fix for the largest measured class.
"""

from zero_employee.core import project_backfill_plan


def _w(root, rel, body):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_a_sow_missing_project_is_planned_with_the_path_derived_value(tmp_path):
    _w(tmp_path, "ducktyper/sow/gs/a.md", "---\nsow: gs\nn: 1\n---\nbody\n")
    rows = project_backfill_plan(tmp_path)["rows"]
    assert rows == [{"file": "ducktyper/sow/gs/a.md", "project": "ducktyper", "sow": "gs"}]


def test_a_sow_that_ALREADY_has_project_is_left_alone(tmp_path):
    _w(tmp_path, "ducktyper/sow/gs/a.md", "---\nsow: gs\nproject: ducktyper\n---\nb\n")
    assert project_backfill_plan(tmp_path)["rows"] == []


def test_a_CLASS_A_file_is_NOT_this_passes_job(tmp_path):
    """No frontmatter at all -> --migrate generates it; this pass must not touch it."""
    _w(tmp_path, "ducktyper/sow/gs/legacy.md", "no frontmatter\n")
    assert project_backfill_plan(tmp_path)["rows"] == []


def test_a_flat_legacy_path_yields_NO_project_and_is_NOT_guessed(tmp_path):
    _w(tmp_path, "sow/gs/a.md", "---\nsow: gs\n---\nb\n")
    plan = project_backfill_plan(tmp_path)
    assert plan["rows"] == []
    assert [u["file"] for u in plan["unresolved"]] == ["sow/gs/a.md"]


def test_the_plan_writes_NOTHING(tmp_path):
    f = _w(tmp_path, "ducktyper/sow/gs/a.md", "---\nsow: gs\n---\nb\n")
    before = f.read_bytes()
    project_backfill_plan(tmp_path)
    assert f.read_bytes() == before
