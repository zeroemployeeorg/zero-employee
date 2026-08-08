"""requested_by must NAME THE FILE (GM-SWEEP-217).

MEASURED: 17 ghosts / 106 resolvable = 14% on the one field that closes a Master->stream loop.
BOOT-MASTER s5 called it the biggest hole in master-to-stream communication and never gated it.
"""

from zero_employee.core import requested_by_ghosts


def _corpus(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    (tmp_path / "ruling").mkdir()
    return tmp_path


def _sow(root, name):
    d = root / "projects/p/sow/s"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text("---\nsow: s\nn: 1\n---\nb\n", encoding="utf-8")


def _ruling(root, name, rb):
    (root / "ruling" / name).write_text(
        "---\nruling: '001'\ngenre: ruling\nstatus: ACTIVE\nlanding_commit: self\nrequested_by: %s\n---\nb\n" % rb,
        encoding="utf-8",
    )


def test_a_resolvable_target_is_not_a_ghost(tmp_path):
    r = _corpus(tmp_path)
    _sow(r, "A-SOW-1-real-name.md")
    _ruling(r, "RULING-001-x.md", "projects/p/sow/s/A-SOW-1-real-name.md")
    assert requested_by_ghosts(r) == []


def test_a_TRUNCATED_tail_is_caught_and_the_nearest_named(tmp_path):
    """The live shape: `-escalation` cited for `-escalation-handover`."""
    r = _corpus(tmp_path)
    _sow(r, "A-SOW-1-escalation-handover.md")
    _ruling(r, "RULING-001-x.md", "projects/p/sow/s/A-SOW-1-escalation.md")
    g = requested_by_ghosts(r)
    assert len(g) == 1 and g[0]["nearest"] == "A-SOW-1-escalation-handover.md"
    assert g[0]["lost"] is False


def test_a_GENUINELY_lost_target_is_flagged_lost(tmp_path):
    """RULING-012's family: no near match, needs a tombstone not a pointer."""
    r = _corpus(tmp_path)
    _sow(r, "A-SOW-1-real.md")
    _ruling(r, "RULING-001-x.md", "projects/p/sow/s/COMPLETELY-DIFFERENT-ZZZZ.md")
    g = requested_by_ghosts(r)
    assert len(g) == 1 and g[0]["lost"] is True


def test_a_MULTI_target_field_checks_every_entry(tmp_path):
    r = _corpus(tmp_path)
    _sow(r, "A-SOW-1-real.md")
    _ruling(
        r,
        "RULING-001-x.md",
        "projects/p/sow/s/A-SOW-1-real.md, projects/p/sow/s/A-SOW-2-missing.md",
    )
    assert len(requested_by_ghosts(r)) == 1


def test_PROSE_in_requested_by_is_not_a_ghost(tmp_path):
    """`requested_by: operator directive 2026-08-02` names no file and is not a broken pointer."""
    r = _corpus(tmp_path)
    _ruling(r, "RULING-001-x.md", "operator directive 2026-08-02")
    assert requested_by_ghosts(r) == []
