"""RULING-220: an instrument names the state it read.

`--inbox`/`--locate` are correctly zero-git (RULING-220 s1) - a seat must see its own
uncommitted work, and reading pathlib off the real working tree is why the tool beats a
spawn message. The defect the ruling names: "disk" is a CHECKOUT, a seat's question is
usually about the TRUNK, and the output never said which one it answered. MEASURED in
profrodai: from a branch, --inbox reports that branch's own tail - a seat proving "my
filing is visible to the fleet" that way has read work the fleet cannot see and called it
published. The fix is DISCLOSURE, not relocation (s2) - these tests prove the disclosure
is present, accurate, and does not change what gets read.
"""

import subprocess
import pytest
from zero_employee.core import git_ref_state, format_ref_disclosure, locate_stream
from zero_employee import cli


def _git(d, *a):
    return subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True, text=True)


def _corpus(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def repo_with_origin(tmp_path):
    """A real corpus with a bare 'origin' remote, main pushed - the shape profrodai
    actually has (a trunk the fleet reads, and a local checkout that may be ahead)."""
    bare = tmp_path / "bare-origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True, capture_output=True)
    work = tmp_path / "work"
    work.mkdir()
    r = _corpus(work)
    subprocess.run(["git", "init", "-q", str(work)], check=True, capture_output=True)
    _git(work, "config", "user.email", "t@t")
    _git(work, "config", "user.name", "t")
    _git(work, "checkout", "-q", "-b", "main")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "seed")
    _git(work, "remote", "add", "origin", str(bare))
    _git(work, "push", "-q", "-u", "origin", "main")
    return r


def test_git_ref_state_on_trunk_clean_and_contained(repo_with_origin):
    st = git_ref_state(repo_with_origin)
    assert st["ref"] == "main"
    assert st["dirty"] is False
    assert st["contained_in_trunk"] is True
    assert st["trunk"] == "main"


def test_git_ref_state_on_an_unpushed_branch_is_NOT_contained(repo_with_origin):
    """THE EXACT profrodai SHAPE: a branch with a real commit main/origin has never seen."""
    _git(repo_with_origin, "checkout", "-q", "-b", "feat/local-only")
    (repo_with_origin / "ruling").mkdir(exist_ok=True)
    (repo_with_origin / "ruling" / "RULING-999-x.md").write_text('---\nruling: "999"\n---\nb\n')
    _git(repo_with_origin, "add", "-A")
    _git(repo_with_origin, "commit", "-q", "-m", "local only, never pushed")
    st = git_ref_state(repo_with_origin)
    assert st["ref"] == "feat/local-only"
    assert st["contained_in_trunk"] is False


def test_git_ref_state_dirty_when_uncommitted_changes_present(repo_with_origin):
    (repo_with_origin / "claude-md" / "CLAUDE.md").write_text("# c\nedited\n")
    st = git_ref_state(repo_with_origin)
    assert st["dirty"] is True


def test_git_ref_state_no_origin_trunk_is_UNKNOWN_never_guessed(tmp_path):
    """A repo with no origin/<trunk> at all - contained_in_trunk must be None, never
    silently False (which would read as 'not visible to the fleet' when the truth is
    'there is no fleet remote to check against')."""
    r = _corpus(tmp_path)
    subprocess.run(["git", "init", "-q", str(r)], check=True, capture_output=True)
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "seed, no remote")
    st = git_ref_state(r)
    assert st["dirty"] is False
    assert st["contained_in_trunk"] is None


def test_git_ref_state_non_git_directory_is_fully_unknown(tmp_path):
    r = _corpus(tmp_path)
    st = git_ref_state(r)
    assert st["ref"] is None and st["sha"] is None and st["dirty"] is None
    assert st["contained_in_trunk"] is None


def test_format_ref_disclosure_flags_uncommitted_and_not_contained(repo_with_origin):
    _git(repo_with_origin, "checkout", "-q", "-b", "feat/x")
    # a real commit the trunk has never seen - a branch with ONLY uncommitted changes
    # and no new commit is still, correctly, contained in main (same HEAD sha).
    (repo_with_origin / "ruling").mkdir(exist_ok=True)
    (repo_with_origin / "ruling" / "RULING-998-x.md").write_text('---\nruling: "998"\n---\nb\n')
    _git(repo_with_origin, "add", "-A")
    _git(repo_with_origin, "commit", "-q", "-m", "not pushed")
    (repo_with_origin / "claude-md" / "CLAUDE.md").write_text("# c\nlocal edit\n")
    st = git_ref_state(repo_with_origin)
    line = format_ref_disclosure(st)
    assert "feat/x" in line
    assert "UNCOMMITTED" in line
    assert "NOT contained in origin/main" in line


def test_format_ref_disclosure_clean_and_contained_reads_positively(repo_with_origin):
    line = format_ref_disclosure(git_ref_state(repo_with_origin))
    assert "clean" in line
    assert "contained in origin/main" in line
    assert "NOT contained" not in line


def test_format_ref_disclosure_unknown_containment_says_so_not_a_guess(tmp_path):
    r = _corpus(tmp_path)
    subprocess.run(["git", "init", "-q", str(r)], check=True, capture_output=True)
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "seed")
    line = format_ref_disclosure(git_ref_state(r))
    assert "UNKNOWN" in line


# -- CLI level: the actual profrodai defect, reproduced and shown fixed --


