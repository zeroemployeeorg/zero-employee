"""Intake capture and grounded promote."""

from __future__ import annotations

import io
import json
import pathlib

from zero_employee import cli
from zero_employee.core import extract_frontmatter, intake_open_rows, lint_file, parse_current_rev, find_canonical_claude_md
from zero_employee.intake_authoring import (
    create_intake,
    create_intake_from_spec,
    doctor_intake,
    build_mission,
    promote_intake,
    propose_intake,
    status_counts,
    git_head,
)
from zero_employee.scaffold import init_corpus
from zero_employee.schemas.intake import normalize_intake_status


def _corpus(tmp_path: pathlib.Path) -> pathlib.Path:
    root = tmp_path / "org"
    init_corpus(root)
    return root


def test_intake_new_from_title(tmp_path):
    root = _corpus(tmp_path)
    result, err = create_intake(root, title="Migrate local doctrine safely")
    assert err == ""
    assert result is not None
    path = root / result.path
    assert path.is_file()
    fm = extract_frontmatter(path.read_text(encoding="utf-8"))
    assert fm["genre"] == "intake"
    assert fm["status"] == "OPEN"
    assert fm["id"] == fm["intake"]
    assert "WHAT:" in path.read_text(encoding="utf-8")
    assert "Migrate local doctrine safely" in path.read_text(encoding="utf-8")


def test_intake_new_from_spec(tmp_path):
    root = _corpus(tmp_path)
    result, err = create_intake_from_spec(
        root,
        {
            "title": "Complete the 17-week course",
            "what": "Every week has a complete body.",
            "why": "Site publishes from corpus.",
            "done_when": "W01-W17 each contain six units.",
            "not_this": ["Not videos", "Not rewrite"],
            "context": ["theory/nebius_week_01.md is different"],
            "project_hint": "profrod",
            "stream_hint": "course-production",
        },
    )
    assert err == ""
    text = (root / result.path).read_text(encoding="utf-8")
    fm = extract_frontmatter(text)
    assert fm["project_hint"] == "profrod"
    assert "DONE WHEN:" in text
    assert "Not videos" in text


