"""binding_rulings_for_stream / --inbox's BINDING RULINGS section.

MEASURED live in ducktyper-ai/org (2026-08-17): a fresh Master read `--inbox`'s own
doctrine literally and reported back, correctly, that the tool could not deliver a
PROACTIVE fleet-binding ruling to a stream that never asked a question. `--inbox` was
built entirely from `awaiting_ruling()` -- a question -> answer channel keyed on a
SOW's own `status: RULING-REQUESTED` and a ruling's `requested_by` citing that SOW
back. A ruling that binds via `binds: [all-streams]` (or a direct stream id) with NO
`requested_by:` naming the stream at all is real, in force, and binding -- and was
invisible to every stream's inbox by construction, no matter what actually bound it.

This module first PROVES the gap exists in the old mechanism (awaiting_ruling alone
sees nothing), then proves the new section closes it.
"""

from __future__ import annotations

import zero_employee.cli as cli
import zero_employee.core as core


def _claude_md(tmp_path):
    (tmp_path / "claude-md").mkdir(parents=True, exist_ok=True)
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("Rev 17\n")


def _stream_dir(tmp_path, project, stream):
    d = tmp_path / project / "sow" / stream
    d.mkdir(parents=True, exist_ok=True)
    return d


def _files_fm(root):
    out = []
    for f in core.iter_sow_files(root):
        fm = core.extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if isinstance(fm, dict):
            out.append((str(f), fm))
    return out


def test_falsification_awaiting_ruling_alone_is_blind_to_a_proactive_fleet_ruling(tmp_path):
    """The bug as reported: a stream that never asked a question has NOTHING in
    awaiting_ruling() for it, even though a real, landed, ACTIVE ruling binds it via
    `binds: [all-streams]`. This is the exact mechanism --inbox used exclusively
    before this fix -- proving the old codepath truly cannot see this ruling."""
    _claude_md(tmp_path)
    _stream_dir(tmp_path, "quackvideo", "quackvideo-cold-start")
    (tmp_path / "quackvideo" / "sow" / "quackvideo-cold-start" / "QUACKVIDEO-COLD-START-SOW-01-x.md").write_text(
        "---\nsow: quackvideo-cold-start\nn: 1\nschema_rev: 17\nproject: quackvideo\n"
        "status: FINDING\nlifecycle: RECON\ngenre: sow\nupdated: 2026-08-17\n---\nbody\n"
    )
    ruling_dir = tmp_path / "ruling"
    ruling_dir.mkdir(parents=True, exist_ok=True)
    (ruling_dir / "RULING-300-fleet-wide-thing.md").write_text(
        '---\nruling: 300\ntitle: "Everyone does X"\nauthority: master\nscope: org\n'
        "status: ACTIVE\nrequested_by: 'operator instruction'\ncreated: 2026-08-17\n"
        "updated: 2026-08-17\nlanding_commit: self\nbinds: [all-streams]\ngenre: ruling\n"
        "conformance: acknowledged\n---\nbody\n"
    )
    files_fm = _files_fm(tmp_path)
    aw = core.awaiting_ruling(files_fm, root=tmp_path)
    mine = [r for r in aw if str(r["stream"]).lower() == "quackvideo-cold-start"]
    assert mine == [], (
        "falsification failed: awaiting_ruling() unexpectedly saw the proactive ruling -- "
        "the bug this test documents does not reproduce, so the fix below would be unproven"
    )


