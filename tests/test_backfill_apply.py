"""The first MUTATION: insert project: and nothing else."""

import yaml
from zero_employee.core import project_backfill_plan, project_backfill_apply


def _w(root, rel, body):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def _corpus(tmp_path):
    return _w(
        tmp_path,
        "ducktyper/sow/gs/a.md",
        "---\nsow: gs\nn: 1\nstatus: SHIPPED\n---\n\n# Title\n\nbody line\n",
    )


def test_exactly_one_line_is_added_and_the_BODY_is_byte_identical(tmp_path):
    f = _corpus(tmp_path)
    before = f.read_text(encoding="utf-8")
    project_backfill_apply(tmp_path, project_backfill_plan(tmp_path)["rows"])
    after = f.read_text(encoding="utf-8")
    assert len(after.splitlines()) == len(before.splitlines()) + 1
    assert before.split("---", 2)[-1] == after.split("---", 2)[-1]
    assert "project: ducktyper" in after


def test_the_result_still_parses_as_yaml(tmp_path):
    f = _corpus(tmp_path)
    project_backfill_apply(tmp_path, project_backfill_plan(tmp_path)["rows"])
    fm = yaml.safe_load(f.read_text(encoding="utf-8").split("---")[1])
    assert fm["project"] == "ducktyper" and fm["sow"] == "gs" and fm["n"] == 1


def test_a_double_run_is_a_NO_OP(tmp_path):
    """s4 refuse-or-idempot: operator double-runs happen."""
    f = _corpus(tmp_path)
    project_backfill_apply(tmp_path, project_backfill_plan(tmp_path)["rows"])
    once = f.read_text(encoding="utf-8")
    res = project_backfill_apply(tmp_path, project_backfill_plan(tmp_path)["rows"])
    assert f.read_text(encoding="utf-8") == once
    assert res["written"] == []


def test_limit_bounds_the_first_batch(tmp_path):
    _w(tmp_path, "ducktyper/sow/gs/a.md", "---\nsow: gs\n---\nb\n")
    _w(tmp_path, "ducktyper/sow/gs/b.md", "---\nsow: gs\n---\nb\n")
    res = project_backfill_apply(tmp_path, project_backfill_plan(tmp_path)["rows"], limit=1)
    assert len(res["written"]) == 1


def test_two_sow_lines_are_REFUSED_not_guessed(tmp_path):
    _w(tmp_path, "ducktyper/sow/gs/a.md", "---\nsow: gs\nsow: gs2\n---\nb\n")
    rows = [{"file": "ducktyper/sow/gs/a.md", "project": "ducktyper", "sow": "gs"}]
    res = project_backfill_apply(tmp_path, rows)
    assert res["written"] == [] and "expected 1" in res["failed"][0]["why"]
