from zero_employee.core import (
    awaiting_ruling,
    sow_identity,
    latest_rev_of,
    render_state_zone,
    splice_state_zone,
    STATE_FENCE_OPEN,
    STATE_FENCE_CLOSE,
)


def _f(path, **fm):
    return (path, fm)


def test_identity_prefers_n_then_filename():
    assert sow_identity("x/DOCS-SORT-SOW-67-a.md", {"n": 67}) == 67
    # streams that put the number in the NAME and the revision in rev:
    assert sow_identity("x/LLMALS-HUD-SOW-03-baseline.md", {"rev": "a"}) == 3
    assert sow_identity("x/EDITORIAL-RECON-SOW-01-findings-rev-q.md", {}) == 1
    assert sow_identity("x/sow-phase-wp-world-props-rev-o.md", {}) is None


def test_latest_rev_grandfathers_unnumbered_legacy():
    # n: arrived at Rev 11; a legacy entry without one must not blind the stream.
    e = [{"n": None}, {"n": 66}, {"n": 67}]
    assert latest_rev_of(e)["n"] == 67


def test_latest_rev_unknown_only_when_nothing_orderable():
    assert latest_rev_of([{"n": None}, {"n": None}]) is None


def test_latest_rev_breaks_n_tie_by_letter_rev():
    # THE BUG (editorial-recon, live on disk): a chain that mints n: once and
    # encodes true order via rev: a, b, c ... z ties every entry on n, so a bare
    # max()-on-n silently returns whichever entry the caller built first -- not
    # the true tail. 27 real files reproduced this exactly (all n: 1, rev: a..z);
    # the board rendered the rev-k snapshot instead of rev-z. This test uses the
    # SAME shape, deliberately built with the true-latest entry FIRST in the list
    # so a first-wins fallback (the pre-fix behavior) would fail it.
    entries = [
        {"n": 1, "rev": "k", "updated": "2026-07-11"},
        {"n": 1, "rev": "a", "updated": "2026-07-01"},
        {"n": 1, "rev": "z", "updated": "2026-08-16"},
        {"n": 1, "rev": "b", "updated": "2026-07-02"},
    ]
    top = latest_rev_of(entries)
    assert top["rev"] == "z"
    assert top["updated"] == "2026-08-16"


def test_latest_rev_breaks_n_tie_by_multiletter_rev():
    # rev chains that run past z (aa, ab, ac ...) are live on disk too -- the
    # tiebreak must rank multi-letter revs correctly, not just single letters.
    entries = [
        {"n": 1, "rev": "z", "updated": "2026-01-01"},
        {"n": 1, "rev": "aa", "updated": "2026-01-02"},
        {"n": 1, "rev": "ac", "updated": "2026-01-04"},
        {"n": 1, "rev": "ab", "updated": "2026-01-03"},
    ]
    assert latest_rev_of(entries)["rev"] == "ac"


def test_latest_rev_breaks_n_tie_by_numeric_rev():
    # some chains use rev: 1, 2, 3 ... instead of letters -- numeric rev must be
    # ranked as a number, not lexically ("10" before "9" would be wrong).
    entries = [
        {"n": 1, "rev": 2, "updated": "2026-01-01"},
        {"n": 1, "rev": 10, "updated": "2026-01-02"},
        {"n": 1, "rev": 9, "updated": "2026-01-03"},
    ]
    assert latest_rev_of(entries)["rev"] == 10


def test_latest_rev_falls_back_to_date_when_rev_unorderable():
    # a rev value that isn't a clean int or letter run (a bare word, a compound
    # id) can't be ranked -- fall back to updated:/created: date rather than
    # guessing at an ordering the field doesn't actually encode.
    entries = [
        {"n": 1, "rev": "charter", "updated": "2026-01-01"},
        {"n": 1, "rev": "charter-7", "updated": "2026-03-01"},
        {"n": 1, "rev": "pm1", "updated": "2026-02-01"},
    ]
    assert latest_rev_of(entries)["updated"] == "2026-03-01"


def test_latest_rev_ties_truly_indistinguishable_keep_first():
    # nothing orderable at all (no rev, no date) -- the prior file-scan-order
    # behavior is preserved as the last resort, not a crash or a new guess.
    entries = [{"n": 1, "first": True}, {"n": 1, "first": False}]
    assert latest_rev_of(entries)["first"] is True


