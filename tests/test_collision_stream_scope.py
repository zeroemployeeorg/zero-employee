"""n-collision is per STREAM, not per project (the schema: "a fresh increment for the
stream's dir"). 78 ERRORs were reported across 19 streams whose SOW-01s are all correct.
"""

from zero_employee.core import check_corpus


def _fm(n, rev="a", sow="x"):
    return {"n": n, "rev": rev, "sow": sow}


def test_two_STREAMS_sharing_n_are_NOT_a_collision(tmp_path):
    """The defect: ACTING-SOW-01 and GUIDE-SWEEP-SOW-01 are both legitimately n:1 rev:a."""
    files = [
        ("ducktyper/sow/acting/ACTING-SOW-01-a.md", _fm(1)),
        ("ducktyper/sow/guide-sweep/GUIDE-SWEEP-SOW-01-b.md", _fm(1)),
    ]
    out = check_corpus(files)
    assert all(f.code != "n-collision" for fs in out.values() for f in fs), dict(out)


def test_the_SAME_stream_reusing_n_and_rev_IS_still_a_collision(tmp_path):
    files = [
        ("ducktyper/sow/acting/ACTING-SOW-01-a.md", _fm(1)),
        ("ducktyper/sow/acting/ACTING-SOW-01-duplicate.md", _fm(1)),
    ]
    out = check_corpus(files)
    codes = [f.code for fs in out.values() for f in fs]
    assert "n-collision" in codes


def test_same_stream_same_n_DIFFERENT_rev_is_a_rev_chain_not_a_collision(tmp_path):
    """SOW-53 Option B, preserved."""
    files = [
        ("ducktyper/sow/acting/ACTING-SOW-01-a.md", _fm(1, rev="a")),
        ("ducktyper/sow/acting/ACTING-SOW-01-b.md", _fm(1, rev="b")),
    ]
    out = check_corpus(files)
    assert all(f.code != "n-collision" for fs in out.values() for f in fs)


def test_flat_legacy_still_uses_the_PREFIX_proxy(tmp_path):
    """SOW-52, preserved: no stream dir, so the filename prefix is the stream."""
    files = [
        ("sow/TRACKA-SOW-1-thing.md", _fm(1)),
        ("sow/TRACKA-SOW-1-other.md", _fm(1)),
    ]
    out = check_corpus(files)
    codes = [f.code for fs in out.values() for f in fs]
    assert "n-collision" in codes


def test_flat_legacy_DISTINCT_prefixes_still_WARN_not_error(tmp_path):
    """SOW-52's cross-stream verdict, which the first cut DELETED by keying flat files on
    the stream: every group became single-stream so the WARN branch was unreachable.
    Note the fixture: SOW-TrackA-* and SOW-TrackB-* both reduce to prefix 'SOW' under the
    heuristic, so they are SAME-stream by its rules - the names must differ BEFORE -SOW-."""
    files = [
        ("sow/TRACKA-SOW-1-thing.md", _fm(1)),
        ("sow/TRACKB-SOW-1-other.md", _fm(1)),
    ]
    out = check_corpus(files)
    codes = [f.code for fs in out.values() for f in fs]
    assert "n-collision" not in codes
    assert "n-collision-premigration" in codes
