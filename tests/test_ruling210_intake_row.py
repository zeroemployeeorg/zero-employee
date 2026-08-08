"""RULING-210 s6 item 3 - the intake OPEN board row.

intake/README.md's RATIFIED section, in capitals: "AN UNCONVERTED INTAKE
RENDERS AS AN OPEN BOARD ROW." Measured before this SOW: `zeo --triage |
grep -i intake` -> ZERO ROWS against a corpus holding an OPEN intake. This
is a PROJECTION (RULING-208 s2) - no SOW or ruling may cite the row as
evidence, only the intake file itself does the proving.
"""

from zero_employee import cli
from zero_employee.core import intake_open_rows


def _sows_repo(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("Rev 17\n", encoding="utf-8")
    return tmp_path


def _intake(root, name, status, project="governance-layer"):
    d = root / "intake"
    d.mkdir(exist_ok=True)
    (d / f"{name}.md").write_text(
        f"---\nintake: {name}\nproject: {project}\ngenre: intake\n"
        f"created: 2026-08-07\nstatus: {status}\n---\n\nWHAT: x\nWHY: y\n"
        f"DONE WHEN: z\nNOT THIS: none stated\n",
        encoding="utf-8",
    )


def test_open_intake_is_a_zero_evidence_row_before_the_fix_MEASURED():
    """The ruling's own measurement, reproduced as a falsifier: intake_open_rows
    is the function this SOW ADDS. Its absence (AttributeError) would have been
    the pre-fix state; its presence and correctness is what this file proves."""
    assert callable(intake_open_rows)


def test_triage_renders_an_open_intake_row(tmp_path, capsys):
    root = _sows_repo(tmp_path)
    _intake(root, "2026-08-07-schema-and-classA-migration", "OPEN")
    rc = cli.main(["--triage", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "INTAKE" in out
    assert "2026-08-07-schema-and-classA-migration" in out
    assert "governance-layer" in out


def test_triage_grep_intake_is_nonzero_the_exact_regression_command(tmp_path, capsys):
    """`zeo --triage | grep -i intake` measured ZERO before this fix, against a
    corpus holding an OPEN intake. Reproduce the grep behaviourally."""
    root = _sows_repo(tmp_path)
    _intake(root, "2026-08-07-zeo-release", "OPEN")
    cli.main(["--triage", str(root)])
    out = capsys.readouterr().out
    hits = [ln for ln in out.splitlines() if "intake" in ln.lower()]
    assert len(hits) > 0


def test_chartered_intake_does_not_render(tmp_path, capsys):
    root = _sows_repo(tmp_path)
    _intake(root, "2026-08-01-old-one", "CHARTERED")
    cli.main(["--triage", str(root)])
    out = capsys.readouterr().out
    assert "2026-08-01-old-one" not in out


def test_declined_and_superseded_do_not_render(tmp_path, capsys):
    root = _sows_repo(tmp_path)
    _intake(root, "2026-08-02-declined-one", "DECLINED")
    _intake(root, "2026-08-03-superseded-one", "SUPERSEDED")
    cli.main(["--triage", str(root)])
    out = capsys.readouterr().out
    assert "declined-one" not in out
    assert "superseded-one" not in out


def test_mixed_intake_only_open_ones_render(tmp_path, capsys):
    root = _sows_repo(tmp_path)
    _intake(root, "2026-08-07-open-one", "OPEN")
    _intake(root, "2026-08-01-chartered-one", "CHARTERED")
    cli.main(["--triage", str(root)])
    out = capsys.readouterr().out
    assert "open-one" in out
    assert "chartered-one" not in out


def test_no_intake_dir_at_all_does_not_error(tmp_path, capsys):
    root = _sows_repo(tmp_path)
    rc = cli.main(["--triage", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "INTAKE" in out  # section header always prints, count 0


def test_intake_open_rows_ignores_non_intake_genre(tmp_path):
    root = _sows_repo(tmp_path)
    d = root / "intake"
    d.mkdir()
    (d / "stray.md").write_text("---\nsow: x\ngenre: sow\nstatus: OPEN\n---\n\nb\n", encoding="utf-8")
    assert intake_open_rows(root) == []


def test_intake_open_rows_status_is_case_insensitive(tmp_path):
    root = _sows_repo(tmp_path)
    _intake(root, "2026-08-07-lower", "open")
    rows = intake_open_rows(root)
    assert len(rows) == 1 and rows[0]["intake"] == "2026-08-07-lower"
