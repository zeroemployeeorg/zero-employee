"""RULING-216 s5: --restaufwand/--kosten/--soll-ist/--progress/--locate fell back to the
LITERAL STRING "." when no positional was given (not None, unlike --board/--inbox), and
_discover_root(".") returns Path(".") unconditionally without walking up to find
claude-md/CLAUDE.md - so these five verbs FAILED OPEN from any wrong cwd regardless of
what a caller passed. Removing a hook's own "." argument (cc-session-start.sh) fixed
NOTHING on its own; the fallback was baked into cli.py itself. Proven wrong by --triage,
the one sibling verb that was ALREADY correct with no positional.
"""

import pytest
from zero_employee import cli


@pytest.fixture
def not_a_corpus(tmp_path):
    """A directory that is NOT a sows repo and has no claude-md/CLAUDE.md anywhere in its
    ancestry within the test sandbox - the exact "wrong cwd" shape RULING-216 measured
    from /tmp."""
    d = tmp_path / "nowhere"
    d.mkdir()
    return d


def _run_from(cwd, args, monkeypatch):
    monkeypatch.chdir(cwd)
    return cli.main(args)


def test_restaufwand_no_arg_fails_closed(not_a_corpus, monkeypatch, capsys):
    rc = _run_from(not_a_corpus, ["--restaufwand"], monkeypatch)
    out = capsys.readouterr()
    assert rc == 2
    assert "run from inside the corpus" in (out.out + out.err)
    assert "0 of 0" not in out.out  # the OLD fail-open shape must not reappear


def test_progress_no_arg_fails_closed(not_a_corpus, monkeypatch, capsys):
    rc = _run_from(not_a_corpus, ["--progress"], monkeypatch)
    out = capsys.readouterr()
    assert rc == 2
    assert "0 stream(s)" not in out.out


def test_kosten_no_arg_fails_closed(not_a_corpus, monkeypatch, capsys):
    rc = _run_from(not_a_corpus, ["--kosten"], monkeypatch)
    assert rc == 2


def test_soll_ist_no_arg_fails_closed(not_a_corpus, monkeypatch, capsys):
    rc = _run_from(not_a_corpus, ["--soll-ist"], monkeypatch)
    assert rc == 2


def test_locate_no_path_arg_fails_closed(not_a_corpus, monkeypatch, capsys):
    rc = _run_from(not_a_corpus, ["--locate", "some-stream"], monkeypatch)
    assert rc == 2


def test_the_dot_form_still_works_explicitly_asking_for_cwd(tmp_path, monkeypatch, capsys):
    """Passing "." explicitly is still a legal, EXPLICIT choice - only the SILENT default
    changed. From a real corpus root, `--restaufwand .` must still work."""
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    rc = _run_from(tmp_path, ["--restaufwand", "."], monkeypatch)
    out = capsys.readouterr()
    assert rc == 0
    assert "RESTAUFWAND" in out.out


def test_triage_no_arg_was_already_correct_unchanged_by_this_fix(not_a_corpus, monkeypatch, capsys):
    rc = _run_from(not_a_corpus, ["--triage"], monkeypatch)
    out = capsys.readouterr()
    assert rc == 2
    assert "couldn't find a corpus" in out.err
