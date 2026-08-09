"""Tests for the --migrate generator against the typed Claim/Ground rewrite.

Prove behavior: the model only owns status+lifecycle; ground/blockers/atomic write
and the migrate_check gate decide what lands on disk.
"""

from __future__ import annotations

import datetime
import json
import pathlib
import stat
import subprocess

import pytest

from zero_employee import migrate
from zero_employee.core import _MIGRATE_REQUIRED, _STATUS_ENUM, migrate_check, project_of


def _claim(status: str = "STALE", lifecycle: str = "RECON") -> str:
    return json.dumps({"status": status, "lifecycle": lifecycle})


def _class_a(tmp_path, body="pre-schema body\nline two\n"):
    d = tmp_path / "governance-layer" / "sow" / "ds-6"
    d.mkdir(parents=True)
    f = d / "ds-6-SOW-07-legacy.md"
    f.write_text(body, encoding="utf-8")
    return f


def _git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
    )


def _init_repo(repo):
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")


# ── enum / claim validation ───────────────────────────────────────────


def test_working_and_resting_exactly_partition_the_core_enum():
    assert migrate.STATUS_WORKING | migrate.STATUS_RESTING == _STATUS_ENUM
    assert not (migrate.STATUS_WORKING & migrate.STATUS_RESTING)


@pytest.mark.parametrize("status", sorted(migrate.STATUS_WORKING))
def test_every_working_status_is_rejected_by_validate_claim(status):
    claim, err = migrate.validate_claim(_claim(status=status, lifecycle="RECON"))
    assert claim is None
    assert err is not None and err.startswith("CLAIM:")
    assert "at-rest" in err


@pytest.mark.parametrize("status", sorted(migrate.STATUS_RESTING))
def test_every_resting_status_with_lifecycle_validates(status):
    claim, err = migrate.validate_claim(_claim(status=status, lifecycle="RECON"))
    assert err is None
    assert claim is not None
    assert claim.status == status
    assert claim.lifecycle == "RECON"


@pytest.mark.parametrize("lifecycle", migrate.LIFECYCLES)
def test_every_lifecycle_validates(lifecycle):
    claim, err = migrate.validate_claim(_claim(lifecycle=lifecycle))
    assert err is None and claim is not None
    assert claim.lifecycle == lifecycle


def test_validate_claim_normalizes_case_and_whitespace():
    claim, err = migrate.validate_claim('{"status": "  stale ", "lifecycle": " design-memo "}')
    assert err is None and claim is not None
    assert claim.status == "STALE"
    assert claim.lifecycle == "DESIGN-MEMO"


def test_validate_claim_rejects_extra_keys_and_missing_lifecycle():
    _, extra = migrate.validate_claim('{"status":"STALE","lifecycle":"RECON","project":"nope"}')
    assert extra is not None and "unexpected key" in extra

    _, missing = migrate.validate_claim('{"status":"STALE"}')
    assert missing is not None and missing.startswith("CLAIM:")


def test_validate_claim_extract_failure_is_prefixed():
    claim, err = migrate.validate_claim("I think this document is probably done.")
    assert claim is None
    assert err is not None and err.startswith("EXTRACT:")


# ── extract_claim ─────────────────────────────────────────────────────


def test_extract_claim_prefers_top_level_json():
    assert migrate.extract_claim('{"status":"HELD","lifecycle":"DESIGN-MEMO"}') == {
        "status": "HELD",
        "lifecycle": "DESIGN-MEMO",
    }


def test_extract_claim_takes_last_json_object_in_reasoning():
    raw = (
        'Considering {"status":"DRAFT","lifecycle":"RECON"} first.\n'
        "Final answer:\n"
        '{"status":"STALE","lifecycle":"DECISION-RECORD"}'
    )
    assert migrate.extract_claim(raw) == {
        "status": "STALE",
        "lifecycle": "DECISION-RECORD",
    }


def test_extract_claim_yaml_keyline_fallback_and_ansi_think_strip():
    raw = "<think>ignore me</think>\nstatus: STALE\x1b[9D\x1b[K\nlifecycle: RECON\n"
    assert migrate.extract_claim(raw) == {"status": "STALE", "lifecycle": "RECON"}


