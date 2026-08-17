"""Charter Phase 2: prove open_questions:/resolves: tooling against a FIXTURE shaped
like the real, landed ARCHIVE-ARCH-SOW-25 / -SOW-34 / RULING-259 chain — read-only
against the real corpus, RULING-268 s2's no-retroactive-backfill rule respected by
never touching those landed files.

The real chain (org/projects/zero-employee/sow/archive-arch/ARCHIVE-ARCH-SOW-25-*.md,
org/ruling/RULING-210-genre-visibility.md, ARCHIVE-ARCH-SOW-34-*.md,
org/ruling/RULING-259-genre-visibility-probe-is-the.md — read in full this session, not
edited) predates open_questions: and used the pre-field scalar resolved_by/restaufwand
workaround RULING-268 s2 explicitly grandfathers ("stays legible as the record of how
this was done before the field existed"). Its SHAPE is exactly the charter's Phase 2
brief: three questions (SOW-25's three §4 asks), two answered by one ruling (RULING-210
answers asks 1 and 3), the third by a later one (RULING-259, nine days later per its own
frontmatter dates 2026-08-07 -> 2026-08-16) — and RULING-259 is "not even a SOW" (it is
a ruling, genre: ruling, resolving a SOW's question, matching the charter's own phrasing
literally: the closing document is not itself a SOW).

This file translates that real shape into open_questions: form as a fixture and proves
the NEW tooling's behavior across a genuine two-stage TIMELINE (not a single snapshot):
stage 1 = only the first ruling has landed (2 of 3 resolved) -> --inbox reports
PARTIAL (2/3); stage 2 = the second ruling lands later (3 of 3) -> RESOLVED (3/3). It
also proves the whole-file-citation trap never fires: a ruling that cites the SOW by
bare <stream>#<n> (no #<question-id>) must not be mistaken by check_resolves for having
individually resolved a specific still-open question — RULING-268 s1's backward-compat
rule is a DIFFERENT mechanism (check_ruling_receipts' grain) and check_resolves must
stay silent on it, never fabricate a resolves-missing-landed-closure finding against a
citation that was never trying to use the fine-grained form.
"""

import pathlib
import tempfile

from zero_employee import cli
from zero_employee.core import build_sow_n_index, check_resolves, extract_frontmatter, iter_sow_files

# The three questions, named after SOW-25's own three §4 asks (real file, read this
# session, not reproduced verbatim — only the SHAPE: three questions, a two-stage
# resolution split 2-then-1).
ASK_1_SEAT = "q1-does-s1-change-ruling-203-s1"
ASK_2_ACCEPTANCE = "q2-is-the-probe-the-acceptance-test"
ASK_3_QUEUE = "q3-do-we-start-the-queue-now"

STAGE_1_QUESTIONS = (
    f"  - id: {ASK_1_SEAT}\n"
    "    claim: does the visibility finding change RULING-203 s1\n"
    "    status: RESOLVED\n"
    "    resolved_by: 'ruling: RULING-210'\n"
    f"  - id: {ASK_2_ACCEPTANCE}\n"
    "    claim: is genre-visibility-probe.py DS-6's named acceptance test\n"
    "    status: OPEN\n"
    "    resolved_by: null\n"
    f"  - id: {ASK_3_QUEUE}\n"
    "    claim: does the 59-file queue start now\n"
    "    status: RESOLVED\n"
    "    resolved_by: 'ruling: RULING-210'\n"
)

# Stage 2: the SAME file, later revision — only ask 2's row flips, mirroring how the
# real SOW-34 (a later SOW, not an edit of SOW-25) left ask 2 open and RULING-259 (nine
# days later, per its own dates) closed it. Modeled here as the asking file's own later
# rev, which is exactly what RULING-268 s1's lands-together rule requires: the closing
# citation and the row flip land in the same commit on WHATEVER file carries the row.
STAGE_2_QUESTIONS = (
    f"  - id: {ASK_1_SEAT}\n"
    "    claim: does the visibility finding change RULING-203 s1\n"
    "    status: RESOLVED\n"
    "    resolved_by: 'ruling: RULING-210'\n"
    f"  - id: {ASK_2_ACCEPTANCE}\n"
    "    claim: is genre-visibility-probe.py DS-6's named acceptance test\n"
    "    status: RESOLVED\n"
    "    resolved_by: 'ruling: RULING-259'\n"
    f"  - id: {ASK_3_QUEUE}\n"
    "    claim: does the 59-file queue start now\n"
    "    status: RESOLVED\n"
    "    resolved_by: 'ruling: RULING-210'\n"
)


