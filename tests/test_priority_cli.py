"""zeo --priority CLI wiring (RULING-279, PRIORITY-NWA-SOW-1 done_when items 3-4)."""

import json

from zero_employee import cli


def _corpus(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    return tmp_path


def _sow(root, project, stream, n, *, status="PROGRESS", restaufwand=None, updated="2026-08-01", ledger_shipped=0):
    d = root / project / "sow" / stream
    d.mkdir(parents=True, exist_ok=True)
    fm = ["---", f"sow: {stream}", f"n: {n}", f"status: {status}", f"created: {updated}", f"updated: {updated}"]
    if restaufwand is not None:
        fm.append(f"restaufwand: {restaufwand}")
    if ledger_shipped:
        fm.append("ledger:")
        for i in range(ledger_shipped):
            fm.append(f"  - claim: c{i}")
            fm.append("    state: SHIPPED")
            fm.append("    commit: abc123")
            fm.append('    check: "make verify"')
    fm.append("---")
    (d / f"{stream}-SOW-{n}-x.md").write_text("\n".join(fm) + "\n\nbody\n", encoding="utf-8")


def test_priority_cli_prints_funded_and_near_miss_with_delta(tmp_path, capsys):
    """RULING-279 s3: a fixture with MORE candidates than top_n so the near-miss
    set is non-empty and printed, with its Nutzwert delta - the opportunity-cost
    requirement proven end-to-end through the real CLI entrypoint."""
    root = _corpus(tmp_path)
    for i in range(5):
        _sow(root, "p", f"stream-{i}", 1, status="PROGRESS", restaufwand=5 + i, ledger_shipped=1)
    rc = cli.main(["--priority", "--top", "2", "--near-miss", "2", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "NUTZWERTANALYSE" in out
    assert "FUNDED" in out
    assert "OPPORTUNITÄTSKOSTEN" in out
    assert "delta-to-last-funded" in out
    # top 2 funded, next 2 named as near-miss (5 candidates > top_n+near_m)
    assert out.count("nutzwert=") >= 4


def test_priority_cli_json_shape(tmp_path, capsys):
    root = _corpus(tmp_path)
    for i in range(4):
        _sow(root, "p", f"stream-{i}", 1, status="PROGRESS", restaufwand=3 + i, ledger_shipped=1)
    rc = cli.main(["--priority", "--top", "1", "--near-miss", "2", "--json", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["kind"] == "nutzwertanalyse"
    assert len(data["funded"]) == 1
    assert len(data["near_miss"]) == 2
    assert "weights" in data
    # tokens only, never currency, in every row
    for row in data["funded"] + data["near_miss"]:
        assert "restaufwand_tokens" in row
        assert "usd" not in row


def test_priority_cli_no_rankable_streams_is_honest_not_a_crash(tmp_path, capsys):
    root = _corpus(tmp_path)
    _sow(root, "p", "done", 1, status="CLOSEOUT", restaufwand=0, ledger_shipped=1)
    rc = cli.main(["--priority", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no OPEN/PAUSED/BLOCKED stream to rank" in out


def test_priority_never_prints_currency():
    """RULING-279's explicit instruction: tokens throughout, never currency, in the
    ranking's own output (PRIORITY-NWA-SOW-1 s3's 'no currency anywhere')."""
    import inspect

    from zero_employee.cli import _priority

    src = inspect.getsource(_priority)
    assert "usd" not in src.lower()
    assert "$" not in src
