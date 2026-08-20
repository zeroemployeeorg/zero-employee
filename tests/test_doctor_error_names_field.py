"""RULING-325 §4: `doctor_file`'s ValidationError handler previously discarded
`exc.errors()[0]['loc']` (the actual missing-field PATH) and reported only Pydantic's
generic `.get('msg')` ("Field required") — useless without independently reverse-
engineering `SowWriteFrontmatter` from source, which is exactly what both streams that
found this defect had to do. Fixed to read `loc` and name the field.
"""

from __future__ import annotations

import pathlib

from zero_employee.scaffold import init_corpus
from zero_employee.sow_authoring import doctor_file, render_sow


def _corpus(tmp_path: pathlib.Path) -> pathlib.Path:
    root = tmp_path / "org"
    init_corpus(root)
    return root


def _write_missing_requested_by(root: pathlib.Path) -> pathlib.Path:
    chain = root / "projects" / "p" / "sow" / "s"
    chain.mkdir(parents=True)
    fm = {
        "sow": "s",
        "n": 1,
        "schema_rev": 17,
        "project": "p",
        "status": "DRAFT",
        "lifecycle": "DESIGN-MEMO",
        "created": "2026-08-20",
        "updated": "2026-08-20",
        "genre": "sow",
        "done_when": "pytest -> 0 failures",
        "restaufwand": 1,
        "sow_repo": "example-org/org",
        "work_repo": "example-org/p",
        # requested_by: deliberately absent — the exact ten-file failure shape RULING-325 found
    }
    content = render_sow(fm, "# body\n")
    dest = chain / "S-SOW-01-missing-requested-by.md"
    dest.write_bytes(content)
    return dest


def test_doctor_reports_the_missing_field_by_name_not_generic_msg(tmp_path):
    root = _corpus(tmp_path)
    path = _write_missing_requested_by(root)
    ready, _oks, fails = doctor_file(path, root=root)
    assert not ready
    joined = " | ".join(fails)
    assert "requested_by" in joined, (
        f"doctor must name the missing field, not just Pydantic's generic 'Field required': {fails}"
    )
    # the old behavior this replaces: a bare "Field required" with no field name anywhere
    assert not any(f.strip() == "required fields incomplete: Field required" for f in fails)


def test_doctor_multiple_missing_fields_all_named(tmp_path):
    root = _corpus(tmp_path)
    chain = root / "projects" / "p" / "sow" / "s2"
    chain.mkdir(parents=True)
    # Missing BOTH requested_by and work_repo.
    fm = {
        "sow": "s2",
        "n": 1,
        "schema_rev": 17,
        "project": "p",
        "status": "DRAFT",
        "lifecycle": "DESIGN-MEMO",
        "created": "2026-08-20",
        "updated": "2026-08-20",
        "genre": "sow",
        "done_when": "pytest -> 0 failures",
        "restaufwand": 1,
        "sow_repo": "example-org/org",
    }
    content = render_sow(fm, "# body\n")
    dest = chain / "S2-SOW-01-missing-two.md"
    dest.write_bytes(content)
    ready, _oks, fails = doctor_file(dest, root=root)
    assert not ready
    joined = " | ".join(fails)
    assert "requested_by" in joined
    assert "work_repo" in joined