def test_a_later_sow_does_NOT_close_a_ruling_request():
    # THE RULE: only a RULING closes a request. Excluding on "a later SOW exists"
    # hid docs-sort SOW-63/66 behind SOW-67 — the exact failure this detects.
    ff = [
        _f(
            "p/sow/ds/DOCS-SORT-SOW-63-x.md",
            sow="ds",
            n=63,
            status="RULING-REQUESTED",
            updated="2026-07-15",
        ),
        _f(
            "p/sow/ds/DOCS-SORT-SOW-67-y.md",
            sow="ds",
            n=67,
            status="PROGRESS",
            updated="2026-07-16",
        ),
    ]
    out = awaiting_ruling(ff)
    assert [r["rev"] for r in out] == ["63"]


def test_revisions_of_one_sow_collapse_to_latest():
    ff = [
        _f(
            "p/sow/er/ER-SOW-01-findings-rev-k.md",
            sow="er",
            status="RULING-REQUESTED",
            updated="2026-07-11",
        ),
        _f(
            "p/sow/er/ER-SOW-01-findings-rev-q.md",
            sow="er",
            status="RULING-REQUESTED",
            updated="2026-07-15",
        ),
    ]
    out = awaiting_ruling(ff)
    assert len(out) == 1 and out[0]["updated"] == "2026-07-15"


def test_answered_requires_an_EXACT_filename_match():
    # A false ANSWERED tells a stream to proceed on a ruling nobody made.
    ff = [
        _f(
            "p/sow/ds/DOCS-SORT-SOW-63-x.md",
            sow="ds",
            n=63,
            status="RULING-REQUESTED",
            updated="2026-07-15",
        ),
        _f(
            "p/ruling/RULING-016-batch.md",
            ruling=16,
            genre="ruling",
            requested_by="SOW-63 SOW-64 and the six-item nudge",
            updated="2026-07-16",
        ),
    ]
    assert awaiting_ruling(ff)[0]["answered"] is None  # prose ≠ proof


def test_answered_fires_on_a_named_file_and_zero_pads():
    ff = [
        _f(
            "p/sow/as/SEAM-2-Swap-Request-Rev1.md",
            sow="as",
            status="RULING-REQUESTED",
            updated="2026-07-10",
        ),
        _f(
            "p/ruling/RULING-001-comic.md",
            ruling=1,
            genre="ruling",
            requested_by="sow/as/SEAM-2-Swap-Request-Rev1.md",
            updated="2026-07-11",
        ),
    ]
    r = awaiting_ruling(ff)[0]
    assert r["answered"] is not None and r["answered"][0] == "001"


def test_state_zone_is_rebuilt_whole_and_roadmap_survives():
    zone = render_state_zone([], "abc1234", "2026-07-17")
    existing = "# STATE\n\n## ROADMAP\nmaster's plan\n\n" + STATE_FENCE_OPEN + "\nSTALE\n" + STATE_FENCE_CLOSE + "\n"
    out = splice_state_zone(existing, zone)
    assert "master's plan" in out and "STALE" not in out
    assert splice_state_zone(out, zone) == out  # idempotent


def test_malformed_fence_fails_loud():
    zone = render_state_zone([], "abc1234", "2026-07-17")
    try:
        splice_state_zone(STATE_FENCE_CLOSE + "\nx\n" + STATE_FENCE_OPEN, zone)
        assert False, "should have raised"
    except ValueError:
        pass


def test_zone_carries_freshness_and_navigation_bindings():
    z = render_state_zone([], "869c729", "2026-07-17")
    assert "869c729" in z and "2026-07-17" in z
    assert "Navigation, not evidence" in z


def test_unknown_genre_skips_and_warns_never_falls_through():
    # Master coins genres at will: tombstone, session-record, escalation-memo all
    # appeared AFTER the dispatch was written. RULING-012 (genre: tombstone) fell
    # through to the SOW grader and collected project-backfill + b2-premigration —
    # SOW rules applied to a ruling. Unknown => SKIP + WARN, never the wrong grader.
    import tempfile
    import pathlib as _pl
    from zero_employee.core import lint_file

    for g in (
        "tombstone",
        "session-record",
        "escalation-memo",
        "a-genre-invented-tomorrow",
    ):
        with tempfile.TemporaryDirectory() as d:
            p = _pl.Path(d) / "X-SOW-01-y.md"
            p.write_text(f"---\ngenre: {g}\nstatus: ACTIVE\n---\nbody\n")
            st, fs = lint_file(str(p), current_rev=13, root=d)
            assert st == "SKIP", (g, st)
            assert [f.code for f in fs] == ["genre-unknown"], (g, fs)


