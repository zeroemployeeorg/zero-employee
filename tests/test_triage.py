"""--triage and the presentation defects (RULING-060; archive-arch SOW-12/13/16)."""

from zero_employee import cli
from zero_employee.core import flat_dark_files, ungraded_streams


def _proj(tmp_path, project, stream=None, name="x.md", body="no frontmatter\n"):
    d = tmp_path / project / "sow"
    if stream:
        d = d / stream
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body, encoding="utf-8")
    return tmp_path / project / "sow"


def test_flat_dark_files_sees_what_the_is_dir_walk_cannot(tmp_path):
    """core.py:796 walks `if x.is_dir()`, so a file sitting flat in sow/ is
    invisible BY CONSTRUCTION - 29 real files across 4 projects."""
    root = _proj(tmp_path, "quackresearch", None, "Act1-Findings.md")
    assert ungraded_streams(root) == [], "the old walk should see nothing here"
    flat = flat_dark_files(root)
    assert len(flat) == 1 and flat[0]["file"] == "Act1-Findings.md"
    assert flat[0]["project"] == "quackresearch"


def test_a_schema_file_sitting_flat_is_not_dark(tmp_path):
    root = _proj(tmp_path, "zeo", None, "graded.md", "---\nsow: zeo\n---\n\nbody\n")
    assert flat_dark_files(root) == []


def test_flat_and_stream_dark_are_both_counted_not_either_or(tmp_path):
    _proj(tmp_path, "p", "streamdir", "a.md")
    root = _proj(tmp_path, "p", None, "flatfile.md")
    assert len(ungraded_streams(root)) == 1
    assert len(flat_dark_files(root)) == 1


