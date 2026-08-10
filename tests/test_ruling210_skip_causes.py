"""RULING-210 - the instrument was not blind; its report was.

Behavioural proof, not textual: the ruling itself was found by MEASUREMENT
(`zeo intake/... | grep -c genre-unknown` -> 0), so these tests run the CLI
and grep its stdout, the same shape of check named in s6/s7.

Three things the ruling charters (s6), one hard fence (s1/s7):
  1. the summary counter is split into named-cause buckets, a zero-valued
     cause prints nothing.
  2. the genre-unknown WARN (core.py:472-479) is rendered, not discarded.
  3. NOT tested here: the open-world default itself (core.py:466-479) - it
     is explicitly out of scope and must not change (that is test_v2_genre_
     ruling.py's territory, untouched by this SOW).
"""

from zero_employee import cli


def _sows_repo(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("Rev 17\n", encoding="utf-8")
    return tmp_path


def _write(tmp_path, rel, body):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


# ── item 2: the genre-unknown WARN reaches stdout, non-zero, where it was 0 ──


def test_genre_unknown_warn_now_prints_MEASURED_nonzero(tmp_path, capsys):
    """The exact command RULING-210 s2 measured as returning 0:
    `zeo <file> | grep -c genre-unknown`. This asserts the fixed side: >0.

    Intake is now a graded genre (intake_authoring); use a still-open-world genre
    so the WARN path remains covered.
    """
    f = _write(
        tmp_path,
        "misc/2026-08-07-x.md",
        "---\nnote: x\nproject: governance-layer\ngenre: session-record\ncreated: 2026-08-07\nstatus: OPEN\n---\n\nbody\n",
    )
    rc = cli.main([str(f)])
    out = capsys.readouterr().out
    assert rc == 0  # a SKIP is not a FAIL - the file isn't graded, not condemned
    assert out.count("genre-unknown") >= 1, "the WARN core.py already builds must render"
    assert "has no grader" in out


def test_intake_genre_is_graded_not_genre_unknown(tmp_path, capsys):
    """Regression: intake used to fall through to genre-unknown SKIP; now graded."""
    f = _write(
        tmp_path,
        "intake/2026-08-07-x.md",
        "---\nintake: x\nid: x\nproject: governance-layer\ngenre: intake\n"
        "created: 2026-08-07\nupdated: 2026-08-07\nstatus: OPEN\n---\n\nWHAT: x\nDONE WHEN: y\n",
    )
    rc = cli.main([str(f)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "genre-unknown" not in out
    assert "1 passed" in out


def test_genre_unknown_finding_message_is_the_real_one_not_paraphrased(tmp_path, capsys):
    f = _write(tmp_path, "x/tombstone-1.md", "---\nsow: x\ngenre: tombstone\n---\n\nb\n")
    cli.main([str(f)])
    out = capsys.readouterr().out
    assert "genre: tombstone has no grader" in out
    assert "SKIPPED, not graded as a SOW" in out


# ── item 1: the summary counter names causes, never one hardcoded label ──


def test_named_genre_unknown_cause_replaces_the_false_no_frontmatter_label(tmp_path, capsys):
    """The paid failure, verbatim: 'a genre: reference file with full frontmatter
    reports byte-identically to a dark file (1 skipped (no frontmatter))'. After
    the fix an unknown-genre file must NOT be counted under the no-frontmatter
    bucket, and the no-frontmatter bucket must not appear when its count is zero."""
    f = _write(tmp_path, "x/tombstone-1.md", "---\nsow: x\ngenre: tombstone\n---\n\nb\n")
    cli.main([str(f)])
    out = capsys.readouterr().out
    assert "skipped (genre not graded)" in out
    assert "skipped (no frontmatter)" not in out, (
        "a file carrying real frontmatter must never be miscounted as having none"
    )


def test_true_no_frontmatter_file_keeps_its_own_named_cause(tmp_path, capsys):
    f = _write(tmp_path, "x/prose.md", "just a prose file, no frontmatter block at all\n")
    cli.main([str(f)])
    out = capsys.readouterr().out
    assert "skipped (no frontmatter)" in out
    assert "skipped (genre not graded)" not in out
    assert "skipped (deliberate)" not in out


def test_deliberate_skip_genre_gets_its_own_named_cause_no_warn_noise(tmp_path, capsys):
    """relay remains deliberate SKIP. Learnings are graded (HINT on empty diary)."""
    f = _write(tmp_path, "ruling/note.md", "---\nsow: x\ngenre: relay\n---\n\nb\n")
    rc = cli.main([str(f)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "skipped (deliberate)" in out
    assert "skipped (no frontmatter)" not in out
    assert "skipped (genre not graded)" not in out
    assert "genre-unknown" not in out


def test_learnings_are_graded_not_deliberately_skipped(tmp_path, capsys):
    """Learnings left _SKIP_GENRES — empty diary is HINT, file PASSes (exit 0)."""
    f = _write(tmp_path, "learnings/x/note.md", "---\nsow: x\ngenre: learnings\n---\n\nb\n")
    rc = cli.main([str(f)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "hint-learnings-empty" in out or "HINT:" in out
    assert "skipped (deliberate)" not in out
    assert "1 passed" in out


def test_a_zero_valued_cause_prints_nothing_the_binding_conformance_rule(tmp_path, capsys):
    """RULING-210 conformance: 'a summary line names the cause of every count it
    prints, or prints no cause at all. A zero-valued cause prints nothing.' A run
    with nothing skipped at all must carry NO skip clause whatsoever."""
    f = _write(
        tmp_path,
        "x/a.md",
        "---\nsow: x\nn: 1\nschema_rev: 17\nstatus: SHIPPED\nproject: p\n"
        "created: 2026-08-07\nupdated: 2026-08-07\n---\n\nb\n",
    )
    cli.main([str(f)])
    out = capsys.readouterr().out
    assert "skipped" not in out


def test_mixed_corpus_names_every_cause_it_counts(tmp_path, capsys):
    root = _sows_repo(tmp_path)
    _write(root, "p/sow/x/tomb.md", "---\nsow: x\ngenre: tombstone\n---\n\nb\n")
    _write(root, "p/sow/x/prose.md", "just prose\n")
    _write(root, "ruling/relay-note.md", "---\nsow: x\ngenre: relay\n---\n\nb\n")
    rc = cli.main([str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "skipped (genre not graded)" in out
    assert "skipped (no frontmatter)" in out
    assert "skipped (deliberate)" in out
    assert "skipped (pre-schema block)" not in out


# ── --quiet: a stated decision, not a silent one (s6 item 2) ──


def test_quiet_suppresses_the_per_file_block_but_keeps_the_named_count(tmp_path, capsys):
    f = _write(tmp_path, "x/tombstone-1.md", "---\nsow: x\ngenre: tombstone\n---\n\nb\n")
    cli.main(["--quiet", str(f)])
    out = capsys.readouterr().out
    assert "skipped (genre not graded)" in out
    assert "has no grader" not in out, "the per-file diagnosis block must be suppressed"


def test_help_documents_quiet():
    rc = cli.main(["help", "--all"])
    assert rc == 0


def test_help_text_mentions_quiet(capsys):
    cli.main(["help", "--all"])
    out = capsys.readouterr().out
    assert "--quiet" in out
