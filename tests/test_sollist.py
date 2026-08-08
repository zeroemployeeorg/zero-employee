"""SOLL/IST-VERGLEICH: what a rev PLANNED against what the next rev DID.

PAID: a session ran the wrong work for a full sitting with every instrument green, and the
operator could not tell without asking. Nothing compared plan to outcome.
"""

from zero_employee.core import soll_ist, ABWEICHUNG_CODES

HEAD = "---\nsow: s\nn: {n}\ncreated: 2026-01-0{n}\nupdated: 2026-01-0{n}\nstatus: PROGRESS\n"


def _corpus(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    return tmp_path


def _rev(root, n, acts=None, body="nothing happened", extra=""):
    d = root / "p" / "sow" / "s"
    d.mkdir(parents=True, exist_ok=True)
    fm = HEAD.format(n=n)
    if acts:
        fm += "next_three_acts: [" + ", ".join('"%s"' % a for a in acts) + "]\n"
    fm += extra + "---\n\n" + body + "\n"
    (d / ("r%d.md" % n)).write_text(fm, encoding="utf-8")


def test_a_plan_CARRIED_OUT_reads_AS_PLANNED(tmp_path):
    r = _corpus(tmp_path)
    _rev(r, 1, ["migrate the render-quality batch", "commit the frontmatter"])
    _rev(
        r,
        2,
        body="I migrated the render-quality batch and did commit the frontmatter today",
    )
    x = soll_ist(r)[0]
    assert x["verdict"] == "AS-PLANNED" and x["done"] == 2


def test_a_plan_ABANDONED_reads_FULL_VARIANCE(tmp_path):
    """archive-arch's shape: planned one thing, spent the session on another."""
    r = _corpus(tmp_path)
    _rev(r, 1, ["migrate the render-quality batch", "commit the frontmatter"])
    _rev(r, 2, body="Spent the session hand-classifying unrelated documents entirely")
    x = soll_ist(r)[0]
    assert x["verdict"] == "FULL-VARIANCE" and x["done"] == 0


def test_an_UNSTATED_variance_is_flagged(tmp_path):
    r = _corpus(tmp_path)
    _rev(r, 1, ["migrate the render-quality batch"])
    _rev(r, 2, body="did something else altogether")
    assert soll_ist(r)[0]["unstated"] is True


def test_a_STATED_variance_is_NOT_flagged(tmp_path):
    """A plan may change. It may not change SILENTLY."""
    r = _corpus(tmp_path)
    _rev(r, 1, ["migrate the render-quality batch"])
    _rev(r, 2, body="did something else", extra="abweichung: DISCOVERED-WORK\n")
    x = soll_ist(r)[0]
    assert x["unstated"] is False and x["abweichung"] == "DISCOVERED-WORK"


def test_the_LEDGER_counts_as_evidence_of_doing(tmp_path):
    r = _corpus(tmp_path)
    _rev(r, 1, ["backfill the project field"])
    _rev(
        r,
        2,
        body="see ledger",
        extra=(
            "ledger:\n  - claim: backfill-the-project-field-landed\n    state: SHIPPED\n"
            '    commit: abc1234\n    check: "gate green"\n'
        ),
    )
    assert soll_ist(r)[0]["done"] == 1


def test_a_rev_with_NO_plan_produces_no_comparison(tmp_path):
    """Absence of SOLL is not a variance - it is an absence, and it is reported as one."""
    r = _corpus(tmp_path)
    _rev(r, 1)
    _rev(r, 2, body="work happened")
    assert soll_ist(r) == []


def test_the_codes_are_the_four_plus_as_planned():
    assert set(ABWEICHUNG_CODES) == {
        "SCOPE-CHANGED",
        "ESTIMATE-WRONG",
        "BLOCKED-EXTERNAL",
        "DISCOVERED-WORK",
        "AS-PLANNED",
    }