def test_binding_rulings_for_stream_sees_the_same_proactive_ruling(tmp_path):
    """The fix: binding_rulings_for_stream sees exactly the ruling awaiting_ruling missed."""
    _claude_md(tmp_path)
    _stream_dir(tmp_path, "quackvideo", "quackvideo-cold-start")
    (tmp_path / "quackvideo" / "sow" / "quackvideo-cold-start" / "QUACKVIDEO-COLD-START-SOW-01-x.md").write_text(
        "---\nsow: quackvideo-cold-start\nn: 1\nschema_rev: 17\nproject: quackvideo\n"
        "status: FINDING\nlifecycle: RECON\ngenre: sow\nupdated: 2026-08-17\n---\nbody\n"
    )
    ruling_dir = tmp_path / "ruling"
    ruling_dir.mkdir(parents=True, exist_ok=True)
    (ruling_dir / "RULING-300-fleet-wide-thing.md").write_text(
        '---\nruling: 300\ntitle: "Everyone does X"\nauthority: master\nscope: org\n'
        "status: ACTIVE\nrequested_by: 'operator instruction'\ncreated: 2026-08-17\n"
        "updated: 2026-08-17\nlanding_commit: self\nbinds: [all-streams]\ngenre: ruling\n"
        "conformance: acknowledged\n---\nbody\n"
    )
    files_fm = _files_fm(tmp_path)
    hits = core.binding_rulings_for_stream(files_fm, "quackvideo-cold-start", tmp_path)
    assert len(hits) == 1, f"expected exactly one binding ruling, got {hits}"
    assert hits[0]["ruling"] == "300"
    assert hits[0]["acknowledged"] is False, "no SOW cites RULING-300 yet -- must show NOT-YET-CITED"


def test_direct_stream_id_binds_without_all_streams(tmp_path):
    """binds: naming the stream id DIRECTLY (no all-streams roster) also delivers."""
    _claude_md(tmp_path)
    _stream_dir(tmp_path, "quackimage", "quackimage-cold-start")
    (tmp_path / "quackimage" / "sow" / "quackimage-cold-start" / "QUACKIMAGE-COLD-START-SOW-01-x.md").write_text(
        "---\nsow: quackimage-cold-start\nn: 1\nschema_rev: 17\nproject: quackimage\n"
        "status: FINDING\nlifecycle: RECON\ngenre: sow\nupdated: 2026-08-17\n---\nbody\n"
    )
    ruling_dir = tmp_path / "ruling"
    ruling_dir.mkdir(parents=True, exist_ok=True)
    (ruling_dir / "RULING-301-targeted-thing.md").write_text(
        '---\nruling: 301\ntitle: "quackimage specifically"\nauthority: master\n'
        "scope: 'stream:quackimage-cold-start'\nstatus: ACTIVE\n"
        "requested_by: 'operator instruction'\ncreated: 2026-08-17\nupdated: 2026-08-17\n"
        "landing_commit: self\nbinds: [quackimage-cold-start]\ngenre: ruling\n"
        "conformance: acknowledged\n---\nbody\n"
    )
    files_fm = _files_fm(tmp_path)
    hits = core.binding_rulings_for_stream(files_fm, "quackimage-cold-start", tmp_path)
    assert len(hits) == 1
    assert hits[0]["ruling"] == "301"

    # a DIFFERENT stream is correctly NOT bound by a ruling naming this one only
    other_hits = core.binding_rulings_for_stream(files_fm, "some-other-stream", tmp_path)
    assert other_hits == []


def test_acknowledged_flips_true_once_the_stream_cites_the_ruling_back(tmp_path):
    """Same doctrine as every other closure in this corpus: citation IS the receipt.
    A later SOW from the bound stream naming RULING-300 anywhere in its bytes flips
    acknowledged True -- no new ack field, no kanban card, just the existing rule
    applied to a ruling nobody originally asked for."""
    _claude_md(tmp_path)
    d = _stream_dir(tmp_path, "quackvideo", "quackvideo-cold-start")
    (d / "QUACKVIDEO-COLD-START-SOW-01-x.md").write_text(
        "---\nsow: quackvideo-cold-start\nn: 1\nschema_rev: 17\nproject: quackvideo\n"
        "status: FINDING\nlifecycle: RECON\ngenre: sow\nupdated: 2026-08-17\n---\nbody\n"
    )
    ruling_dir = tmp_path / "ruling"
    ruling_dir.mkdir(parents=True, exist_ok=True)
    (ruling_dir / "RULING-300-fleet-wide-thing.md").write_text(
        '---\nruling: 300\ntitle: "Everyone does X"\nauthority: master\nscope: org\n'
        "status: ACTIVE\nrequested_by: 'operator instruction'\ncreated: 2026-08-17\n"
        "updated: 2026-08-17\nlanding_commit: self\nbinds: [all-streams]\ngenre: ruling\n"
        "conformance: acknowledged\n---\nbody\n"
    )
    files_fm = _files_fm(tmp_path)
    before = core.binding_rulings_for_stream(files_fm, "quackvideo-cold-start", tmp_path)
    assert before[0]["acknowledged"] is False

    (d / "QUACKVIDEO-COLD-START-SOW-02-x.md").write_text(
        "---\nsow: quackvideo-cold-start\nn: 2\nschema_rev: 17\nproject: quackvideo\n"
        "status: PROGRESS\nlifecycle: DESIGN-MEMO\ngenre: sow\nupdated: 2026-08-18\n"
        "supersedes: 1\n---\nActed on RULING-300 as directed.\n"
    )
    files_fm = _files_fm(tmp_path)
    after = core.binding_rulings_for_stream(files_fm, "quackvideo-cold-start", tmp_path)
    assert after[0]["acknowledged"] is True, "citing RULING-300 in a later SOW must flip acknowledged True"


