"""RESTAUFWAND: what is LEFT and whether it is FALLING (RULING-202 s3).

Percent-complete rises while the work grows. The trend of REMAINING is the signal, and
`done_when` with a runnable predicate is what lets a stream ever stop - measured at zero
corpus-wide, which is why profrod-site sat 10 days at one SOW in DESIGN.
"""

from zero_employee.core import restaufwand


def _corpus(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    return tmp_path


def _rev(root, n, rest=None, dw=None, status="PROGRESS"):
    d = root / "p" / "sow" / "s"
    d.mkdir(parents=True, exist_ok=True)
    fm = "---\nsow: s\nn: %d\nstatus: %s\n" % (n, status)
    if rest is not None:
        fm += "restaufwand: %d\n" % rest
    if dw:
        fm += 'done_when: "%s"\n' % dw
    (d / ("r%d.md" % n)).write_text(fm + "---\n\nbody\n", encoding="utf-8")


def test_a_shrinking_remainder_reads_FALLING(tmp_path):
    r = _corpus(tmp_path)
    _rev(r, 1, 40)
    _rev(r, 2, 31)
    x = restaufwand(r)[0]
    assert x["verdict"] == "FALLING" and x["delta"] == -9 and x["remaining"] == 31


def test_an_UNCHANGED_remainder_reads_FLAT_because_busy_is_not_progressing(tmp_path):
    r = _corpus(tmp_path)
    _rev(r, 1, 40)
    _rev(r, 2, 40)
    assert restaufwand(r)[0]["verdict"] == "FLAT"


def test_a_GROWING_remainder_reads_RISING(tmp_path):
    """Discovery outpacing delivery. Not a fault - a fact that wants a reason."""
    r = _corpus(tmp_path)
    _rev(r, 1, 40)
    _rev(r, 2, 55)
    x = restaufwand(r)[0]
    assert x["verdict"] == "RISING" and x["delta"] == 15


def test_NO_declaration_reads_UNDECLARED_never_a_silent_zero(tmp_path):
    r = _corpus(tmp_path)
    _rev(r, 1)
    _rev(r, 2)
    x = restaufwand(r)[0]
    assert x["verdict"] == "UNDECLARED" and x["remaining"] is None


def test_ONE_declaration_is_SINGLE_POINT_not_a_trend(tmp_path):
    """A trend needs two points. One number is a claim, not a direction."""
    r = _corpus(tmp_path)
    _rev(r, 1)
    _rev(r, 2, 40)
    assert restaufwand(r)[0]["verdict"] == "SINGLE-POINT"


def test_a_WORKING_status_without_done_when_is_FLAGGED(tmp_path):
    """RULING-202 s4: a stream that cannot state its stopping condition has a DIRECTION."""
    r = _corpus(tmp_path)
    _rev(r, 1, 10, status="DESIGN")
    assert restaufwand(r)[0]["needs_done_when"] is True


def test_a_WORKING_status_WITH_done_when_is_not_flagged(tmp_path):
    r = _corpus(tmp_path)
    _rev(r, 1, 10, dw="make verify -> 0 failures", status="PROGRESS")
    x = restaufwand(r)[0]
    assert x["needs_done_when"] is False and "make verify" in x["done_when"]


def test_a_RESTING_status_needs_no_done_when(tmp_path):
    r = _corpus(tmp_path)
    _rev(r, 1, 0, status="CLOSEOUT")
    assert restaufwand(r)[0]["needs_done_when"] is False


def test_the_LATEST_rev_supplies_done_when(tmp_path):
    r = _corpus(tmp_path)
    _rev(r, 1, 10, dw="OLD")
    _rev(r, 2, 5, dw="NEW")
    assert restaufwand(r)[0]["done_when"] == "NEW"
