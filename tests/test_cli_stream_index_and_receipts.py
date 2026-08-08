"""The CLI PATH for --stream-index, and the corpus-level checks wired into ordinary
lint runs (check_binds_corpus, check_ruling_receipts). Same lesson as
test_cli_promote_resync.py: a flag dispatched with its imports missing raises NameError
on first real use, and a test that only calls core functions directly never catches it.
"""

import subprocess
import pytest
from zero_employee import cli


def _git(d, *a):
    subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n")
    d = tmp_path / "p" / "sow" / "s"
    d.mkdir(parents=True)
    (d / "f.md").write_text(
        "---\nsow: s\nn: 1\nstatus: PROGRESS\ndone_when: x\nrestaufwand: 1\n---\n\nbody\n",
        encoding="utf-8",
    )
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "seed")
    return tmp_path


def test_stream_index_via_main_does_not_NameError_and_writes_the_file(repo, capsys):
    rc = cli.main(["--stream-index", str(repo)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "stream-index.md written" in out
    target = repo / "stream-index.md"
    assert target.is_file()
    text = target.read_text(encoding="utf-8")
    assert "STREAM-INDEX:AUTO" in text and "`s`" in text


def test_stream_index_is_regenerated_whole_a_hand_edit_does_not_survive(repo, capsys):
    cli.main(["--stream-index", str(repo)])
    capsys.readouterr()
    target = repo / "stream-index.md"
    target.write_text("hand-edited garbage\n", encoding="utf-8")
    cli.main(["--stream-index", str(repo)])
    capsys.readouterr()
    assert "hand-edited garbage" not in target.read_text(encoding="utf-8")


def test_a_ruling_with_unresolved_binds_fails_at_commit_check(repo, capsys):
    rd = repo / "ruling"
    rd.mkdir()
    (rd / "RULING-900-x.md").write_text(
        '---\nruling: "900"\ngenre: ruling\nstatus: ACTIVE\nlanding_commit: self\n'
        "binds: [episode-layout]\n---\n\nbody\n",
        encoding="utf-8",
    )
    rc = cli.main(["--commit-check", str(rd / "RULING-900-x.md")])
    out = capsys.readouterr().out
    assert rc == 1
    assert "binds-unresolved" in out


def test_a_ruling_naming_an_asker_with_no_receipt_warns_in_ordinary_lint(repo, capsys):
    rd = repo / "ruling"
    rd.mkdir()
    (rd / "RULING-901-x.md").write_text(
        '---\nruling: "901"\ngenre: ruling\nstatus: ACTIVE\nlanding_commit: self\nrequested_by: s#1\n---\n\nbody\n',
        encoding="utf-8",
    )
    rc = cli.main([str(repo)])
    out = capsys.readouterr().out
    assert "resolved-by-missing-citation" in out


def test_missing_citation_is_visible_when_linting_ONLY_the_ruling_file(repo, capsys):
    """MEASURED against the real org corpus: `--commit-check` on a single ruling FILE
    (the real pre-commit-hook shape) silently dropped this finding, because files_fm held
    only the one ruling and the asker's frontmatter lives in a different file entirely.
    Fixed by resolving the asker corpus-wide (build_stem_index) rather than from files_fm."""
    rd = repo / "ruling"
    rd.mkdir()
    f = rd / "RULING-904-x.md"
    f.write_text(
        '---\nruling: "904"\ngenre: ruling\nstatus: ACTIVE\nlanding_commit: self\nrequested_by: s#1\n---\n\nbody\n',
        encoding="utf-8",
    )
    rc = cli.main(["--commit-check", str(f)])
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "resolved-by-missing-citation" in out


def test_the_same_case_is_an_error_at_commit_check(repo, capsys):
    rd = repo / "ruling"
    rd.mkdir()
    (rd / "RULING-902-x.md").write_text(
        '---\nruling: "902"\ngenre: ruling\nstatus: ACTIVE\nlanding_commit: self\nrequested_by: s#1\n---\n\nbody\n',
        encoding="utf-8",
    )
    rc = cli.main(["--commit-check", str(rd / "RULING-902-x.md")])
    out = capsys.readouterr().out
    assert rc == 1
    assert "[ERROR] [resolved-by-missing-citation]" in out or "resolved-by-missing-citation" in out


def test_a_ruling_naming_an_asker_that_DOES_cite_back_is_clean(repo, capsys):
    (repo / "p" / "sow" / "s" / "f.md").write_text(
        '---\nsow: s\nn: 1\nproject: p\nstatus: RULING-REQUESTED\nresolved_by: "ruling: RULING-903"\n'
        "done_when: x\nrestaufwand: 1\n---\n\nbody\n",
        encoding="utf-8",
    )
    rd = repo / "ruling"
    rd.mkdir()
    (rd / "RULING-903-x.md").write_text(
        '---\nruling: "903"\ngenre: ruling\nstatus: ACTIVE\nlanding_commit: self\nrequested_by: s#1\n---\n\nbody\n',
        encoding="utf-8",
    )
    rc = cli.main([str(repo)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "resolved-by-missing-citation" not in out


def test_a_charter_with_the_fields_lints_PASS_not_skip(repo, capsys):
    d = repo / "p" / "sow" / "c"
    d.mkdir(parents=True)
    (d / "CHARTER-01.md").write_text(
        "---\ngenre: charter\ncharter: C-01\nsow: c\nstatus: ACTIVE\nlanding_commit: self\n"
        "done_when: x\nrestaufwand: 1\n---\n\nbody\n",
        encoding="utf-8",
    )
    rc = cli.main([str(d / "CHARTER-01.md")])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "skipped (deliberate)" not in out


def test_a_charter_missing_the_fields_warns_not_silently_skips(repo, capsys):
    d = repo / "p" / "sow" / "c2"
    d.mkdir(parents=True)
    (d / "CHARTER-02.md").write_text(
        "---\ngenre: charter\ncharter: C-02\nsow: c2\nstatus: ACTIVE\nlanding_commit: self\n---\n\nbody\n",
        encoding="utf-8",
    )
    rc = cli.main([str(d / "CHARTER-02.md")])
    out = capsys.readouterr().out
    assert "working-no-done-when" in out and "working-no-restaufwand" in out
