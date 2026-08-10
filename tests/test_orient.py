"""Orientation OS: bare zeo, orient --json, help, work, next, new."""

from __future__ import annotations

import json

from zero_employee import cli
from zero_employee.orient import (
    PROTOCOL_VERSION,
    build_next_action,
    build_orientation,
    build_work_listing,
)


def _corpus(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("Rev 17\n", encoding="utf-8")
    (tmp_path / "intake").mkdir()
    return tmp_path


def _sow(root, project, stream, *, n=1, status="DESIGN", extra=""):
    d = root / "projects" / project / "sow" / stream
    d.mkdir(parents=True, exist_ok=True)
    body = (
        f"---\nsow: {stream}\nn: {n}\nschema_rev: 17\nstatus: {status}\n"
        f"project: {project}\ncreated: 2026-08-01\nupdated: 2026-08-09\n"
        f"done_when: Ship it\nrestaufwand: 3\n{extra}---\n\nbody\n"
    )
    (d / f"{stream}-SOW-{n:02d}-x.md").write_text(body, encoding="utf-8")
    return d


def test_bare_zeo_is_orientation_not_usage(tmp_path, monkeypatch, capsys):
    root = _corpus(tmp_path)
    _sow(root, "zero-employee", "doctrine-migration", status="DESIGN")
    monkeypatch.chdir(root)
    rc = cli.main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ZEO · Zero-Employee Organization" in out
    assert "What do you want to do?" in out
    assert "zeo new" in out
    assert "zeo orient --json" in out
    assert "USAGE" not in out


def test_bare_zeo_outside_corpus_suggests_init(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ZEO_SOWS_ROOT", raising=False)
    rc = cli.main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Not oriented" in out
    assert "zeo init" in out


def test_orient_json_protocol(tmp_path, monkeypatch, capsys):
    root = _corpus(tmp_path)
    _sow(root, "ducktyper", "props", status="DESIGN")
    monkeypatch.chdir(root)
    rc = cli.main(["orient", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["protocol_version"] == PROTOCOL_VERSION
    assert data["oriented"] is True
    assert data["corpus"]["root"] == str(root.resolve())
    assert "active_streams" in data["work"]
    assert data["work"]["active_streams"] >= 1
    assert "entrypoints" in data
    assert data["entrypoints"]["new_work"] == "zeo new --json"
    assert len(data["rules"]) >= 4


def test_orient_json_unoriented(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ZEO_SOWS_ROOT", raising=False)
    rc = cli.main(["orient", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["oriented"] is False


def test_help_progressive(capsys):
    assert cli.main(["help"]) == 0
    out = capsys.readouterr().out
    assert "Getting started" in out
    assert "zeo help --all" in out
    assert "--migrate <file>" not in out

    assert cli.main(["help", "--all"]) == 0
    full = capsys.readouterr().out
    assert "--migrate <file>" in full
    assert "Legacy aliases remain supported" in full

    assert cli.main(["help", "intake"]) == 0
    topic = capsys.readouterr().out
    assert "zeo intake" in topic

    assert cli.main(["--help"]) == 0
    assert "Getting started" in capsys.readouterr().out


def test_work_listing(tmp_path, monkeypatch, capsys):
    root = _corpus(tmp_path)
    _sow(root, "zero-employee", "doctrine-migration", status="DESIGN")
    _sow(root, "ducktyper", "props", status="BLOCKED", n=1)
    monkeypatch.chdir(root)
    rc = cli.main(["work"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ACTIVE" in out
    assert "doctrine-migration" in out
    assert "WAITING ON YOU" in out
    assert "props" in out

    rc = cli.main(["work", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert any(x["stream"] == "doctrine-migration" for x in data["active"])


def test_work_stream_detail(tmp_path, monkeypatch, capsys):
    root = _corpus(tmp_path)
    _sow(root, "zero-employee", "doctrine-migration", status="DESIGN")
    monkeypatch.chdir(root)
    rc = cli.main(["work", "doctrine-migration"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "doctrine-migration" in out
    assert "SOW-1" in out or "SOW-01" in out or "SOW-1" in out
    assert "zeo orient --stream doctrine-migration --json" in out


def test_next_prefers_intake_when_quiet_otherwise(tmp_path, monkeypatch, capsys):
    root = _corpus(tmp_path)
    (root / "intake" / "2026-08-09-idea.md").write_text(
        "---\ngenre: intake\nid: 2026-08-09-idea\nstatus: OPEN\n"
        "created: 2026-08-09\nupdated: 2026-08-09\n---\n\n# idea\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(root)
    rc = cli.main(["next", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["kind"] == "intake"
    assert "intake mission" in data["command"]


def test_next_inside_stream(tmp_path, monkeypatch):
    root = _corpus(tmp_path)
    d = _sow(
        root,
        "zero-employee",
        "doctrine-migration",
        status="DESIGN",
        extra="next_three_acts:\n  - implement acceptance item 2\n",
    )
    n = build_next_action(root=root, cwd=d)
    assert n.kind == "continue_stream"
    assert "acceptance" in n.summary or "Continue" in n.summary


def test_new_json_choices(capsys):
    assert cli.main(["new", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["protocol_version"] == PROTOCOL_VERSION
    assert len(data["choices"]) == 3
    keys = {c["key"] for c in data["choices"]}
    assert keys == {"intake", "sow", "project"}


def test_triage_and_board_subcommands(tmp_path, monkeypatch, capsys):
    root = _corpus(tmp_path)
    _sow(root, "zero-employee", "doctrine-migration", status="RULING-REQUESTED")
    monkeypatch.chdir(root)
    assert cli.main(["triage"]) == 0
    assert "NEEDS MASTER" in capsys.readouterr().out
    assert cli.main(["board"]) == 0
    out = capsys.readouterr().out
    assert "doctrine-migration" in out or (root / "STATE.md").is_file()


def test_index_and_mint_aliases(tmp_path, monkeypatch, capsys):
    root = _corpus(tmp_path)
    (root / "ruling").mkdir(exist_ok=True)
    monkeypatch.chdir(root)
    assert cli.main(["index", "streams"]) == 0
    assert (root / "stream-index.md").is_file()
    assert cli.main(["mint", "ruling"]) == 0
    out = capsys.readouterr().out.lower()
    assert "ruling" in out or "race" in out or out.strip() != ""


def test_build_orientation_stream_context(tmp_path):
    root = _corpus(tmp_path)
    d = _sow(root, "zero-employee", "doctrine-migration", status="DESIGN")
    o = build_orientation(root=root, cwd=d)
    assert o.oriented
    assert o.active_context is not None
    assert o.active_context.kind == "stream"
    assert o.active_context.stream == "doctrine-migration"


def test_work_listing_builder(tmp_path):
    root = _corpus(tmp_path)
    _sow(root, "p", "s1", status="PROGRESS")
    listing = build_work_listing(root)
    assert any(i.stream == "s1" for i in listing.active)


def test_init_footer_mentions_orient(tmp_path, capsys):
    root = tmp_path / "org"
    rc = cli.main(["init", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "zeo orient --json" in out
    assert "zeo new" in out
