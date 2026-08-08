"""RULING-093 s2: the era-gate keys on the FILENAME, not on project_of()."""

import zero_employee.core as core


def _legacy(tmp_path):
    d = tmp_path / "ducktyper" / "sow" / "seam"
    d.mkdir(parents=True)
    f = d / "SEAM-2-BrandFont-Weight-Clamp-Finding-Rev1.md"  # a REAL blocked file
    f.write_text("---\nn: 43\nsow: arch-sep\n---\nbody\n", encoding="utf-8")
    return f


def test_a_legacy_filename_in_a_MIGRATED_project_is_WARN_not_ERROR(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "project_of", lambda p, r=None: "ducktyper")
    out = core.check_n(str(_legacy(tmp_path)), {"n": 43, "sow": "arch-sep"})
    assert [f.code for f in out] == ["n-pattern-premigration"]
    assert all(f.severity == core.WARN for f in out)


def test_NO_path_shape_yields_an_ERROR_n_pattern_for_a_legacy_name(tmp_path, monkeypatch):
    """The invariant: the ERROR arm is unreachable by PLACEMENT."""
    for proj in ("ducktyper", "quackverse", None):
        monkeypatch.setattr(core, "project_of", lambda p, r=None, _v=proj: _v)
        out = core.check_n(str(_legacy(tmp_path / str(proj))), {"n": 43, "sow": "arch-sep"})
        assert "n-pattern" not in [f.code for f in out], f"ERROR reachable via {proj}"


def test_a_CONFORMANT_filename_is_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "project_of", lambda p, r=None: "ducktyper")
    d = tmp_path / "ducktyper" / "sow" / "docs-sort"
    d.mkdir(parents=True)
    f = d / "docs-sort-SOW-7-a-slug.md"
    f.write_text("---\nn: 7\nsow: docs-sort\n---\nbody\n", encoding="utf-8")
    out = core.check_n(str(f), {"n": 7, "sow": "docs-sort"})
    assert [x.code for x in out] == []