def test_intake_new_stdin_cli(tmp_path, monkeypatch, capsys):
    root = _corpus(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO("Raw prose about needing a doctrine migration path.\n"),
    )
    rc = cli.main(["intake", "new", "--stdin", "--title", "Doctrine migration"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Created intake/" in out
    files = list((root / "intake").glob("*.md"))
    files = [f for f in files if f.name != "README.md"]
    assert len(files) == 1
    assert "Raw prose" in files[0].read_text(encoding="utf-8")


def test_intake_positional_title_cli(tmp_path, monkeypatch, capsys):
    root = _corpus(tmp_path)
    monkeypatch.chdir(root)
    rc = cli.main(["intake", "Need a way to migrate doctrine"])
    assert rc == 0
    assert "Created intake/" in capsys.readouterr().out


def test_doctor_what_missing_fails(tmp_path):
    root = _corpus(tmp_path)
    d = root / "intake"
    d.mkdir(exist_ok=True)
    path = d / "2026-08-09-bad.md"
    path.write_text(
        "---\ngenre: intake\nid: 2026-08-09-bad\nintake: 2026-08-09-bad\n"
        "created: 2026-08-09\nupdated: 2026-08-09\nstatus: OPEN\n---\n\nWHY: only why\n",
        encoding="utf-8",
    )
    ready, errors, advice = doctor_intake(path, root=root)
    assert not ready
    assert any("WHAT" in e for e in errors)


def test_doctor_soft_advice_done_when(tmp_path):
    root = _corpus(tmp_path)
    result, _ = create_intake(root, title="Something", what="Do the thing")
    path = root / result.path
    ready, errors, advice = doctor_intake(path, root=root)
    assert ready
    assert not errors
    assert any("DONE WHEN" in a for a in advice)


def test_status_counts_and_open(tmp_path, monkeypatch, capsys):
    root = _corpus(tmp_path)
    create_intake(root, title="Idea one")
    create_intake(root, title="Idea two")
    counts = status_counts(root)
    assert counts["OPEN"] == 2
    monkeypatch.chdir(root)
    rc = cli.main(["intake", "open"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Idea" in out or "idea" in out.lower() or "OPEN" in out


def test_legacy_chartered_not_open(tmp_path):
    root = _corpus(tmp_path)
    d = root / "intake"
    d.mkdir(exist_ok=True)
    (d / "old.md").write_text(
        "---\nintake: old-one\nproject: governance-layer\ngenre: intake\n"
        "created: 2026-08-01\nstatus: CHARTERED\n---\n\nWHAT: x\n",
        encoding="utf-8",
    )
    assert normalize_intake_status("CHARTERED") == "PROMOTED"
    assert intake_open_rows(root) == []


def test_lint_grades_intake_not_genre_unknown(tmp_path):
    root = _corpus(tmp_path)
    result, _ = create_intake(root, title="Lint me", what="A concrete what", done_when="tests pass")
    path = root / result.path
    status, findings = lint_file(path, root=root)
    assert status == "PASS"
    assert not any(f.code == "genre-unknown" for f in findings)


def test_mission_json_keys(tmp_path, monkeypatch, capsys):
    root = _corpus(tmp_path)
    result, _ = create_intake(root, title="Mission test", what="Investigate scaffold")
    path = root / result.path
    mission = build_mission(root, path)
    assert mission["protocol_version"] == 1
    assert mission["action"] == "investigate_then_promote"
    assert "submission" in mission
    assert "schema" in mission["submission"]
    monkeypatch.chdir(root)
    rc = cli.main(["intake", "mission", result.path, "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["protocol_version"] == 1


def _evidence_file(root: pathlib.Path) -> pathlib.Path:
    src = root / "src_probe"
    src.mkdir()
    f = src / "example.py"
    f.write_text(
        "\n".join(
            [
                "# line 1",
                "def hello():",
                "    return 42",
                "# line 4",
                "# line 5",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return f


def test_propose_rejects_bad_path(tmp_path):
    root = _corpus(tmp_path)
    result, _ = create_intake(root, title="Propose bad", what="Fix something")
    path = root / result.path
    head = git_head(root) or "no-git"
    _, _, err = propose_intake(
        root,
        path,
        {
            "repo_head": head,
            "observations": [
                {
                    "fact": "missing file",
                    "evidence": {"path": "does/not/exist.py", "line_start": 1, "line_end": 2},
                }
            ],
            "implementation": {
                "problem": "p",
                "invariant": "i",
                "approach": ["a"],
                "done_when": [{"type": "inspection", "criterion": "c"}],
            },
        },
    )
    assert "missing" in err.lower() or "evidence" in err.lower()


def test_propose_rejects_bad_line_range(tmp_path):
    root = _corpus(tmp_path)
    ev = _evidence_file(root)
    result, _ = create_intake(root, title="Propose range", what="Fix something")
    path = root / result.path
    head = git_head(root) or "no-git"
    rel = str(ev.relative_to(root))
    _, _, err = propose_intake(
        root,
        path,
        {
            "repo_head": head,
            "observations": [
                {
                    "fact": "bad range",
                    "evidence": {"path": rel, "line_start": 1, "line_end": 99},
                }
            ],
            "implementation": {
                "problem": "p",
                "invariant": "i",
                "approach": ["a"],
                "done_when": [{"type": "inspection", "criterion": "c"}],
            },
        },
    )
    assert "line range" in err.lower() or "bounds" in err.lower()


def test_propose_rejects_stale_head(tmp_path):
    root = _corpus(tmp_path)
    # Need a real git repo for stale head check
    import subprocess

    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True, capture_output=True)
    (root / "seed.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "seed.txt"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=root, check=True, capture_output=True)
    ev = _evidence_file(root)
    result, _ = create_intake(root, title="Stale head", what="Fix something")
    path = root / result.path
    rel = str(ev.relative_to(root))
    _, _, err = propose_intake(
        root,
        path,
        {
            "repo_head": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            "observations": [
                {
                    "fact": "hello exists",
                    "evidence": {"path": rel, "line_start": 2, "line_end": 3},
                }
            ],
            "implementation": {
                "problem": "p",
                "invariant": "i",
                "approach": ["a"],
                "done_when": [{"type": "inspection", "criterion": "c"}],
            },
        },
    )
    assert "stale" in err.lower()


def test_promote_without_proposal_fails(tmp_path):
    root = _corpus(tmp_path)
    result, _ = create_intake(
        root,
        title="No proposal",
        what="Do work",
        project_hint="p",
        stream_hint="s",
    )
    path = root / result.path
    out, err = promote_intake(root, path, project="p", stream="s")
    assert out is None
    assert "proposal" in err.lower()


def test_promote_green_path(tmp_path):
    root = _corpus(tmp_path)
    ev = _evidence_file(root)
    result, _ = create_intake(
        root,
        title="Grounded promote",
        what="Unify SOW write paths",
        done_when="tests pass",
        project_hint="demo",
        stream_hint="ergonomics",
    )
    path = root / result.path
    head = git_head(root) or "no-git"
    rel = str(ev.relative_to(root))
    prop_path, proposal, err = propose_intake(
        root,
        path,
        {
            "summary": "three write paths",
            "repo_head": head,
            "observations": [
                {
                    "fact": "hello helper exists",
                    "evidence": {"path": rel, "line_start": 2, "line_end": 3},
                }
            ],
            "interpretations": [{"claim": "reuse hello", "based_on": [0]}],
            "implementation": {
                "problem": "divergent writers",
                "invariant": "one transactional create path",
                "approach": ["extract shared helper", "route CLI through it"],
                "files_expected_to_change": ["src/zero_employee/cli.py"],
                "non_goals": ["Do not let LLM emit YAML"],
                "done_when": [
                    {"type": "command", "command": "pytest -q", "expect": "exit 0"},
                    {"type": "inspection", "criterion": "intake marked PROMOTED"},
                ],
            },
            "destination": {
                "project": "demo",
                "stream": "ergonomics",
                "title": "Unify SOW write paths",
            },
        },
    )
    assert err == ""
    assert prop_path is not None
    assert proposal is not None

    out, err = promote_intake(root, path)
    assert err == ""
    assert out is not None
    sow = root / out.sow_path
    assert sow.is_file()
    canon = find_canonical_claude_md(root)
    rev = parse_current_rev(canon.read_text(encoding="utf-8"))
    st, findings = lint_file(sow, current_rev=rev or 17, root=root, commit_mode=True)
    assert st == "PASS", findings
    fm = extract_frontmatter(path.read_text(encoding="utf-8"))
    assert normalize_intake_status(fm["status"]) == "PROMOTED"
    assert fm["promoted_to"] == out.sow_path


def test_promote_with_spec_cli(tmp_path, monkeypatch, capsys):
    root = _corpus(tmp_path)
    ev = _evidence_file(root)
    result, _ = create_intake(root, title="CLI promote", what="Ship intake promote")
    intake_rel = result.path
    head = git_head(root) or "no-git"
    rel = str(ev.relative_to(root))
    spec = {
        "repo_head": head,
        "observations": [
            {
                "fact": "probe file",
                "evidence": {"path": rel, "line_start": 1, "line_end": 2},
            }
        ],
        "implementation": {
            "problem": "p",
            "invariant": "i",
            "approach": ["a"],
            "done_when": [{"type": "inspection", "criterion": "c"}],
        },
        "destination": {"project": "demo", "stream": "cli-stream", "title": "CLI promote"},
    }
    spec_path = root / "proposal.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    monkeypatch.chdir(root)
    rc = cli.main(
        [
            "intake",
            "promote",
            intake_rel,
            "--spec",
            str(spec_path),
            "--json",
        ]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["n"] >= 1
    assert "PROMOTED" in (root / intake_rel).read_text(encoding="utf-8")


def test_init_creates_intake_dir(tmp_path):
    root = tmp_path / "fresh"
    init_corpus(root)
    assert (root / "intake").is_dir()
    assert (root / "intake" / "README.md").is_file()
    gi = (root / ".gitignore").read_text(encoding="utf-8")
    assert ".zeo/" in gi
