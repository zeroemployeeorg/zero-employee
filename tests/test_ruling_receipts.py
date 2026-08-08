"""RULING-214 s2: a ruling naming an asking SOW whose resolved_by does not cite it back
is an ERROR at the commit path, WARN otherwise. Deliberately narrow to the SOW(s) a ruling
literally names in its own requested_by - never a SOW its prose body merely discusses."""

import tempfile
import pathlib
from zero_employee.core import check_ruling_receipts, build_sow_n_index


def _corpus(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    return tmp_path


def _sow(d, name, sow_id, n, resolved_by=""):
    d.mkdir(parents=True, exist_ok=True)
    rb = f'resolved_by: "{resolved_by}"\n' if resolved_by else ""
    (d / name).write_text(
        f"---\nsow: {sow_id}\nn: {n}\nstatus: RULING-REQUESTED\nupdated: 2026-08-01\n{rb}---\n\nbody\n",
        encoding="utf-8",
    )


def _ruling(d, num, requested_by, extra=""):
    d.mkdir(parents=True, exist_ok=True)
    (d / f"RULING-{num}-x.md").write_text(
        f'---\nruling: "{num}"\ngenre: ruling\nstatus: ACTIVE\nlanding_commit: self\n'
        f"requested_by: {requested_by}\n{extra}---\n\nbody\n",
        encoding="utf-8",
    )


def test_a_named_asker_that_cites_back_is_silent():
    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _sow(root / "p" / "sow" / "s", "f.md", "s", 1, resolved_by="ruling: RULING-200")
        _ruling(root / "ruling", "200", "s#1")
        files_fm = [(str(f), _fm(f)) for f in (root / "p" / "sow" / "s").glob("*.md")]
        files_fm += [(str(f), _fm(f)) for f in (root / "ruling").glob("*.md")]
        out = check_ruling_receipts(files_fm, root)
        assert out == {}


def test_a_named_asker_that_does_NOT_cite_back_is_flagged():
    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _sow(root / "p" / "sow" / "s", "f.md", "s", 1)  # no resolved_by at all
        _ruling(root / "ruling", "200", "s#1")
        files_fm = _all_fm(root)
        out = check_ruling_receipts(files_fm, root)
        assert len(out) == 1
        [(path, findings)] = out.items()
        assert path.endswith("RULING-200-x.md")
        assert findings[0].code == "resolved-by-missing-citation"
        assert findings[0].severity == "WARN"


def test_commit_mode_promotes_missing_citation_to_error():
    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _sow(root / "p" / "sow" / "s", "f.md", "s", 1)
        _ruling(root / "ruling", "200", "s#1")
        out = check_ruling_receipts(_all_fm(root), root, commit_mode=True)
        [(path, findings)] = out.items()
        assert findings[0].severity == "ERROR"


def test_a_ruling_disposing_a_sow_it_never_names_is_NOT_flagged():
    """RULING-070's exact shape: disposes four SOWs' questions on terminal-state ground
    but names only ONE in requested_by. The lint must not infer the other three from
    the ruling's PROSE - that would be indistinguishable from a real closure and is the
    exact shape the Master's own backfill message forbids building."""
    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _sow(
            root / "p" / "sow" / "named",
            "f.md",
            "named",
            1,
            resolved_by="ruling: RULING-070",
        )
        _sow(root / "p" / "sow" / "unnamed", "g.md", "unnamed", 3)  # never named, never cites
        _ruling(root / "ruling", "070", "named#1")
        out = check_ruling_receipts(_all_fm(root), root)
        assert out == {}  # unnamed#3 is invisible to this lint - it was never asked to check it


def test_an_operator_directive_requested_by_has_no_asker_to_check():
    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _ruling(root / "ruling", "200", "operator directive 2026-08-01 (fleet risk)")
        out = check_ruling_receipts(_all_fm(root), root)
        assert out == {}


def test_an_unresolvable_target_is_not_this_lints_problem():
    """A ghost citation is check_requested_by's problem; this lint only judges targets
    that resolve, so it must not crash or misreport on one that doesn't."""
    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _ruling(root / "ruling", "200", "ghost-stream#99")
        out = check_ruling_receipts(_all_fm(root), root)
        assert out == {}


def test_stream_n_form_receipt_citation_round_trips():
    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _sow(
            root / "p" / "sow" / "archive-arch",
            "f.md",
            "archive-arch",
            22,
            resolved_by="ruling: RULING-214",
        )
        _ruling(root / "ruling", "214", "archive-arch#22")
        out = check_ruling_receipts(_all_fm(root), root)
        assert out == {}


def test_build_sow_n_index_keeps_the_latest_rev_by_updated():
    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        d = root / "p" / "sow" / "s"
        d.mkdir(parents=True)
        (d / "r1.md").write_text("---\nsow: s\nn: 1\nupdated: 2026-08-01\n---\n\nold\n", encoding="utf-8")
        (d / "r2.md").write_text("---\nsow: s\nn: 1\nupdated: 2026-08-05\n---\n\nnew\n", encoding="utf-8")
        idx = build_sow_n_index(root)
        path, fm = idx[("s", 1)]
        assert path.endswith("r2.md")


def _fm(f):
    from zero_employee.core import extract_frontmatter

    fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
    return fm


def _all_fm(root):
    from zero_employee.core import iter_sow_files, extract_frontmatter

    out = []
    for f in iter_sow_files(root):
        fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if isinstance(fm, dict):
            out.append((str(f), fm))
    return out
