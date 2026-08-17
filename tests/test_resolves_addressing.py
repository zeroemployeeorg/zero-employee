"""RULING-268 s1 / charter Phase 1 item 2: resolves: <stream>#<n>#<question-id>
addressing — the fine-grained sibling of check_requested_by's already-ruled
<stream>#<n> form (RULING-214 s3), taught to check_resolves.

A bare <stream>#<n> citation (no #<question-id> suffix) resolves EVERY open question
the file carries — the backward-compat rule (RULING-268 s1) — and is explicitly NOT
this function's grain (it is check_requested_by's / check_resolved_by's problem).
"""

import tempfile
import pathlib

from zero_employee.core import check_resolves, build_sow_n_index, extract_frontmatter, iter_sow_files


def _corpus(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    return tmp_path


def _sow_with_questions(d, name, sow_id, n, questions_yaml):
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(
        f"---\nsow: {sow_id}\nn: {n}\nstatus: RULING-REQUESTED\nupdated: 2026-08-01\n"
        f"open_questions:\n{questions_yaml}---\n\nbody\n",
        encoding="utf-8",
    )


def _ruling(d, num, resolves_yaml, extra=""):
    d.mkdir(parents=True, exist_ok=True)
    (d / f"RULING-{num}-x.md").write_text(
        f'---\nruling: "{num}"\ngenre: ruling\nstatus: ACTIVE\nlanding_commit: self\n'
        f"resolves:\n{resolves_yaml}{extra}---\n\nbody\n",
        encoding="utf-8",
    )


def _fm(f):
    return extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))


def _all_fm(root):
    out = []
    for f in iter_sow_files(root):
        fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if isinstance(fm, dict):
            out.append((str(f), fm))
    return out


THREE_Q = (
    "  - id: q1-seat\n"
    "    claim: which seat owns it\n"
    "    status: RESOLVED\n"
    "    resolved_by: 'ruling: RULING-210'\n"
    "  - id: q2-acceptance-test\n"
    "    claim: what proves it\n"
    "    status: RESOLVED\n"
    "    resolved_by: 'ruling: RULING-210'\n"
    "  - id: q3-queue-block\n"
    "    claim: does it block the queue\n"
    "    status: OPEN\n"
    "    resolved_by: null\n"
)


def test_resolves_naming_a_resolved_question_is_silent():
    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _sow_with_questions(root / "p" / "sow" / "archive-arch", "f.md", "archive-arch", 25, THREE_Q)
        _ruling(root / "ruling", "210", "  - archive-arch#25#q1-seat\n  - archive-arch#25#q2-acceptance-test\n")
        out = check_resolves(_all_fm(root), root, sow_index=build_sow_n_index(root))
        assert out == {}


def test_resolves_naming_a_still_open_question_is_flagged():
    """The lands-together rule: citing a question whose own row hasn't flipped to
    RESOLVED yet in the SAME commit is a defect — not a mere ghost, a sequencing one."""
    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _sow_with_questions(root / "p" / "sow" / "archive-arch", "f.md", "archive-arch", 25, THREE_Q)
        _ruling(root / "ruling", "259", "  - archive-arch#25#q3-queue-block\n")
        out = check_resolves(_all_fm(root), root, sow_index=build_sow_n_index(root))
        [(path, findings)] = out.items()
        assert path.endswith("RULING-259-x.md")
        assert findings[0].code == "resolves-missing-landed-closure"


def test_resolves_naming_a_nonexistent_question_id_is_a_ghost():
    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _sow_with_questions(root / "p" / "sow" / "archive-arch", "f.md", "archive-arch", 25, THREE_Q)
        _ruling(root / "ruling", "210", "  - archive-arch#25#q99-nonexistent\n")
        out = check_resolves(_all_fm(root), root, sow_index=build_sow_n_index(root))
        [(path, findings)] = out.items()
        assert findings[0].code == "resolves-ghost-question-id"


def test_resolves_naming_an_unknown_stream_n_is_a_ghost():
    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _ruling(root / "ruling", "210", "  - ghost-stream#99#q1\n")
        out = check_resolves(_all_fm(root), root, sow_index=build_sow_n_index(root))
        [(path, findings)] = out.items()
        assert findings[0].code == "resolves-ghost-stream-n"


def test_bare_stream_n_with_no_question_id_is_not_this_functions_problem():
    """RULING-268 s1: an old-style whole-file citation keeps working exactly as today
    — resolves EVERY open question the file carries. check_resolves only grades entries
    that use the NEW #<question-id> form; a bare stream#n entry is left alone here."""
    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _sow_with_questions(root / "p" / "sow" / "archive-arch", "f.md", "archive-arch", 25, THREE_Q)
        _ruling(root / "ruling", "210", "  - archive-arch#25\n")
        out = check_resolves(_all_fm(root), root, sow_index=build_sow_n_index(root))
        assert out == {}


def test_commit_mode_promotes_ghost_to_error():
    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _ruling(root / "ruling", "210", "  - ghost-stream#99#q1\n")
        out = check_resolves(_all_fm(root), root, sow_index=build_sow_n_index(root), commit_mode=True)
        [(path, findings)] = out.items()
        assert findings[0].severity == "ERROR"


def test_no_resolves_field_is_silent():
    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _ruling(root / "ruling", "210", "", extra="")
        # overwrite without a resolves: key at all
        (root / "ruling" / "RULING-210-x.md").write_text(
            '---\nruling: "210"\ngenre: ruling\nstatus: ACTIVE\nlanding_commit: self\n---\n\nbody\n',
            encoding="utf-8",
        )
        out = check_resolves(_all_fm(root), root, sow_index=build_sow_n_index(root))
        assert out == {}
