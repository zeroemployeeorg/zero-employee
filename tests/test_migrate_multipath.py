"""archive-arch SOW-18 s5b/s5d: the gate must grade every path, and a taught verb must exist."""

import io
import contextlib
from zero_employee.core import migrate_check_render
from zero_employee import cli

GOOD = (
    "---\nsow: a\nn: 1\nschema_rev: 16\nstatus: SHIPPED\ncreated: 2026-01-01\n"
    "updated: 2026-01-01\nsow_repo: r\nwork_repo: r\nproject: ducktyper\n---\n\nbody\n"
)


def _mk(root, rel, body=GOOD):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_EVERY_path_gets_a_verdict_line(tmp_path):
    ps = [str(_mk(tmp_path, f"ducktyper/sow/a/f{i}.md")) for i in range(5)]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        migrate_check_render(ps)
    out = buf.getvalue()
    assert out.count("MIGRATE-CHECK:") == 6, out
    assert "5 path(s) graded" in out


def test_a_SINGLE_path_still_works_as_a_string(tmp_path):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = migrate_check_render(str(_mk(tmp_path, "ducktyper/sow/a/one.md")))
    assert rc == 0 and buf.getvalue().count("MIGRATE-CHECK:") == 1


def test_ONE_bad_path_among_good_ones_fails_the_whole_call(tmp_path):
    ps = [
        str(_mk(tmp_path, "ducktyper/sow/a/ok.md")),
        str(_mk(tmp_path, "ducktyper/sow/a/bad.md", "no frontmatter\n")),
    ]
    with contextlib.redirect_stdout(io.StringIO()):
        rc = migrate_check_render(ps)
    assert rc == 1


def test_the_incarnation_verb_EXISTS_and_prints_an_id(capsys):
    rc = cli.main(["--incarnation"])
    out = capsys.readouterr().out.strip()
    assert rc == 0 and len(out) == 8 and all(c in "0123456789abcdef" for c in out)


def test_two_incarnations_differ(capsys):
    cli.main(["--incarnation"])
    a = capsys.readouterr().out.strip()
    cli.main(["--incarnation"])
    b = capsys.readouterr().out.strip()
    assert a != b
