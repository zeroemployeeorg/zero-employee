""" "has a --- block" is not "is schema-era" (GM-DS6-199)."""

from zero_employee.core import is_schema_shaped, lint_file, ungraded_streams, find_sow_roots

NOTE_ONLY = (
    "---\nnote: >\n  Save to the SOW repo as sow/worldprops/rev-j.md\n---\n\n"
    "# SOW - Phase WP (Rev J)\n\nreal body prose\n"
)
REAL_SOW = "---\nsow: wp\nn: 1\nstatus: SHIPPED\nproject: ducktyper\n---\n\n# body\n"


def _mk(root, rel, body):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_a_note_only_block_is_NOT_schema_shaped():
    assert is_schema_shaped({"note": "save me"}) is False


def test_any_schema_key_makes_it_schema_shaped():
    for k in ("sow", "n", "status", "genre", "ruling"):
        assert is_schema_shaped({k: "x"}) is True


def test_a_delivery_note_file_SKIPS_with_a_WARN_not_a_FAIL(tmp_path):
    """It was FAILING on project-missing: missing ONE field when it is missing every field."""
    f = _mk(tmp_path, "ducktyper/sow/wp/rev-j.md", NOTE_ONLY)
    status, findings = lint_file(str(f))
    assert status == "SKIP", (status, [x.code for x in findings])
    assert any(x.code == "preschema-block" for x in findings)


def test_a_REAL_sow_is_unaffected(tmp_path):
    f = _mk(tmp_path, "ducktyper/sow/wp/real.md", REAL_SOW)
    status, _ = lint_file(str(f))
    assert status == "PASS"


def test_the_DARK_meter_sees_a_stream_whose_only_blocks_are_DELIVERY_NOTES(tmp_path):
    """Ten accidental blocks made a whole stream read GRADED and hid its Class-A files."""
    _mk(tmp_path, "ducktyper/sow/wp/rev-j.md", NOTE_ONLY)
    _mk(tmp_path, "ducktyper/sow/wp/rev-a.md", "# SOW no frontmatter at all\n")
    ug = [u for r in find_sow_roots(tmp_path) for u in ungraded_streams(r)]
    assert [u["stream"] for u in ug] == ["wp"], ug
    assert ug[0]["files"] == 2


def test_a_stream_with_ONE_real_sow_is_NOT_pre_schema(tmp_path):
    _mk(tmp_path, "ducktyper/sow/wp/real.md", REAL_SOW)
    _mk(tmp_path, "ducktyper/sow/wp/rev-a.md", "# no frontmatter\n")
    ug = [u for r in find_sow_roots(tmp_path) for u in ungraded_streams(r)]
    assert ug == []
