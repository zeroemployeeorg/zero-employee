"""--locate: a spawn names the STREAM; the tool derives the rest FROM DISK.

PAID: a spawn message named two chain dirs and two tails for one seat. The stream refused to
derive an n: from it - correctly. org/ holds the whole GitHub org, each project is a repo,
and paths move (twice today). Nothing about a stream's location should be hand-carried.
"""

from zero_employee.core import locate_stream


def _mk(root, rel, body):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def _corpus(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    return tmp_path


def test_it_finds_the_chain_under_the_projects_container(tmp_path):
    r = _corpus(tmp_path)
    _mk(
        r,
        "projects/governance-layer/sow/archive-arch/A-SOW-16-x.md",
        "---\nsow: archive-arch\nn: 16\nrev: p\nstatus: HELD\n---\nb\n",
    )
    L = locate_stream(r, "archive-arch")
    assert L["project"] == "governance-layer"
    assert L["chain_dir"].endswith("projects/governance-layer/sow/archive-arch")


def test_it_reports_the_TAIL_and_the_NEXT_n(tmp_path):
    """The exact thing the contradictory spawn got wrong."""
    r = _corpus(tmp_path)
    for n in (16, 17):
        _mk(
            r,
            f"projects/governance-layer/sow/archive-arch/A-SOW-{n}-x.md",
            f"---\nsow: archive-arch\nn: {n}\nrev: p\nstatus: CLOSEOUT\n---\nb\n",
        )
    L = locate_stream(r, "archive-arch")
    assert L["latest"]["n"] == 17 and L["next_n"] == 18


def test_AMBIGUITY_is_reported_never_resolved(tmp_path):
    r = _corpus(tmp_path)
    _mk(r, "projects/a/sow/dup/x.md", "---\nsow: dup\nn: 1\n---\nb\n")
    _mk(r, "projects/b/sow/dup/y.md", "---\nsow: dup\nn: 1\n---\nb\n")
    L = locate_stream(r, "dup")
    assert L["ambiguous"] and len(L["candidates"]) == 2


def test_an_unknown_stream_is_NOT_invented(tmp_path):
    r = _corpus(tmp_path)
    L = locate_stream(r, "nope")
    assert L["chain_dir"] is None and L["candidates"] == []


def test_the_FLAT_layout_still_resolves(tmp_path):
    r = _corpus(tmp_path)
    _mk(r, "ducktyper/sow/seam/S-SOW-1-x.md", "---\nsow: seam\nn: 1\n---\nb\n")
    assert locate_stream(r, "seam")["project"] == "ducktyper"