def test_inbox_cli_discloses_the_unpushed_branch_it_actually_read(repo_with_origin, capsys):
    """THE MEASURED DEFECT, reproduced: --inbox on a local-only branch used to report
    that branch's tail with NOTHING saying it was not the fleet's view. Now it must."""
    _git(repo_with_origin, "checkout", "-q", "-b", "feat/my-work")
    sd = repo_with_origin / "demo-project" / "sow" / "demo-stream"
    sd.mkdir(parents=True)
    (sd / "DEMO-SOW-1-x.md").write_text(
        "---\nsow: demo-stream\nn: 1\nrev: a\nstatus: SHIPPED\n---\nb\n",
        encoding="utf-8",
    )
    _git(repo_with_origin, "add", "-A")
    _git(repo_with_origin, "commit", "-q", "-m", "not pushed")
    rc = cli.main(["--inbox", "demo-stream", str(repo_with_origin)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "feat/my-work" in out
    assert "NOT contained in origin/main" in out


def test_locate_cli_discloses_ref_before_the_answer(repo_with_origin, capsys):
    sd = repo_with_origin / "demo-project" / "sow" / "demo-stream"
    sd.mkdir(parents=True)
    (sd / "DEMO-SOW-1-x.md").write_text(
        "---\nsow: demo-stream\nn: 1\nrev: a\nstatus: SHIPPED\n---\nb\n",
        encoding="utf-8",
    )
    rc = cli.main(["--locate", "demo-stream", str(repo_with_origin)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ref: main" in out
    assert "contained in origin/main" in out
    # the disclosure line comes BEFORE the answer, not buried after it
    assert out.index("ref: main") < out.index("stream      demo-stream")


def test_locate_cli_disclosure_survives_the_ambiguous_early_return(repo_with_origin, capsys):
    """Even the AMBIGUOUS/NO-CHAIN-DIR early returns are state-dependent answers - the
    disclosure must print before those short-circuits, not only on the happy path."""
    (repo_with_origin / "projects" / "a" / "sow" / "dup").mkdir(parents=True)
    (repo_with_origin / "projects" / "b" / "sow" / "dup").mkdir(parents=True)
    (repo_with_origin / "projects" / "a" / "sow" / "dup" / "x.md").write_text(
        "---\nsow: dup\nn: 1\n---\nb\n", encoding="utf-8"
    )
    (repo_with_origin / "projects" / "b" / "sow" / "dup" / "y.md").write_text(
        "---\nsow: dup\nn: 1\n---\nb\n", encoding="utf-8"
    )
    rc = cli.main(["--locate", "dup", str(repo_with_origin)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "ref: main" in out
    assert "AMBIGUOUS" in out


def test_disclosure_never_changes_what_locate_stream_reads(repo_with_origin):
    """RULING-220 s2's hard boundary: disclosure, not relocation. Uncommitted work on a
    branch must still be VISIBLE to locate_stream - the fix adds a label, it does not
    switch the read to the trunk."""
    _git(repo_with_origin, "checkout", "-q", "-b", "feat/uncommitted-work")
    sd = repo_with_origin / "demo-project" / "sow" / "demo-stream"
    sd.mkdir(parents=True)
    (sd / "DEMO-SOW-1-x.md").write_text(
        "---\nsow: demo-stream\nn: 1\nrev: a\nstatus: SHIPPED\n---\nb\n",
        encoding="utf-8",
    )
    # deliberately UNCOMMITTED - never staged, never pushed
    L = locate_stream(repo_with_origin, "demo-stream")
    assert L["chain_dir"] is not None
    assert L["latest"]["n"] == 1


# -- RULING-220 s3 applied beyond s2's two named verbs: the generator verbs' header line
# names a COMMIT (more precise than a branch name) but not whether the tree was dirty at
# generation time - a gap the same size as the one s2 fixed, closed with the same helper. --


def test_board_cli_discloses_dirty_state_alongside_the_commit_it_stamped(repo_with_origin, capsys):
    (repo_with_origin / "claude-md" / "CLAUDE.md").write_text("# c\nuncommitted edit\n")
    rc = cli.main(["--board", str(repo_with_origin)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "UNCOMMITTED changes present" in out


def test_ruling_index_cli_discloses_dirty_state(repo_with_origin, capsys):
    (repo_with_origin / "claude-md" / "CLAUDE.md").write_text("# c\nuncommitted edit\n")
    rc = cli.main(["--ruling-index", str(repo_with_origin)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "UNCOMMITTED changes present" in out


def test_stream_index_cli_discloses_clean_and_contained_when_true(repo_with_origin, capsys):
    rc = cli.main(["--stream-index", str(repo_with_origin)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ref: main" in out
    assert "clean" in out
    assert "contained in origin/main" in out


def test_generator_verbs_do_not_contaminate_their_own_disclosure_with_their_own_write(repo_with_origin, capsys):
    """PAID (caught by the previous test, not asserted from a diff): all three generator
    verbs compute their disclosure AFTER writing their own output file to disk in the
    first draft of this fix - so a genuinely CLEAN corpus was reported as UNCOMMITTED on
    every single run, because the tool's own fresh STATE.md/ruling-index.md/stream-index.md
    is itself an untracked change the instant it lands. Fixed by capturing git_ref_state
    BEFORE the write. Runs all three back to back on a corpus with NO other uncommitted
    changes and asserts none of them ever claims dirty."""
    for args, target_name in (
        (["--board"], "STATE.md"),
        (["--ruling-index"], "ruling-index.md"),
        (["--stream-index"], "stream-index.md"),
    ):
        rc = cli.main([*args, str(repo_with_origin)])
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "(clean)" in out, f"{args[0]} falsely reported dirty from its own write:\n{out}"
        assert (repo_with_origin / target_name).is_file()
        # commit this verb's own output so the NEXT verb in this loop sees a genuinely
        # clean tree too - otherwise the second and third calls would correctly (not
        # falsely) report dirty because of the FIRST call's still-uncommitted artifact.
        _git(repo_with_origin, "add", "-A")
        _git(repo_with_origin, "commit", "-q", "-m", f"generated {target_name}")
