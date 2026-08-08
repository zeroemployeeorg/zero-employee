"""RULING-208: a stream id resolves to a path via the DECLARED sow: field, never the
dirname. build_stream_index is the mechanism; check_binds is the lint that consumes it."""

from zero_employee.core import (
    build_stream_index,
    render_stream_index,
    check_binds,
    check_binds_corpus,
)


def _corpus(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    return tmp_path


def _sow(d, name, sow_id, n=1, extra=""):
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(
        f"---\nsow: {sow_id}\nn: {n}\nstatus: PROGRESS\n{extra}---\n\nbody\n",
        encoding="utf-8",
    )


def test_declared_sow_field_wins_over_dirname():
    """The exact RULING-208 s0 defect: a dir named repo-hygiene declares a DIFFERENT id."""
    import tempfile
    import pathlib

    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _sow(
            root / "quackverse" / "sow" / "repo-hygiene",
            "a.md",
            "quackverse-repo-hygiene",
        )
        idx = build_stream_index(root)
        assert "quackverse-repo-hygiene" in idx
        assert idx["quackverse-repo-hygiene"]["path"] == "quackverse/sow/repo-hygiene"
        assert "repo-hygiene" not in idx  # the DIRNAME is not a separate, false id


def test_preschema_dir_resolves_by_dirname_when_no_file_declares_sow():
    import tempfile
    import pathlib

    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        d = root / "ducktyper" / "sow" / "worldprops"
        d.mkdir(parents=True)
        (d / "a.md").write_text("---\nnote: no schema fields here\n---\n\nbody\n", encoding="utf-8")
        idx = build_stream_index(root)
        assert idx["worldprops"]["path"] == "ducktyper/sow/worldprops"
        assert idx["worldprops"]["preschema"] is True


def test_two_dirs_declaring_the_same_id_are_ambiguous_never_guessed():
    import tempfile
    import pathlib

    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _sow(root / "a" / "sow" / "x1", "f.md", "dup")
        _sow(root / "b" / "sow" / "x2", "f.md", "dup")
        idx = build_stream_index(root)
        assert idx["dup"]["path"] is None
        assert idx["dup"]["ambiguous"] is True
        assert len(idx["dup"]["candidates"]) == 2


def test_render_stream_index_is_fenced_and_lists_every_id():
    import tempfile
    import pathlib

    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _sow(root / "a" / "sow" / "s1", "f.md", "s1")
        idx = build_stream_index(root)
        out = render_stream_index(idx, "deadbeef", "2026-08-07")
        assert "STREAM-INDEX:AUTO" in out and "END STREAM-INDEX" in out
        assert "`s1`" in out and "a/sow/s1" in out


# ── check_binds ──────────────────────────────────────────────────────
IDX = {
    "arch-sep": {
        "path": "ducktyper/sow/arch-sep",
        "candidates": ["ducktyper/sow/arch-sep"],
        "ambiguous": False,
        "project": "ducktyper",
        "preschema": False,
    },
    "dup": {
        "path": None,
        "candidates": ["a/sow/x1", "b/sow/x2"],
        "ambiguous": True,
        "project": None,
        "preschema": False,
    },
}
PROJECTS = {"ducktyper", "governance-layer"}


def test_a_resolving_stream_id_is_silent():
    assert check_binds({"binds": ["arch-sep"]}, IDX, PROJECTS) == []


def test_an_ambiguous_id_is_recorded_never_resolved():
    out = check_binds({"binds": ["dup"]}, IDX, PROJECTS)
    assert len(out) == 1 and out[0].code == "binds-ambiguous"


def test_a_project_token_is_told_to_move_to_scope():
    out = check_binds({"binds": ["governance-layer"]}, IDX, PROJECTS)
    assert len(out) == 1 and out[0].code == "binds-project-not-scope"


def test_a_role_shaped_unresolved_token_asks_for_binds_class():
    out = check_binds({"binds": ["sparring"]}, IDX, PROJECTS)
    assert len(out) == 1 and out[0].code == "binds-needs-class"


def test_a_roster_shaped_unresolved_token_asks_for_binds_class():
    out = check_binds({"binds": ["all-streams"]}, IDX, PROJECTS)
    assert len(out) == 1 and out[0].code == "binds-needs-class"


def test_a_genuinely_unresolved_token_is_flagged_plainly():
    out = check_binds({"binds": ["episode-layout"]}, IDX, PROJECTS)
    assert len(out) == 1 and out[0].code == "binds-unresolved"


def test_binds_class_role_exempts_the_whole_list_even_a_real_stream_id():
    # RULING-208 s4's own worked example: binds-class describes the CITATION's intent.
    out = check_binds({"binds": ["arch-sep", "sparring"], "binds-class": "role"}, IDX, PROJECTS)
    assert out == []


def test_binds_class_stream_does_not_exempt_an_unresolved_token():
    out = check_binds({"binds": ["episode-layout"], "binds-class": "stream"}, IDX, PROJECTS)
    assert len(out) == 1 and out[0].code == "binds-unresolved"


def test_invalid_binds_class_value_is_flagged():
    out = check_binds({"binds": ["arch-sep"], "binds-class": "nonsense"}, IDX, PROJECTS)
    assert any(f.code == "binds-class-invalid" for f in out)


def test_a_malformed_pipe_value_is_flagged():
    out = check_binds({"binds": ["all-streams | master | namedstreams"]}, IDX, PROJECTS)
    assert any(f.code == "binds-malformed" for f in out)


def test_no_binds_field_is_silent():
    assert check_binds({}, IDX, PROJECTS) == []


def test_check_binds_corpus_applies_to_any_genre_with_a_binds_field():
    import tempfile
    import pathlib

    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        d = root / "governance-layer" / "sow" / "zeo-release"
        d.mkdir(parents=True)
        f = d / "CHARTER-01.md"
        f.write_text(
            "---\ngenre: charter\nsow: zeo-release\nstatus: ACTIVE\nbinds: [episode-layout]\n---\n\nbody\n",
            encoding="utf-8",
        )
        files_fm = [
            (
                str(f),
                {
                    "genre": "charter",
                    "sow": "zeo-release",
                    "status": "ACTIVE",
                    "binds": ["episode-layout"],
                },
            )
        ]
        out = check_binds_corpus(files_fm, root)
        assert len(out) == 1
        [(path, findings)] = out.items()
        assert findings[0].code == "binds-unresolved"


def test_commit_mode_promotes_binds_findings_to_error():
    import tempfile
    import pathlib

    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        files_fm = [("r.md", {"genre": "ruling", "binds": ["episode-layout"]})]
        out = check_binds_corpus(files_fm, root, commit_mode=True)
        [(path, findings)] = out.items()
        assert findings[0].severity == "ERROR"