def test_superseded_ruling_no_longer_binds(tmp_path):
    """A SUPERSEDED/VOIDED ruling does not bind -- only ACTIVE/AMENDED do."""
    _claude_md(tmp_path)
    _stream_dir(tmp_path, "quackvideo", "quackvideo-cold-start")
    (tmp_path / "quackvideo" / "sow" / "quackvideo-cold-start" / "QUACKVIDEO-COLD-START-SOW-01-x.md").write_text(
        "---\nsow: quackvideo-cold-start\nn: 1\nschema_rev: 17\nproject: quackvideo\n"
        "status: FINDING\nlifecycle: RECON\ngenre: sow\nupdated: 2026-08-17\n---\nbody\n"
    )
    ruling_dir = tmp_path / "ruling"
    ruling_dir.mkdir(parents=True, exist_ok=True)
    (ruling_dir / "RULING-302-retired-thing.md").write_text(
        '---\nruling: 302\ntitle: "Retired"\nauthority: master\nscope: org\n'
        "status: SUPERSEDED\nsuperseded_by: 303\nrequested_by: 'operator instruction'\n"
        "created: 2026-08-01\nupdated: 2026-08-17\nlanding_commit: self\n"
        "binds: [all-streams]\ngenre: ruling\nconformance: acknowledged\n---\nbody\n"
    )
    files_fm = _files_fm(tmp_path)
    hits = core.binding_rulings_for_stream(files_fm, "quackvideo-cold-start", tmp_path)
    assert hits == [], "a SUPERSEDED ruling must not appear as currently binding"


def test_cli_inbox_prints_the_binding_rulings_section(tmp_path, capsys, monkeypatch):
    """End-to-end: `zeo --inbox <stream>` itself now prints the new section and the
    unacknowledged proactive ruling, not just the internal function."""
    _claude_md(tmp_path)
    _stream_dir(tmp_path, "quackvideo", "quackvideo-cold-start")
    (tmp_path / "quackvideo" / "sow" / "quackvideo-cold-start" / "QUACKVIDEO-COLD-START-SOW-01-x.md").write_text(
        "---\nsow: quackvideo-cold-start\nn: 1\nschema_rev: 17\nproject: quackvideo\n"
        "status: FINDING\nlifecycle: RECON\ngenre: sow\nupdated: 2026-08-17\n---\nbody\n"
    )
    ruling_dir = tmp_path / "ruling"
    ruling_dir.mkdir(parents=True, exist_ok=True)
    (ruling_dir / "RULING-300-fleet-wide-thing.md").write_text(
        '---\nruling: 300\ntitle: "Everyone does X"\nauthority: master\nscope: org\n'
        "status: ACTIVE\nrequested_by: 'operator instruction'\ncreated: 2026-08-17\n"
        "updated: 2026-08-17\nlanding_commit: self\nbinds: [all-streams]\ngenre: ruling\n"
        "conformance: acknowledged\n---\nbody\n"
    )
    monkeypatch.chdir(tmp_path)
    assert cli.main(["--inbox", "quackvideo-cold-start"]) == 0
    out = capsys.readouterr().out
    assert "BINDING RULINGS" in out
    assert "RULING-300" in out
    assert "NOT-YET-CITED" in out
