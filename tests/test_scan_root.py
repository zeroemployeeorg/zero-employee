"""The scan must search the CORPUS, not the stream dir.

PAID: --promote handed the stream dir to citation_scan, so it searched the six files being
renamed and reported "2 references in 1 file" - while a ruling one directory over cited one
of them. A scan that silently searches the wrong tree reports safety from no evidence.
"""

from zero_employee.core import corpus_root, citation_scan, citation_totals

RMAP = {"GS-SOW-04-relief.md": "gs-SOW-4-relief.md"}


def _corpus(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# canonical\n", encoding="utf-8")
    d = tmp_path / "ducktyper" / "sow" / "gs"
    d.mkdir(parents=True)
    (d / "GS-SOW-04-relief.md").write_text("body\n", encoding="utf-8")
    r = tmp_path / "ducktyper" / "ruling"
    r.mkdir(parents=True)
    (r / "RULING-045.md").write_text("requested_by: ducktyper/sow/gs/GS-SOW-04-relief.md\n", encoding="utf-8")
    return tmp_path, d


def test_corpus_root_walks_UP_to_the_marker(tmp_path):
    root, stream = _corpus(tmp_path)
    assert corpus_root(stream) == root.resolve()


def test_corpus_root_is_None_without_a_marker(tmp_path):
    (tmp_path / "x").mkdir()
    assert corpus_root(tmp_path / "x") is None


def test_scanning_from_the_STREAM_DIR_misses_the_ruling(tmp_path):
    """The defect, pinned: this is what the live run actually did."""
    root, stream = _corpus(tmp_path)
    assert citation_totals(citation_scan(stream, RMAP)) == (0, 0)


def test_scanning_from_the_CORPUS_ROOT_finds_it(tmp_path):
    root, stream = _corpus(tmp_path)
    hits = citation_scan(corpus_root(stream), RMAP)
    assert "ducktyper/ruling/RULING-045.md" in hits
    assert citation_totals(hits)[1] >= 1


def test_a_hit_carries_its_DIRECTORY_PREFIX_which_is_how_the_bug_showed(tmp_path):
    root, stream = _corpus(tmp_path)
    hits = citation_scan(corpus_root(stream), RMAP)
    assert all("/" in k for k in hits), "a bare filename means the root was the stream dir"
