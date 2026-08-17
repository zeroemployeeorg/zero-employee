"""board_rows() / --triage's DARK meter must not treat a non-`sow`-genre filing
(design/ruling/learnings/charter) sharing a sow/<stream>/ directory as a stream
revision to be rev-ordered.

MEASURED live (ducktyper-ai/org, 2026-08-17), reported by a peer Master: a
`design`-genre filing (RULING-286's fifth genre) landed inside
quackvideo/sow/cold-start/ alongside the real QUACKVIDEO-COLD-START-SOW-01. The
design filing correctly carries no `sow:` field (design-authoring-SKILL specifies
none), so board_rows() fell back to the bare directory name (`cold-start`) as a
brand-new phantom stream id -- disjoint from the real `quackvideo-cold-start`
stream, which declares its own `sow:` id. That phantom stream had zero
integer-`n` entries, so latest_rev_of() returned None and it rendered UNKNOWN --
a document that lints CLEAN in a fully supported genre inflated the DARK
burn-down meter.

This module reproduces the exact shape (a design filing beside a numbered SOW in
the same directory) and proves board_rows() no longer creates the phantom row.
"""

from __future__ import annotations

import zero_employee.cli as cli
import zero_employee.core as core


def _claude_md(tmp_path):
    (tmp_path / "claude-md").mkdir(parents=True, exist_ok=True)
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("Rev 17\n")


def _files_fm(root):
    out = []
    for f in core.iter_sow_files(root):
        fm = core.extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if isinstance(fm, dict):
            out.append((str(f), fm))
    return out


def _seed_corpus(tmp_path):
    _claude_md(tmp_path)
    d = tmp_path / "quackvideo" / "sow" / "cold-start"
    d.mkdir(parents=True, exist_ok=True)
    (d / "QUACKVIDEO-COLD-START-SOW-01-ist-aufnahme.md").write_text(
        "---\nsow: quackvideo-cold-start\nn: 1\nschema_rev: 17\nproject: quackvideo\n"
        "status: FINDING\nlifecycle: RECON\ngenre: sow\nupdated: 2026-08-17\n---\nbody\n"
    )
    (d / "FLEET-DESIGN-01-deferred-survey-items.md").write_text(
        "---\ndesign: deferred-survey-items\nproject: quackvideo\ngenre: design\n"
        "created: 2026-08-17\nstatus: OPEN\ndecided_into:\n---\n"
        "QUESTION: does this corpus wait for the stack detector?\n\n"
        "APPROACHES:\n- name: wait\n  evidence: none yet\n  tradeoff: idle\n"
        "- name: measure by hand\n  evidence: none yet\n  tradeoff: manual\n\n"
        "NOT DECIDING HERE: none\n"
    )
    return d


def test_falsification_a_design_filing_beside_a_sow_used_to_spawn_a_phantom_dark_stream(tmp_path, monkeypatch):
    """Confirms the bug reproduces under the OLD mechanism directly: a file whose
    genre is not 'sow' but sits in a sow/<stream>/ dir with no sow: field, grouped
    the way board_rows() grouped before this fix (by directory-name fallback with
    no genre filter), IS ungradeable by latest_rev_of alone -- i.e. the entries
    list for that phantom key really does contain nothing orderable, proving the
    old (unfiltered) grouping would render UNKNOWN. This does not call the fixed
    board_rows(); it isolates the exact mechanism that made the bug real."""
    d = _seed_corpus(tmp_path)
    design_fm = core.extract_frontmatter((d / "FLEET-DESIGN-01-deferred-survey-items.md").read_text(encoding="utf-8"))
    phantom_entries = [{"n": design_fm.get("n"), "rev": design_fm.get("rev")}]
    assert core.latest_rev_of(phantom_entries) is None, (
        "falsification failed: the design filing's own entry was unexpectedly orderable -- "
        "the phantom-stream mechanism this test documents does not reproduce"
    )


def test_board_rows_does_not_create_a_phantom_stream_for_a_design_filing(tmp_path):
    """The fix: board_rows() must show exactly ONE stream (the real one, quackvideo-
    cold-start, correctly at rev 1) and NO phantom 'cold-start' UNKNOWN row."""
    _seed_corpus(tmp_path)
    files_fm = _files_fm(tmp_path)
    rows = core.board_rows(files_fm)
    stream_ids = {r["stream"] for r in rows}
    assert "cold-start" not in stream_ids, f"phantom directory-named stream leaked through: {rows}"
    assert stream_ids == {"quackvideo-cold-start"}, f"expected exactly one real stream, got {rows}"
    real = next(r for r in rows if r["stream"] == "quackvideo-cold-start")
    assert real["latest"] == "1"
    assert real["status"] == "FINDING"


def test_cli_triage_reports_zero_dark_with_a_clean_design_filing_present(tmp_path, monkeypatch, capsys):
    """End-to-end: `zeo --triage .` itself must not count the design filing as DARK."""
    _seed_corpus(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["--triage", "."]) == 0
    out = capsys.readouterr().out
    assert "DARK - invisible to the board; the migration burn-down meter (doctrine): 0" in out, out
    assert "UNKNOWN-rev" not in out, out
