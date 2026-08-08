"""project: is B1's checksum on the PHYSICAL axis; a disagreement has two causes.

Conflating them would paper over a misplaced FILE by rewriting a field that was right.
"""

from zero_employee.core import project_repair_plan


def _mk(root, rel, body):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def _corpus(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    return tmp_path


def test_a_STREAM_id_in_project_is_REPAIRABLE(tmp_path):
    """The real case: project:'editorial-recon' under ducktyper/ - a stream, not a project."""
    r = _corpus(tmp_path)
    _mk(
        r,
        "projects/ducktyper/sow/editorial-recon/E-SOW-1-x.md",
        "---\nsow: editorial-recon\nproject: editorial-recon\nn: 1\n---\nb\n",
    )
    P = project_repair_plan(r)
    assert len(P["repair"]) == 1 and P["repair"][0]["derived"] == "ducktyper"
    assert P["escalate"] == []


def test_a_REAL_but_different_project_is_ESCALATED_never_rewritten(tmp_path):
    """The file may be MISPLACED. A tool cannot tell which side is wrong."""
    r = _corpus(tmp_path)
    _mk(
        r,
        "projects/ducktyper/sow/a/A-SOW-1-x.md",
        "---\nsow: a\nproject: ducktyper\nn: 1\n---\nb\n",
    )
    _mk(
        r,
        "projects/quackverse/sow/b/B-SOW-1-x.md",
        "---\nsow: b\nproject: b\nn: 1\n---\nb\n",
    )
    _mk(
        r,
        "projects/ducktyper/sow/c/C-SOW-1-x.md",
        "---\nsow: c\nproject: quackverse\nn: 1\n---\nb\n",
    )
    P = project_repair_plan(r)
    esc = [x["file"] for x in P["escalate"]]
    assert any("sow/c/" in f for f in esc), P
    assert not any("sow/c/" in x["file"] for x in P["repair"])


def test_an_AGREEING_project_is_not_reported(tmp_path):
    r = _corpus(tmp_path)
    _mk(
        r,
        "projects/ducktyper/sow/a/A-SOW-1-x.md",
        "---\nsow: a\nproject: ducktyper\nn: 1\n---\nb\n",
    )
    P = project_repair_plan(r)
    assert P["repair"] == [] and P["escalate"] == []


def test_MISSING_carries_its_REASON(tmp_path):
    r = _corpus(tmp_path)
    _mk(r, "projects/ducktyper/sow/a/A-SOW-1-x.md", "---\nsow: a\nn: 1\n---\nb\n")
    P = project_repair_plan(r)
    assert len(P["missing"]) == 1 and P["missing"][0]["why"]


def test_the_plan_writes_NOTHING(tmp_path):
    r = _corpus(tmp_path)
    f = _mk(
        r,
        "projects/ducktyper/sow/e/E-SOW-1-x.md",
        "---\nsow: e\nproject: e\nn: 1\n---\nb\n",
    )
    before = f.read_bytes()
    project_repair_plan(r)
    assert f.read_bytes() == before
