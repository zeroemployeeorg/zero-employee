"""A stream is what it DECLARES, not where it sits (GM-DS6-214).

locate_stream matched the directory name only, so `--locate quackverse-repo-hygiene` returned
nothing while the board showed 11 open rows for it: the SOWs declare that id and live in a dir
named `repo-hygiene`. Every other projection keys on `fm.get("sow") or <dirname>`.
"""

from zero_employee.core import locate_stream


def _corpus(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    return tmp_path


def _mk(root, rel, sow, n=1):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\nsow: %s\nn: %d\nrev: a\nstatus: HELD\n---\nb\n" % (sow, n),
        encoding="utf-8",
    )


def test_a_QUALIFIED_id_in_an_UNQUALIFIED_dir_resolves(tmp_path):
    """The live case: sow: quackverse-repo-hygiene inside sow/repo-hygiene/."""
    r = _corpus(tmp_path)
    _mk(r, "projects/quackverse/sow/repo-hygiene/a.md", "quackverse-repo-hygiene")
    L = locate_stream(r, "quackverse-repo-hygiene")
    assert L["chain_dir"] and L["chain_dir"].endswith("repo-hygiene")


def test_the_DIRECTORY_name_is_not_a_stream_id_when_a_declaration_exists(tmp_path):
    r = _corpus(tmp_path)
    _mk(r, "projects/quackverse/sow/repo-hygiene/a.md", "quackverse-repo-hygiene")
    assert locate_stream(r, "repo-hygiene")["chain_dir"] is None


def test_a_dir_hosting_a_FOREIGN_relay_sow_resolves_for_BOTH(tmp_path):
    """Measured live: docs-sort/ hosts a quackverse-cto-relay SOW. Legitimate."""
    r = _corpus(tmp_path)
    _mk(r, "projects/g/sow/docs-sort/a.md", "docs-sort", 1)
    _mk(r, "projects/g/sow/docs-sort/b.md", "quackverse-cto-relay", 2)
    assert locate_stream(r, "docs-sort")["chain_dir"]
    assert locate_stream(r, "quackverse-cto-relay")["chain_dir"]


def test_an_UNDECLARED_dir_still_falls_back_to_its_name(tmp_path):
    r = _corpus(tmp_path)
    d = tmp_path / "projects/p/sow/legacy"
    d.mkdir(parents=True)
    (d / "a.md").write_text("no frontmatter\n", encoding="utf-8")
    assert locate_stream(r, "legacy")["chain_dir"]
