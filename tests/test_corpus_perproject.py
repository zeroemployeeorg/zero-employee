"""V1-D acceptance — n: scope is PER-PROJECT (collision + gap). Same n in two
projects is not a collision; gaps do not bleed across projects; pre-migration
all-None files preserve the prior flat behavior (extends N6/N7)."""

from zero_employee.core import check_corpus

R = "/root"


def fm(n):
    return {"n": n}


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