def test_known_genres_still_route_correctly():
    import tempfile
    import pathlib as _pl
    from zero_employee.core import lint_file

    with tempfile.TemporaryDirectory() as d:
        p = _pl.Path(d) / "RULING-016-x.md"
        p.write_text("---\nruling: 016\ngenre: ruling\nstatus: ACTIVE\nlanding_commit:\n---\n")
        st, fs = lint_file(str(p), current_rev=13, root=d)
        assert st == "FAIL" and any("RULING-016" in f.message for f in fs)


def test_cli_inbox_and_board_run_without_a_path_argument(tmp_path, monkeypatch):
    # THE GAP THIS CLOSES: make verify was GREEN on a binary that crashed at main()
    # because no test invoked the CLI dispatch - only the functions. A dispatch crash
    # (orphaned root = positional[0], DS5-DIAG-251) passed the letter of the gate. Now
    # main() itself is exercised: --board and --inbox must exit 0 with an auto-found root.
    import zero_employee.cli as cli

    # build a minimal sows repo: claude-md/CLAUDE.md marker + one SOW
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# CLAUDE.md\nRev 13\n")
    d = tmp_path / "ducktyper" / "sow" / "docs-sort"
    d.mkdir(parents=True)
    (d / "DOCS-SORT-SOW-01-x.md").write_text(
        "---\nsow: docs-sort\nn: 1\nstatus: RULING-REQUESTED\nupdated: 2026-07-18\n---\nbody\n"
    )
    monkeypatch.chdir(tmp_path)
    assert cli.main(["--inbox", "docs-sort"]) == 0  # no path: auto-discovered from cwd
    assert cli.main(["--board"]) == 0  # no path: auto-discovered
    assert cli.main(["--inbox", "docs-sort", str(tmp_path)]) == 0  # explicit path still works


def test_cli_help_exits_zero():
    import zero_employee.cli as cli

    assert cli.main(["--help"]) == 0


def test_cli_migrate_check_dispatches_and_fails_blank_file(tmp_path):
    # THE RECURRING GAP: a flag that parses but doesn't dispatch (orphaned below the
    # board/inbox root guard - DS5-DIAG-312). --migrate-check takes a FILE, needs no repo,
    # must dispatch BEFORE the root guard. This test invokes main() so the fall-through
    # (which printed usage + returned 2) can never silently ship again.
    import zero_employee.cli as cli

    blank = tmp_path / "PRE-SCHEMA-DOC.md"
    blank.write_text("# just a prose doc\nno frontmatter here\n")
    rc = cli.main(["--migrate-check", str(blank)])
    assert rc == 1, "a blank file must FAIL migrate-check (rc=1), not fall through to usage"


def test_cli_migrate_check_passes_conformant(tmp_path):
    import zero_employee.cli as cli

    good = tmp_path / "X-SOW-01-y.md"
    good.write_text(
        "---\nsow: x\nn: 1\nschema_rev: 14\nstatus: SHIPPED\ncreated: 2026-07-18\n"
        "updated: 2026-07-18\nsow_repo: r\nwork_repo: same-as-sow_repo\nproject: ducktyper\n"
        'ledger:\n  - claim: c\n    state: SHIPPED\n    commit: abc\n    check: "make verify"\n---\nbody\n'
    )
    rc = cli.main(["--migrate-check", str(good)])
    assert rc == 0, "a conformant SOW must PASS migrate-check (rc=0)"


