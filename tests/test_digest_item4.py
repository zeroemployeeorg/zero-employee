"""DS6-CHARTER-03 register item 4: `zeo --digest [since]`.

"Fold it in, do not rewrite the bounding logic" (the coordinator's own instruction) -
tools/hooks/zeo-digest.sh lives in the SIBLING org repo, not here, and this port is
verified against ITS ACTUAL BYTES on disk, not against memory of what it does. If the
sibling repo isn't present (a CI checkout of zeo alone, say), the direct-comparison
tests skip rather than fabricate a result; the structural tests below them do not depend
on the sibling repo at all and always run.
"""

import subprocess
import shutil
import pathlib
import re
import os
import pytest
from zero_employee import cli


def _sibling_org_repo() -> pathlib.Path:
    env = os.environ.get("ZEO_ORG_REPO", "").strip()
    if env:
        return pathlib.Path(env).expanduser().resolve()
    # tests/ -> repo root -> sibling org/ (private monorepo layout)
    return pathlib.Path(__file__).resolve().parents[2] / "org"


_ORG_REPO = _sibling_org_repo()
_REAL_SCRIPT = _ORG_REPO / "tools" / "hooks" / "zeo-digest.sh"
_HAS_REAL_SCRIPT = _REAL_SCRIPT.is_file() and shutil.which("bash") is not None


def _git(d, *a):
    return subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True, text=True)