def test_extract_claim_last_keyline_wins():
    raw = "status: DRAFT\nstatus: PROGRESS\nstatus: STALE\nlifecycle: RECON\n"
    assert migrate.extract_claim(raw) == {"status": "STALE", "lifecycle": "RECON"}


def test_extract_claim_pure_prose_yields_empty_dict():
    assert migrate.extract_claim("I think this document is probably done.") == {}


# ── ground derivation ─────────────────────────────────────────────────


def test_stream_and_project_derive_from_path():
    p = pathlib.Path("governance-layer/sow/ds-6/ds-6-SOW-01-reception.md")
    assert migrate.stream_of(p) == "ds-6"
    assert project_of(p) == "governance-layer"


def test_loose_corpus_doc_gets_no_invented_stream():
    p = pathlib.Path("quackverse/sow/QuackVerse-Execution-Kanban.md")
    assert migrate.stream_of(p) is None


def test_n_comes_from_the_filename_or_is_honestly_absent():
    assert migrate.n_of(pathlib.Path("ds-6-SOW-01-reception-and-migrate-design.md")) == 1
    assert migrate.n_of(pathlib.Path("SOW-TrackA-core-fs-completion-Rev1.md")) is None


def test_ground_blockers_name_missing_n_and_project():
    blockers = migrate.ground_blockers(
        migrate.Ground(
            sow=None,
            project=None,
            n=None,
            created=None,
            updated=None,
        )
    )
    assert any(b.startswith("n:") for b in blockers)
    assert any(b.startswith("project:") for b in blockers)


def test_ungrounded_identity_escalates_without_calling_the_model(tmp_path):
    f = tmp_path / "loose.md"
    f.write_text("pre-schema body\n", encoding="utf-8")
    called = []
    out, detail = migrate.migrate_file(
        f,
        tmp_path,
        tmp_path,
        lambda p, t: called.append(1) or _claim(),
    )
    assert out == "ESCALATE"
    assert "ungrounded identity" in detail
    assert not called


def test_git_dates_follow_a_rename_so_birth_is_not_the_restructure(tmp_path):
    repo = tmp_path / "r"
    _init_repo(repo)
    (repo / "old.md").write_text("pre-schema body\n", encoding="utf-8")
    _git(repo, "add", "old.md")
    _git(repo, "commit", "-q", "-m", "birth", "--date=2020-01-02T00:00:00")
    _git(repo, "mv", "old.md", "new.md")
    _git(repo, "commit", "-q", "-m", "restructure rename", "--date=2021-03-04T00:00:00")

    created, updated = migrate.git_dates(repo / "new.md", repo)
    assert created == datetime.date(2020, 1, 2)
    assert updated == datetime.date(2020, 1, 2)