def _sows_repo(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("Rev 16\n", encoding="utf-8")
    return tmp_path


def test_triage_prints_all_six_buckets(tmp_path, capsys):
    root = _sows_repo(tmp_path)
    d = root / "governance-layer" / "sow" / "ds-6"
    d.mkdir(parents=True)
    (d / "ds-6-SOW-01-x.md").write_text(
        "---\nsow: ds-6\nn: 1\nschema_rev: 16\nstatus: RULING-REQUESTED\n"
        "project: governance-layer\ncreated: 2026-07-01\nupdated: 2026-07-01\n---\n\nb\n",
        encoding="utf-8",
    )
    rc = cli.main(["--triage", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    for bucket in (
        "NEEDS MASTER",
        "NEEDS A SUCCESSOR",
        "PAUSED",
        "BLOCKED",
        "DARK",
        "RESTING",
    ):
        assert bucket in out, bucket
    assert "ds-6" in out


def test_triage_dark_bucket_counts_flat_files_the_meter_must_not_under_report(tmp_path, capsys):
    """RULING-060 s2.2: DARK is the migration's public burn-down meter."""
    root = _sows_repo(tmp_path)
    _proj(root, "quackresearch", None, "Questions-for-Chad.md")
    cli.main(["--triage", str(root)])
    out = capsys.readouterr().out
    assert "FLAT files" in out and "Questions-for-Chad.md" in out


def test_board_echoes_the_table_not_just_a_digest(tmp_path, capsys):
    """SOW-12 sE.1: the operator saw a one-line count and concluded emptiness."""
    root = _sows_repo(tmp_path)
    d = root / "ducktyper" / "sow" / "s1"
    d.mkdir(parents=True)
    (d / "s1-SOW-01-x.md").write_text(
        "---\nsow: s1\nn: 1\nschema_rev: 16\nstatus: SHIPPED\nproject: ducktyper\n"
        "created: 2026-07-01\nupdated: 2026-07-01\n---\n\nb\n",
        encoding="utf-8",
    )
    cli.main(["--board", str(root)])
    out = capsys.readouterr().out
    assert "STREAM" in out and "s1" in out and "SHIPPED" in out


def test_the_banner_states_the_REAL_version_not_a_hardcoded_string(tmp_path, capsys):
    """SOW-12 sE.3: it printed v0.4 against a 0.10.0 wheel and caused stale-binary
    false alarms all week - one of them mine at DS6-PROV-19."""
    root = _sows_repo(tmp_path)
    f = root / "x.md"
    f.write_text("no frontmatter\n", encoding="utf-8")
    cli.main([str(f)])
    out = capsys.readouterr().out
    assert "v0.4" not in out
    # The test's own name says the banner must not carry a HARDCODED string - and it
    # hardcoded one, so it failed on the 0.11.0 -> 0.12.0 bump and would fail on every
    # future one. Read the version from package metadata: same intent, still catches
    # the v0.4 regression it was written for, and no longer taxes a bump.
    # NOTE: test_migrate.py also carries "0.11.0" and is CORRECT as-is - it INJECTS
    # the version as a parameter and asserts on that, so no bump can reach it.
    from importlib.metadata import version as _pkg_version

    # BOTH distribution names ship: zero-employee is the package, sow-lint is retained
    # as a second console script for 227 immutable references (RULING-093 legacy_name).
    _ver = None
    for _n in ("zero-employee", "sow-lint"):
        try:
            _ver = _pkg_version(_n)
            break
        except Exception:
            continue
    assert _ver and _ver in out


def test_help_documents_triage(capsys):
    cli.main(["--help"])
    out = capsys.readouterr().out
    assert "--triage" in out


# ── the NEEDS-SUCCESSOR filter (RULING-060 s2.1, MANDATED) ────────────
from zero_employee.core import needs_successor


def _aw(stream, n, nnn="019"):
    return {
        "stream": stream,
        "sownum": n,
        "rev": str(n),
        "updated": "2026-07-18",
        "file": f"{stream}-SOW-{n}.md",
        "answered": (nnn, "2026-07-18"),
        "resolved": None,
        "supersession": False,
    }


def _row(stream, latest, status):
    return {
        "stream": stream,
        "project": "p",
        "latest": str(latest),
        "status": status,
        "lifecycle": "-",
        "updated": "x",
        "file": "",
        "note": "",
    }


def test_the_named_defect_sfx_vault_at_SOW9_is_not_listed_at_SOW1():
    """SOW-13's verbatim case: sfx-vault shown pending at SOW-1/2/3 while the
    stream sits at SOW-6. Measured live at 29-of-34 before this filter existed."""
    aw = [_aw("sfx-vault", 1), _aw("sfx-vault", 2), _aw("sfx-vault", 6)]
    listed, supp = needs_successor(aw, [_row("sfx-vault", 9, "SHIPPED")])
    assert listed == [] and len(supp) == 3


def test_the_stream_at_its_own_answered_SOW_is_still_listed():
    aw = [_aw("docs-sort", 80)]
    listed, supp = needs_successor(aw, [_row("docs-sort", 80, "RULING-REQUESTED")])
    assert len(listed) == 1 and supp == []


def test_CLOSEOUT_suppresses_even_an_unorderable_rev():
    aw = [
        {
            "stream": "arch-sep",
            "sownum": -1,
            "rev": "h",
            "updated": "x",
            "file": "f",
            "answered": ("018", "x"),
            "resolved": None,
        }
    ]
    listed, supp = needs_successor(aw, [_row("arch-sep", 52, "CLOSEOUT")])
    assert listed == [] and supp[0][1] == "stream CLOSEOUT"


def test_a_valid_resolved_by_closes_it():
    a = _aw("s", 1)
    a["resolved"] = ("superseded-by", "SOW-2")
    listed, supp = needs_successor([a], [_row("s", 1, "HELD")])
    assert listed == [] and supp[0][1] == "resolved_by"


def test_HELD_alone_does_NOT_suppress_only_the_three_ruled_conditions_do():
    """RULING-060 s2.1 names higher-n, CLOSEOUT, resolved_by. HELD is not on that
    list, and a filter broader than its ruling is an unruled invention."""
    listed, supp = needs_successor([_aw("s", 5)], [_row("s", 5, "HELD")])
    assert len(listed) == 1 and supp == []


def test_an_unorderable_stream_stays_VISIBLE_rather_than_guessed_closed():
    listed, _ = needs_successor([_aw("guide-sweep", 1)], [_row("guide-sweep", "UNKNOWN", "UNKNOWN")])
    assert len(listed) == 1


def test_a_stream_with_no_board_row_is_not_silently_dropped():
    listed, _ = needs_successor([_aw("ghost", 1)], [])
    assert len(listed) == 1