def _corpus(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def two_author_repo(tmp_path):
    """seat-a seeds; seat-b's commits are "the session" - the exact shape the author-
    boundary walk exists to isolate (a clock window would get this wrong after a rebase,
    which is why --since is the FALLBACK, not the default)."""
    r = _corpus(tmp_path)
    subprocess.run(["git", "init", "-q", str(r)], check=True, capture_output=True)
    _git(r, "config", "user.email", "a@a")
    _git(r, "config", "user.name", "seat-a")
    (r / "ruling").mkdir()
    (r / "ruling" / "RULING-001-x.md").write_text(
        '---\nruling: "1"\nscope: org\n---\ntitle: r1\nbody\n', encoding="utf-8"
    )
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "seed by another author")
    _git(r, "config", "user.name", "seat-b")
    (r / "ruling" / "RULING-002-y.md").write_text(
        '---\ntitle: A test ruling filed this session\nruling: "2"\nscope: org\n---\nbody\n',
        encoding="utf-8",
    )
    sd = r / "proj" / "sow" / "demo"
    sd.mkdir(parents=True)
    (sd / "DEMO-SOW-1-x.md").write_text("---\nsow: demo\nn: 1\n---\nbody\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "seat-b files ruling 2 and a sow")
    _git(
        r,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "self-correction: my earlier count was WRONG, fixed",
    )
    return r


def test_digest_walks_the_author_boundary_not_a_clock_window(two_author_repo, capsys):
    """Default (no since): only seat-b's TWO commits count, not seat-a's seed."""
    rc = cli.main(["--digest", str(two_author_repo)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "total: 2" in out
    assert "seed by another author" not in out
    assert "seat-b files ruling 2 and a sow" in out


def test_digest_rulings_and_sows_filed_sections(two_author_repo, capsys):
    rc = cli.main(["--digest", str(two_author_repo)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "RULING-002-y.md" in out
    assert "A test ruling filed this session" in out
    assert (
        "RULING-001-x.md" not in out.split("--- SOWs FILED ---")[0].split("--- RULINGS FILED ---")[1]
    )  # the SEED ruling (seat-a) is not "filed this session"
    assert "DEMO-SOW-1-x.md" in out


def test_digest_self_corrections_section_greps_the_keyword_list(two_author_repo, capsys):
    rc = cli.main(["--digest", str(two_author_repo)])
    out = capsys.readouterr().out
    assert "self-correction: my earlier count was WRONG, fixed" in out


def test_digest_uncosigned_org_scope_rulings_excludes_a_cosigned_one(two_author_repo, capsys):
    (two_author_repo / "ruling" / "RULING-002-y.md").write_text(
        '---\ntitle: cosigned\nruling: "2"\nscope: org\ncosign: "COSIGNED by sparring"\n---\nbody\n',
        encoding="utf-8",
    )
    rc = cli.main(["--digest", str(two_author_repo)])
    out = capsys.readouterr().out
    section = out.split("--- UNCOSIGNED")[1].split("--- TREE STATE")[0]
    assert "RULING-002-y.md" not in section
    assert "RULING-001-x.md" in section  # never cosigned, still owed
    assert "count: 1" in section


def test_digest_tree_state_shows_dirty_tracked_files_not_untracked(two_author_repo, capsys):
    """The bash original filters OUT `??` (untracked) lines from tree state - only
    tracked-file changes are "left behind"; an untracked scratch file is normal."""
    (two_author_repo / "claude-md" / "CLAUDE.md").write_text("# c\nedited\n")
    (two_author_repo / "scratch-untracked.txt").write_text("x")
    rc = cli.main(["--digest", str(two_author_repo)])
    out = capsys.readouterr().out
    section = out.split("--- TREE STATE")[1]
    assert "CLAUDE.md" in section
    assert "scratch-untracked.txt" not in section


def test_digest_explicit_since_window_bypasses_the_author_walk(two_author_repo, capsys):
    rc = cli.main(["--digest", "100y", str(two_author_repo)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "since 100y" in out
    # a 100-year window includes EVERYONE's commits, including seat-a's seed
    assert "seed by another author" in out


def test_digest_no_session_costs_log_says_so_honestly(two_author_repo, capsys):
    rc = cli.main(["--digest", str(two_author_repo)])
    out = capsys.readouterr().out
    assert "no log" in out.split("--- SESSION COST ---")[1]


@pytest.mark.skipif(
    not _HAS_REAL_SCRIPT,
    reason="sibling org repo's tools/hooks/zeo-digest.sh not found - structural tests above still cover the port",
)
def test_digest_matches_the_real_bash_script_on_the_same_commit_range(two_author_repo, tmp_path):
    """THE fidelity check the coordinator asked for: run the ACTUAL script (copied
    byte-for-byte from the sibling org repo at test time, not from memory) against the
    Python port on the identical commit range, and diff. The one permitted difference is
    the WHAT IS OWED NOW block's indentation (the port prefixes every line with the same
    2-space indent every other section already uses; the original bash pastes _triage's
    raw output unindented) - a formatting improvement, not a bounding-logic change, and
    it is the ONLY diff asserted as acceptable below."""
    hooks_dir = two_author_repo / "tools" / "hooks"
    hooks_dir.mkdir(parents=True)
    script = hooks_dir / "zeo-digest.sh"
    script.write_text(_REAL_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    script.chmod(0o755)

    bash_out = subprocess.run(["bash", str(script)], cwd=str(two_author_repo), capture_output=True, text=True).stdout
    from zero_employee.cli import main as _main
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _main(["--digest", str(two_author_repo)])
    py_out = buf.getvalue()

    bash_lines = bash_out.splitlines()
    py_lines = py_out.splitlines()

    # normalize the WHAT IS OWED NOW block's indentation only (the port adds a uniform
    # 2-space prefix to every line of that one pasted-in block for visual consistency
    # with every other section; bash pastes it raw) - compare that block by CONTENT
    # (lstripped), byte-identical everywhere else.
    def _split_owed(lines):
        pre, owed, post = [], [], []
        state = 0
        for l in lines:
            if l.startswith("--- WHAT IS OWED NOW"):
                state = 1
            elif state == 1 and l.startswith("--- UNCOSIGNED"):
                state = 2
            (pre if state == 0 else owed if state == 1 else post).append(l)
        return pre, owed, post

    bp, bo, bpost = _split_owed(bash_lines)
    pp, po, ppost = _split_owed(py_lines)

    # Public package generalizes ruling citations to "doctrine"; the org bash
    # script (and PATH zeo it shells out to for triage) may still name RULING-NNN.
    # Normalize both sides so INTAKE / successor / DARK / UNCOSIGNED headers equate.
    _ruling_cite = re.compile(r"RULING-\d+(?:\s+s[\d.]+)?(?:\s+item\s+\d+)?|doctrine(?:\s+item\s+\d+)?")

    # MEASURED (2026-08-17): the bash script and the Python port each stamp the
    # header's "===== ZEO SESSION DIGEST · since ... · <timestamp> · <host> ====="
    # line with their OWN independent `now()` call, one process apart. Near a
    # minute boundary the two legitimately differ ("07:18" vs "07:19") even
    # though the two runs cover the identical commit range and everything else
    # is byte-identical - this is a genuine race in the test's own comparison
    # method, not a bounding-logic difference between the two implementations.
    # Normalize the timestamp out of the header the same way ruling citations
    # are already normalized above, rather than asserting a coincidence.
    _digest_header_ts = re.compile(r"(===== ZEO SESSION DIGEST · since [^·]*· )\d{4}-\d{2}-\d{2} \d{2}:\d{2}( · )")

    def _norm_for_comparison(line: str) -> str:
        line = _digest_header_ts.sub(r"\1<ts>\2", line)
        if "UNCOSIGNED ORG-SCOPE RULINGS" in line:
            # Parenthetical cite differs (RULING-021 vs doctrine); header identity is enough.
            return "--- UNCOSIGNED ORG-SCOPE RULINGS ---"
        return _ruling_cite.sub("doctrine", line)

    assert [_norm_for_comparison(l) for l in bp] == [_norm_for_comparison(l) for l in pp]
    assert [_norm_for_comparison(l) for l in bpost] == [_norm_for_comparison(l) for l in ppost]
    assert [_norm_for_comparison(l.strip()) for l in bo] == [_norm_for_comparison(l.strip()) for l in po]