def _corpus(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("Rev 17\n", encoding="utf-8")
    return tmp_path


def _write_sow25_fixture(root, questions_yaml):
    d = root / "projects" / "zero-employee" / "sow" / "archive-arch"
    d.mkdir(parents=True, exist_ok=True)
    (d / "archive-arch-SOW-25-fixture.md").write_text(
        "---\nsow: archive-arch\nproject: zero-employee\nn: 25\nstatus: RULING-REQUESTED\n"
        "updated: 2026-08-05\ndone_when: x\nrestaufwand: 1\nopen_questions:\n"
        f"{questions_yaml}---\n\nbody (fixture — mirrors real ARCHIVE-ARCH-SOW-25's three "
        "asks; the real file is never edited, see module docstring)\n",
        encoding="utf-8",
    )
    return d / "archive-arch-SOW-25-fixture.md"


def _write_ruling_210(root, resolves_yaml):
    d = root / "ruling"
    d.mkdir(parents=True, exist_ok=True)
    (d / "RULING-210-fixture.md").write_text(
        '---\nruling: "210"\ngenre: ruling\nstatus: ACTIVE\nlanding_commit: self\n'
        f"resolves:\n{resolves_yaml}---\n\nbody (fixture)\n",
        encoding="utf-8",
    )


def _write_ruling_259(root, resolves_yaml):
    # RULING-259 in the real corpus is a RULING, not a SOW — "one of them not even a
    # SOW" per the charter's own phrasing. Mirrored here: this fixture's closing
    # document is genre: ruling, same as RULING-210, never a SOW file.
    d = root / "ruling"
    d.mkdir(parents=True, exist_ok=True)
    (d / "RULING-259-fixture.md").write_text(
        '---\nruling: "259"\ngenre: ruling\nstatus: ACTIVE\nlanding_commit: self\n'
        f"resolves:\n{resolves_yaml}---\n\nbody (fixture)\n",
        encoding="utf-8",
    )


def _all_fm(root):
    out = []
    for f in iter_sow_files(root):
        fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if isinstance(fm, dict):
            out.append((str(f), fm))
    return out


def test_stage_1_two_of_three_resolved_reports_partial(capsys):
    """After only RULING-210 has landed (resolves asks 1 and 3, ask 2 still open):
    --inbox must report PARTIAL (2/3) — the exact charter Phase 2 acceptance line."""
    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _write_sow25_fixture(root, STAGE_1_QUESTIONS)
        _write_ruling_210(root, f"  - archive-arch#25#{ASK_1_SEAT}\n  - archive-arch#25#{ASK_3_QUEUE}\n")

        rc = cli.main(["--inbox", "archive-arch", str(root)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "PARTIAL (2/3)" in out, out
        # the still-open ask must not be silently absorbed into a false RESOLVED/OPEN
        # tag — PARTIAL is the only correct tag for a 2-of-3 mix (RULING-268 s1 exactness)
        assert "RESOLVED (3/3)" not in out
        assert "OPEN (0/3)" not in out

        # and the fine-grained addressing check must be clean: RULING-210's two
        # citations both name rows that ARE status: RESOLVED on the target — no
        # ghost, no lands-together defect.
        findings = check_resolves(_all_fm(root), root, sow_index=build_sow_n_index(root))
        assert findings == {}


def test_stage_2_third_question_resolved_later_reports_resolved_3_of_3(capsys):
    """RULING-259 (a RULING, not a SOW — mirrors the real chain's own shape) lands
    later and resolves the third question. The SAME asking file's next revision
    flips ask 2's row to RESOLVED in the same conceptual commit as RULING-259's
    citation (RULING-268 s1's lands-together rule) — --inbox must now report
    RESOLVED (3/3), not PARTIAL, and not silently stay at 2/3."""
    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _write_sow25_fixture(root, STAGE_2_QUESTIONS)
        _write_ruling_210(root, f"  - archive-arch#25#{ASK_1_SEAT}\n  - archive-arch#25#{ASK_3_QUEUE}\n")
        _write_ruling_259(root, f"  - archive-arch#25#{ASK_2_ACCEPTANCE}\n")

        rc = cli.main(["--inbox", "archive-arch", str(root)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "RESOLVED (3/3)" in out, out
        assert "PARTIAL" not in out

        findings = check_resolves(_all_fm(root), root, sow_index=build_sow_n_index(root))
        assert findings == {}


def test_bare_whole_file_citation_never_silently_resolves_a_named_question():
    """The trap the charter's Phase 2 item 2 names by name: a ruling that cites the
    SOW with a bare <stream>#<n> (old-style, whole-file form) must NOT be treated by
    check_resolves as having resolved any SPECIFIC question — that is
    check_ruling_receipts'/check_resolved_by's grain (RULING-268 s1's own backward-
    compat carve-out), not check_resolves'. Proven here by citing archive-arch#25
    bare while ask 2 is still OPEN (stage 1 shape): check_resolves must find NOTHING
    to flag, because it never even looks at a bare citation — it must not silently
    treat the whole-file cite as a fine-grained resolution of ask 2's still-open row,
    and it must not fabricate a resolves-missing-landed-closure finding either,
    since a bare citation never asserted the fine-grained claim in the first place."""
    with tempfile.TemporaryDirectory() as t:
        root = _corpus(pathlib.Path(t))
        _write_sow25_fixture(root, STAGE_1_QUESTIONS)  # ask 2 still OPEN
        _write_ruling_210(root, "  - archive-arch#25\n")  # bare, whole-file form only

        findings = check_resolves(_all_fm(root), root, sow_index=build_sow_n_index(root))
        # check_resolves grades ONLY #<question-id> entries; a bare stream#n entry is
        # invisible to it by design (test_bare_stream_n_with_no_question_id_is_not_this_functions_problem
        # already proves this for a single-question fixture — this asserts it holds on
        # the real chain's own three-question shape, where a false-positive risk is
        # higher because two of the three rows genuinely resolved by name elsewhere).
        assert findings == {}

        # and the inbox rollup for this file must still honestly show the mix — a
        # bare whole-file ruling citation does not and must not flip open_questions:
        # rows itself (those are frontmatter values, not something check_resolves or
        # the bare-citation form silently mutates); the row data alone drives the tag.
        fm = extract_frontmatter(
            (root / "projects" / "zero-employee" / "sow" / "archive-arch" / "archive-arch-SOW-25-fixture.md").read_text(
                encoding="utf-8"
            )
        )
        from zero_employee.core import open_questions_summary

        summary = open_questions_summary(fm)
        assert summary == {"tag": "PARTIAL", "resolved": 2, "total": 3}