def test_a_pure_rename_never_becomes_the_updated_date(tmp_path):
    repo = tmp_path / "r"
    _init_repo(repo)
    (repo / "old.md").write_text("v1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "birth", "--date=2020-01-02T00:00:00")
    (repo / "old.md").write_text("v2 real edit\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "edit", "--date=2021-03-04T00:00:00")
    _git(repo, "mv", "old.md", "new.md")
    _git(repo, "commit", "-q", "-m", "restructure rename", "--date=2022-05-06T00:00:00")

    created, updated = migrate.git_dates(repo / "new.md", repo)
    assert created == datetime.date(2020, 1, 2)
    assert updated == datetime.date(2021, 3, 4)


def test_git_dates_are_silent_rather_than_wrong_off_history(tmp_path):
    repo = tmp_path / "r2"
    _init_repo(repo)
    assert migrate.git_dates(repo / "nothere.md", repo) == (None, None)


def test_body_window_keeps_short_bodies_and_bounds_long_ones():
    short = "a\nb\n"
    assert migrate._body_window(short) == short

    long = "".join(f"line {i}\n" for i in range(200))
    windowed = migrate._body_window(long, head=80, tail=20)
    assert "lines omitted" in windowed
    assert windowed.startswith("line 0\n")
    assert windowed.splitlines()[-1] == "line 199"


# ── assemble / render / parse_verify / gate contract ───────────────────


def test_assemble_and_render_round_trip_passes_migrate_check(tmp_path):
    """MigratedFrontmatter must stay green under migrate_check's required set."""
    ground = migrate.Ground(
        sow="ds-6",
        project="governance-layer",
        n=7,
        created=datetime.date(2020, 1, 2),
        updated=datetime.date(2021, 3, 4),
    )
    claim = migrate.Claim.model_validate({"status": "STALE", "lifecycle": "DECISION-RECORD"})
    fm = migrate.assemble_frontmatter(
        ground,
        claim,
        tag="gemma4:latest",
        version="0.11.0",
        today=datetime.date(2026, 7, 23),
    )
    body = b"pre-schema body\n"
    candidate = migrate.render_candidate(fm, body)

    assert migrate.parse_verify(candidate) is None
    assert candidate.endswith(body)

    dumped = fm.model_dump(mode="json")
    for key in _MIGRATE_REQUIRED:
        assert dumped.get(key) not in (None, ""), key

    dest = tmp_path / "governance-layer" / "sow" / "ds-6" / "ds-6-SOW-07-legacy.md"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(candidate)
    status, feedback = migrate_check(dest)
    assert status == "PASS", feedback


def test_assemble_writes_unknown_for_absent_ground():
    ground = migrate.Ground(
        sow=None,
        project="governance-layer",
        n=7,
        created=None,
        updated=None,
    )
    claim = migrate.Claim.model_validate({"status": "STALE", "lifecycle": "RECON"})
    fm = migrate.assemble_frontmatter(
        ground,
        claim,
        tag="t",
        version="1.0.0",
        today=datetime.date(2026, 1, 1),
    )
    assert fm.sow == migrate.UNKNOWN
    assert fm.created == migrate.UNKNOWN
    assert fm.updated == migrate.UNKNOWN
    assert fm.schema_rev == 17
    assert "zeo 1.0.0" in fm.migrated_by


# ── atomic_replace ────────────────────────────────────────────────────


def test_atomic_replace_preserves_mode_and_refuses_concurrent_change(tmp_path):
    path = tmp_path / "doc.md"
    original = b"original\n"
    path.write_bytes(original)
    path.chmod(0o640)

    migrate.atomic_replace(path, expected=original, replacement=b"replacement\n")
    assert path.read_bytes() == b"replacement\n"
    assert stat.S_IMODE(path.stat().st_mode) == 0o640
    assert not list(tmp_path.glob(".*.migrate"))

    with pytest.raises(RuntimeError, match="source changed"):
        migrate.atomic_replace(
            path,
            expected=original,
            replacement=b"should-not-land\n",
        )
    assert path.read_bytes() == b"replacement\n"


# ── migrate_file loop ─────────────────────────────────────────────────


def test_already_schema_is_a_noop_v1_is_class_a_only(tmp_path):
    f = _class_a(tmp_path, "---\nsow: x\n---\n\nbody\n")
    called = []
    out, _ = migrate.migrate_file(
        f,
        tmp_path,
        tmp_path,
        lambda p, t: called.append(1) or _claim(),
    )
    assert out == "ALREADY-SCHEMA"
    assert not called


def test_malformed_frontmatter_escalates_without_model(tmp_path):
    f = _class_a(tmp_path, "---\n: not yaml\n---\n\nbody\n")
    called = []
    out, detail = migrate.migrate_file(
        f,
        tmp_path,
        tmp_path,
        lambda p, t: called.append(1) or _claim(),
    )
    assert out == "ESCALATE"
    assert "malformed" in detail
    assert not called


def test_non_utf8_source_escalates_without_model(tmp_path):
    f = _class_a(tmp_path)
    f.write_bytes(b"\xff\xfe pre-schema\n")
    called = []
    out, detail = migrate.migrate_file(
        f,
        tmp_path,
        tmp_path,
        lambda p, t: called.append(1) or _claim(),
    )
    assert out == "ESCALATE"
    assert "UTF-8" in detail
    assert not called


def test_happy_path_writes_and_never_touches_the_body(tmp_path):
    body = "pre-schema body\nline two\n"
    f = _class_a(tmp_path, body)
    out, detail = migrate.migrate_file(
        f,
        tmp_path,
        tmp_path,
        lambda p, t: _claim("STALE", "DECISION-RECORD"),
        version="0.11.0",
        today="2026-07-23",
    )
    assert out == "MIGRATED", detail
    text = f.read_text(encoding="utf-8")
    assert text.endswith(body)
    assert "migrated_by: gemma4:latest · 2026-07-23 · zeo 0.11.0" in text
    assert "lifecycle: DECISION-RECORD" in text
    assert migrate.UNKNOWN in text


def test_write_false_reports_migrated_but_leaves_disk_untouched(tmp_path):
    f = _class_a(tmp_path)
    before = f.read_bytes()
    out, detail = migrate.migrate_file(
        f,
        tmp_path,
        tmp_path,
        lambda p, t: _claim(),
        write=False,
    )
    assert out == "MIGRATED", detail
    assert f.read_bytes() == before


def test_a_model_insisting_on_a_working_status_never_reaches_disk(tmp_path):
    f = _class_a(tmp_path)
    before = f.read_text(encoding="utf-8")
    seen = []

    def stubborn(prompt, tag):
        seen.append(prompt)
        return _claim("RULING-REQUESTED", "ESCALATION")

    out, detail = migrate.migrate_file(f, tmp_path, tmp_path, stubborn)
    assert out == "ESCALATE", detail
    assert f.read_text(encoding="utf-8") == before
    assert len(seen) == 5
    assert "CLAIM:" in seen[1]
    assert "at-rest" in seen[1]


def test_the_loop_recovers_when_the_model_corrects_itself(tmp_path):
    f = _class_a(tmp_path)
    answers = iter(
        [
            _claim("DRAFT", "RECON"),
            "```json\n" + _claim("STALE", "RECON") + "\n```\n",
        ]
    )
    out, detail = migrate.migrate_file(
        f,
        tmp_path,
        tmp_path,
        lambda p, t: next(answers),
    )
    assert out == "MIGRATED", detail
    assert "status: STALE" in f.read_text(encoding="utf-8")


def test_unparseable_model_output_is_refused_not_written(tmp_path):
    f = _class_a(tmp_path)
    before = f.read_text(encoding="utf-8")
    out, _ = migrate.migrate_file(
        f,
        tmp_path,
        tmp_path,
        lambda p, t: "status: [unclosed\n",
    )
    assert out == "ESCALATE"
    assert f.read_text(encoding="utf-8") == before


def test_model_exception_retries_with_model_feedback(tmp_path):
    f = _class_a(tmp_path)
    seen = []

    def flaky(prompt, tag):
        seen.append(prompt)
        if len(seen) == 1:
            raise RuntimeError("ollama down")
        return _claim()

    out, detail = migrate.migrate_file(f, tmp_path, tmp_path, flaky)
    assert out == "MIGRATED", detail
    assert "MODEL:" in seen[1]


def test_identical_gate_rejection_stops_early(tmp_path, monkeypatch):
    f = _class_a(tmp_path)
    before = f.read_text(encoding="utf-8")
    seen = []

    monkeypatch.setattr(
        migrate,
        "migrate_check",
        lambda path: ("FAIL", ["synthetic gate failure"]),
    )

    out, detail = migrate.migrate_file(
        f,
        tmp_path,
        tmp_path,
        lambda p, t: seen.append(p) or _claim(),
        cap=5,
    )
    assert out == "ESCALATE", detail
    assert f.read_text(encoding="utf-8") == before
    assert len(seen) == 3
    assert "GATE:" in detail


def test_path_outside_root_escalates(tmp_path):
    outside = tmp_path / "outside"
    root = tmp_path / "root"
    outside.mkdir()
    root.mkdir()
    d = outside / "governance-layer" / "sow" / "ds-6"
    d.mkdir(parents=True)
    f = d / "ds-6-SOW-07-legacy.md"
    f.write_text("pre-schema body\n", encoding="utf-8")

    out, detail = migrate.migrate_file(
        f,
        root,
        outside,
        lambda p, t: _claim(),
    )
    assert out == "ESCALATE"
    assert "outside migration root" in detail or "ungrounded identity" in detail


def test_no_candidate_file_is_left_behind(tmp_path):
    f = _class_a(tmp_path)
    migrate.migrate_file(f, tmp_path, tmp_path, lambda p, t: _claim())
    assert not list(f.parent.glob("*.migrate-candidate"))
    assert not list(f.parent.glob(".*.migrate"))


def test_the_gate_grades_the_real_filename_not_a_temp_name(tmp_path):
    f = _class_a(tmp_path)
    out, detail = migrate.migrate_file(
        f,
        tmp_path,
        tmp_path,
        lambda p, t: _claim(),
    )
    assert out == "MIGRATED", detail
    assert all(x.name.endswith(".md") for x in f.parent.iterdir())


def test_the_model_reads_a_bounded_window_but_disk_body_is_whole(tmp_path):
    body = "".join(f"line {i}\n" for i in range(500))
    f = _class_a(tmp_path, body)
    seen = []
    out, detail = migrate.migrate_file(
        f,
        tmp_path,
        tmp_path,
        lambda p, t: seen.append(p) or _claim(),
    )
    assert out == "MIGRATED", detail
    assert "lines omitted" in seen[0]
    assert f.read_text(encoding="utf-8").endswith(body)


def test_a_talking_model_still_cannot_smuggle_a_working_status(tmp_path):
    f = _class_a(tmp_path)
    before = f.read_text(encoding="utf-8")
    out, _ = migrate.migrate_file(
        f,
        tmp_path,
        tmp_path,
        lambda p, t: "Thinking...\nlots of reasoning\nstatus: RULING-REQUESTED\nlifecycle: ESCALATION\n",
    )
    assert out == "ESCALATE"
    assert f.read_text(encoding="utf-8") == before


def test_ungrounded_fields_are_named_in_the_outcome(tmp_path):
    f = _class_a(tmp_path)
    out, detail = migrate.migrate_file(
        f,
        tmp_path,
        tmp_path,
        lambda p, t: _claim(),
    )
    assert out == "MIGRATED", detail
    assert "UNGROUNDED=" in detail
    assert "created" in detail and "updated" in detail


def test_a_fully_grounded_file_reports_no_concessions(tmp_path):
    d = tmp_path / "governance-layer" / "sow" / "ds-6"
    d.mkdir(parents=True)
    f = d / "ds-6-SOW-07-legacy.md"
    f.write_text("pre-schema body\n", encoding="utf-8")
    _init_repo(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "b", "--date=2020-01-02T00:00:00")

    out, detail = migrate.migrate_file(
        f,
        tmp_path,
        tmp_path,
        lambda p, t: _claim(),
    )
    assert out == "MIGRATED", detail
    assert "UNGROUNDED" not in detail, detail
    text = f.read_text(encoding="utf-8")
    assert "2020-01-02" in text
    assert "created:" in text


def test_concurrent_change_during_write_escalates(tmp_path, monkeypatch):
    f = _class_a(tmp_path)
    before = f.read_text(encoding="utf-8")

    def collide(path, *, expected, replacement):
        raise RuntimeError("source changed while migration was running")

    monkeypatch.setattr(migrate, "atomic_replace", collide)
    out, detail = migrate.migrate_file(
        f,
        tmp_path,
        tmp_path,
        lambda p, t: _claim(),
    )
    assert out == "ESCALATE"
    assert "CONCURRENT_CHANGE" in detail
    assert f.read_text(encoding="utf-8") == before


# ── CLI surface ───────────────────────────────────────────────────────


def test_cli_help_documents_the_migrate_flags(capsys):
    from zero_employee import cli

    cli.main(["--help"])
    out = capsys.readouterr().out
    assert "--migrate <file>" in out and "--model <tag>" in out
    assert "--migrate-check <file>" in out


def test_cli_migrate_dispatches_and_reports_already_schema(tmp_path, capsys):
    from zero_employee import cli

    f = tmp_path / "x.md"
    f.write_text("---\nsow: x\n---\n\nbody\n", encoding="utf-8")
    rc = cli.main(["--migrate", str(f)])
    out = capsys.readouterr().out
    assert rc == 0 and "ALREADY-SCHEMA" in out


def test_cli_migrate_missing_file_is_a_clean_error_not_a_traceback(capsys):
    from zero_employee import cli

    rc = cli.main(["--migrate", "/nope/nothere.md"])
    assert rc == 2 and "does not exist" in capsys.readouterr().out