def test_cli_inbox_declares_invisible_coverage(tmp_path, capsys, monkeypatch):
    # RULING-023 s5 / Sparring s2: the inbox must DECLARE its blind spot, never print a
    # confident 0 that means blindness. A stream with pre-schema (unparseable) files must
    # show them as INVISIBLE, not silently drop them into a false "caught up".
    import zero_employee.cli as cli

    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("Rev 14\n")
    d = tmp_path / "ducktyper" / "sow" / "blindtest"
    d.mkdir(parents=True)
    # one readable SOW, two pre-schema (no frontmatter)
    (d / "BLINDTEST-SOW-01-x.md").write_text(
        "---\nsow: blindtest\nn: 1\nstatus: RULING-REQUESTED\nupdated: 2026-07-18\n---\nbody\n"
    )
    (d / "OLD-prose-doc-a.md").write_text("# just prose, no frontmatter\n")
    (d / "OLD-prose-doc-b.md").write_text("# also prose\n")
    monkeypatch.chdir(tmp_path)
    assert cli.main(["--inbox", "blindtest"]) == 0
    out = capsys.readouterr().out
    assert "INVISIBLE" in out, "inbox must declare pre-schema files as INVISIBLE"
    assert "2 INVISIBLE" in out, f"should count exactly 2 invisible, got:\n{out}"


def test_lint_file_fails_bad_status_enum(tmp_path):
    # THE HOLE (DS5-DIAG-333→350): lint_file never checked status-in-enum — only migrate_check
    # did — so `zeo <file>` graded status:NONSENSE as "passed". check_status closes it,
    # gated on canonical shape (project_of) so pre-schema files aren't newly-failed.
    import zero_employee.core as core

    d = tmp_path / "ducktyper" / "sow" / "st"
    d.mkdir(parents=True)
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("Rev 14\n")
    bad = d / "ST-SOW-01-x.md"
    bad.write_text("---\nsow: st\nn: 1\nschema_rev: 14\nstatus: NONSENSE\nproject: ducktyper\ngenre: sow\n---\nbody\n")
    status, findings = core.lint_file(bad, root=tmp_path)
    assert status == "FAIL", f"bad status must FAIL, got {status}"
    assert any(f.code == "status-enum" for f in findings), "must emit status-enum ERROR"


def test_lint_file_accepts_valid_status(tmp_path):
    import zero_employee.core as core

    d = tmp_path / "ducktyper" / "sow" / "st"
    d.mkdir(parents=True)
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("Rev 14\n")
    good = d / "ST-SOW-02-y.md"
    good.write_text(
        "---\nsow: st\nn: 2\nschema_rev: 14\nstatus: SHIPPED\nproject: ducktyper\ngenre: sow\n"
        "created: 2026-07-18\nupdated: 2026-07-18\nledger:\n  - claim: c\n    state: SHIPPED\n"
        "    commit: abc\n    check: x\n---\nbody\n"
    )
    status, findings = core.lint_file(good, root=tmp_path)
    assert not any(f.code == "status-enum" for f in findings), "valid status must not error"


def test_cannot_grade_is_a_third_output_not_a_silent_pass(tmp_path):
    # Sparring SOW-79 s2 (binding): silent downgrade is the one behavior an enforcement
    # instrument is never permitted. A schema-era file the linter can't fully resolve
    # (schema_rev present but canonical rev unlocatable -> schema-nocanon) must return
    # CANNOT-GRADE, never PASS-on-a-WARN. Pre-schema files (no schema_rev) stay SKIP.
    import zero_employee.core as core

    d = tmp_path / "ducktyper" / "sow" / "cg"
    d.mkdir(parents=True)
    # NO claude-md marker in tmp_path -> canonical rev unlocatable -> schema-nocanon
    f = d / "CG-SOW-01-x.md"
    f.write_text(
        "---\nsow: cg\nn: 1\nschema_rev: 14\nstatus: SHIPPED\nproject: ducktyper\ngenre: sow\n"
        "created: 2026-07-19\nupdated: 2026-07-19\nledger:\n  - claim: c\n    state: SHIPPED\n"
        "    commit: abc\n    check: x\n---\nbody\n"
    )
    status, findings = core.lint_file(f, current_rev=None, root=tmp_path)
    assert status == "CANNOT-GRADE", f"schema-era + unresolvable must be CANNOT-GRADE, got {status}"


def test_pre_schema_file_is_skip_not_cannot_grade(tmp_path):
    # the distinction that keeps it honest: a file with NO schema_rev is pre-schema -> SKIP,
    # NOT CANNOT-GRADE (which would wrongly block pre-schema commits). s2's declared line.
    import zero_employee.core as core

    d = tmp_path / "ducktyper" / "sow" / "cg"
    d.mkdir(parents=True)
    f = d / "OLD-prose.md"
    f.write_text("# just prose, no frontmatter\n")
    status, _ = core.lint_file(f, root=tmp_path)
    assert status == "SKIP", f"pre-schema file must SKIP, got {status}"
