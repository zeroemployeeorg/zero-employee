"""Pydantic genre schemas, HINT severity, and reserving mint."""

from __future__ import annotations

from zero_employee import cli
from zero_employee.core import (
    HINT,
    lint_file,
    reserve_ruling_stub,
    reserve_sow_stub,
    words_to_slug,
)
from zero_employee.schemas import grade_sow
from zero_employee.schemas.common import LIFECYCLES, STATUS_ENUM, STATUS_WORKING


def test_shared_enums_cover_working_and_resting():
    assert STATUS_WORKING < STATUS_ENUM
    assert "DRAFT" in STATUS_WORKING
    assert "STALE" in STATUS_ENUM - STATUS_WORKING
    assert "RECON" in LIFECYCLES


def test_words_to_slug_normalizes():
    assert words_to_slug("Motion Diagnosis Two Mechanisms!") == "motion-diagnosis-two-mechanisms"
    assert words_to_slug("") == "untitled"


def test_grade_sow_presence_check_is_hint_not_error():
    fm = {
        "status": "SHIPPED",
        "lifecycle": "CLOSEOUT-RECORD",
        "ledger": [
            {
                "claim": "imports",
                "state": "SHIPPED",
                "commit": "abc1234",
                "check": 'python -c "import foo"',
            }
        ],
    }
    findings = grade_sow(fm, project_known=True, path_canonical=True)
    codes = {f.code for f in findings}
    assert "hint-presence-check" in codes
    assert any(f.severity == HINT and f.code == "hint-presence-check" for f in findings)


def test_hint_does_not_fail_exit_code(tmp_path, capsys):
    d = tmp_path / "proj" / "sow" / "ds-6"
    d.mkdir(parents=True)
    f = d / "ds-6-SOW-01-ok.md"
    f.write_text(
        "---\nsow: ds-6\nn: 1\nschema_rev: 17\nstatus: SHIPPED\nproject: proj\n"
        "created: 2026-08-08\nupdated: 2026-08-08\nlifecycle: CLOSEOUT-RECORD\n"
        "ledger:\n  - claim: x\n    state: SHIPPED\n    commit: abc\n"
        "    check: 'python -c \"import x\"'\n---\n\nbody\n",
        encoding="utf-8",
    )
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("(Rev 17)\n", encoding="utf-8")
    rc = cli.main([str(f)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "hint-presence-check" in out or "HINT:" in out


def test_learnings_empty_body_hints(tmp_path):
    f = tmp_path / "learnings" / "x" / "note.md"
    f.parent.mkdir(parents=True)
    f.write_text("---\ngenre: learnings\n---\n\nprose only\n", encoding="utf-8")
    status, findings = lint_file(f)
    assert status == "PASS"
    assert any(f.code == "hint-learnings-empty" for f in findings)


def test_learnings_entry_missing_ground_errors(tmp_path):
    f = tmp_path / "learnings" / "x" / "2026-08-08-x.md"
    f.parent.mkdir(parents=True)
    f.write_text(
        "---\ngenre: learnings\n---\n\n"
        "- date: 2026-08-08\n"
        "  stream: x\n"
        "  kind: craft\n"
        "  genre: learnings\n"
        "  lesson: Prefer local invariants.\n"
        "  ground: \n",
        encoding="utf-8",
    )
    status, findings = lint_file(f)
    assert status == "FAIL"
    assert any(f.code == "learnings-missing-field" for f in findings)


def test_reserve_sow_stub_exclusive(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("(Rev 17)\n", encoding="utf-8")
    chain = tmp_path / "projects" / "p" / "sow" / "speechbubble"
    chain.mkdir(parents=True)
    path, detail = reserve_sow_stub(tmp_path, "speechbubble", "motion diagnosis two mechanisms")
    assert path is not None
    assert path.exists()
    assert path.name.startswith("speechbubble-SOW-01-")
    assert "motion-diagnosis" in path.name
    # Second reserve gets next n
    path2, _ = reserve_sow_stub(tmp_path, "speechbubble", "other slug words here")
    assert path2 is not None
    assert path2.name.startswith("speechbubble-SOW-02-")
    assert path2 != path


def test_reserve_ruling_stub_exclusive(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("(Rev 17)\n", encoding="utf-8")
    home = tmp_path / "ruling"
    home.mkdir()
    # Seed an org-scope ruling so next id is 201 if band not landed, or 1+
    (home / "RULING-001-seed.md").write_text(
        "---\nruling: 1\nscope: org\nstatus: ACTIVE\nlanding_commit: self\ngenre: ruling\n---\n\n",
        encoding="utf-8",
    )
    path, detail = reserve_ruling_stub(tmp_path, "ghost reciprocity check")
    assert path is not None
    assert path.exists()
    assert path.name.startswith("RULING-")
    assert "ghost-reciprocity" in path.name
    text = path.read_text(encoding="utf-8")
    assert "landing_commit: self" in text
    assert "genre: ruling" in text


def test_cli_mint_words_reserves_sow(tmp_path, capsys):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("(Rev 17)\n", encoding="utf-8")
    (tmp_path / "projects" / "p" / "sow" / "ds-6").mkdir(parents=True)
    rc = cli.main(
        [
            "--mint",
            "sow",
            "ds-6",
            "--words",
            "freshen gate green",
            str(tmp_path),
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "RESERVED" in out
    stubs = list((tmp_path / "projects" / "p" / "sow" / "ds-6").glob("ds-6-SOW-*.md"))
    assert len(stubs) == 1
