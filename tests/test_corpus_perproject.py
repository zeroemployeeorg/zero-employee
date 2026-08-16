"""V1-D acceptance — n: scope is PER-PROJECT (collision + gap). Same n in two
projects is not a collision; gaps do not bleed across projects; pre-migration
all-None files preserve the prior flat behavior (extends N6/N7)."""

from zero_employee.core import check_corpus

R = "/root"


def fm(n, rev=None, status=None):
    out = {"n": n}
    if rev is not None:
        out["rev"] = rev
    if status is not None:
        out["status"] = status
    return out


def has(out, path, code):
    return any(f.code == code for f in out.get(path, []))


def test_D1_same_n_diff_projects_no_collision():
    a = (f"{R}/sovereignagents/sow/ds/DOCS-SORT-SOW-31-a.md", fm(31))
    b = (f"{R}/quackverse/sow/tb/QV-SOW-31-b.md", fm(31))
    out = check_corpus([a, b], root=R)
    assert not has(out, a[0], "n-collision")
    assert not has(out, b[0], "n-collision")


def test_D2_same_n_same_project_collides():
    a = (f"{R}/sovereignagents/sow/ds/DOCS-SORT-SOW-31-a.md", fm(31))
    b = (f"{R}/sovereignagents/sow/ds/DOCS-SORT-SOW-31-b.md", fm(31))
    out = check_corpus([a, b], root=R)
    assert has(out, a[0], "n-collision")


def test_D3_flat_legacy_all_none_preserves_prior_collision():
    a = (f"{R}/sow/ds/DOCS-SORT-SOW-31-a.md", fm(31))
    b = (f"{R}/sow/ds/DOCS-SORT-SOW-31-b.md", fm(31))
    out = check_corpus([a, b], root=R)
    assert has(out, a[0], "n-collision")


def test_D4_gaps_dont_bleed_across_projects():
    files = [
        (f"{R}/pa/sow/t/A-SOW-1-x.md", fm(1)),
        (f"{R}/pa/sow/t/A-SOW-2-x.md", fm(2)),
        (f"{R}/pa/sow/t/A-SOW-3-x.md", fm(3)),
        (f"{R}/pb/sow/t/B-SOW-50-x.md", fm(50)),
        (f"{R}/pb/sow/t/B-SOW-51-x.md", fm(51)),
    ]
    out = check_corpus(files, root=R)
    assert not any(f.code == "n-gap" for fs in out.values() for f in fs)


def test_D5_real_gap_within_project_reported():
    files = [
        (f"{R}/pa/sow/t/A-SOW-28-x.md", fm(28)),
        (f"{R}/pa/sow/t/A-SOW-29-x.md", fm(29)),
        (f"{R}/pa/sow/t/A-SOW-30-x.md", fm(30)),
        (f"{R}/pa/sow/t/A-SOW-33-x.md", fm(33)),
    ]
    out = check_corpus(files, root=R)
    assert any(f.code == "n-gap" for fs in out.values() for f in fs)


def test_D6_a_voided_tombstone_sharing_n_and_rev_does_not_permanently_collide():
    """Paid live at profrodai/org, 2026-08-16, one turn after check_ruling_corpus's
    identical-shaped fix (RULING-013's tombstone pair): MOTION-ELEMENTS-SOW-1-
    classroom-element-gap-map.md (status: VOIDED, an accidentally-committed working
    file, formally tombstoned and ratified by a later ruling) shared n:1 rev:a with
    MOTION-ELEMENTS-SOW-1-engine-element-gap-map.md (the real, live chain head) and
    failed the gate forever - the same append-don't-revert tombstone shape as the
    ruling-collision bug, one check over. A VOIDED file sharing an identity slot with
    a live one must not collide."""
    a = (f"{R}/pa/sow/motion-elements/A-SOW-1-classroom.md", fm(1, rev="a", status="VOIDED"))
    b = (f"{R}/pa/sow/motion-elements/A-SOW-1-engine.md", fm(1, rev="a", status="FINDING"))
    out = check_corpus([a, b], root=R)
    assert not has(out, a[0], "n-collision")
    assert not has(out, b[0], "n-collision")


def test_D7_two_live_files_still_collide_even_with_a_voided_third():
    """The fix narrows the check; it must not blind it. Two LIVE files sharing an
    n/rev (matching the real quackverse-coverage-90 SOW-10 pair, both
    RULING-REQUESTED) are still a real, unresolved collision and still error,
    regardless of a third, unrelated VOIDED file also claiming that n/rev."""
    a = (f"{R}/pa/sow/coverage-90/A-SOW-10-a.md", fm(10, rev="9", status="RULING-REQUESTED"))
    b = (f"{R}/pa/sow/coverage-90/A-SOW-10-b.md", fm(10, rev="9", status="RULING-REQUESTED"))
    c = (f"{R}/pa/sow/coverage-90/A-SOW-10-c.md", fm(10, rev="9", status="VOIDED"))
    out = check_corpus([a, b, c], root=R)
    assert has(out, a[0], "n-collision")
    assert has(out, b[0], "n-collision")
    assert not has(out, c[0], "n-collision")


def test_D8_a_shipped_file_still_collides_with_a_second_claimant():
    """SHIPPED/CLOSEOUT/HANDOVER/HELD/BLOCKED/FINDING are terminal-but-still-THE-
    record states, not tombstones - a second file claiming a SHIPPED file's n/rev
    is still a live bug and must still error. Only VOIDED/SUPERSEDED/STALE mean
    "this identity was retracted elsewhere"."""
    a = (f"{R}/pa/sow/t/A-SOW-5-a.md", fm(5, rev="1", status="SHIPPED"))
    b = (f"{R}/pa/sow/t/A-SOW-5-b.md", fm(5, rev="1", status="DRAFT"))
    out = check_corpus([a, b], root=R)
    assert has(out, a[0], "n-collision")
    assert has(out, b[0], "n-collision")
