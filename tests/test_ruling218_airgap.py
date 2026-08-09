"""RULING-218: a shared binary carried THIS corpus's doctrine (RULING-200's 200+ band)
across the airgap into example-org, where `--mint ruling` returned 200 instead of the
correct 46 - via TWO compounding defects (s1): (a) discovery was blind on an explicit
root that was never validated, so it silently read 0 ruling homes; (b) even with
discovery repaired, the floor was hardcoded `max(200, ...)` and won regardless, because
RULING-200 has never landed in that corpus. Both fixed together (s2), plus s3's ref-scan
(a claim can live on a pushed branch `--mint` never walked).

This file tests the MECHANISM, synthetically, in disposable tmp_path repos - never against
the live example-org corpus (read-only, out of scope for this seat) or by re-deriving numbers
by hand. The literal example-org repro (46) and the sovereignagents non-regression (218+) were
verified directly against the real corpora as part of this SOW's proof and are recorded
there, not re-asserted here as brittle integration tests against a moving-target corpus.
"""

import subprocess
import pytest
from zero_employee import cli
from zero_employee.core import scan_ref_ruling_claims


def _git(d, *a):
    return subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True, text=True)


def _seed_corpus(d):
    subprocess.run(["git", "init", "-q", str(d)], check=True, capture_output=True)
    _git(d, "config", "user.email", "t@t")
    _git(d, "config", "user.name", "t")
    (d / "claude-md").mkdir(parents=True)
    (d / "claude-md" / "CLAUDE.md").write_text("# c\n")
    return d


def _ruling(d, num, letter, scope="org"):
    d.mkdir(parents=True, exist_ok=True)
    (d / f"RULING-{num}-{letter}.md").write_text(
        f'---\nruling: "{num}"\ngenre: ruling\nstatus: ACTIVE\nlanding_commit: self\n'
        f"scope: {scope}\nrequested_by: operator directive 2026-08-07 (test)\n---\n\n"
        f"# RULING-{num} - {letter}\nbody\n",
        encoding="utf-8",
    )


# -- s1(a)/s2.3: explicit-root discovery is validated, never trusted verbatim --


def test_near_miss_explicit_root_self_heals_via_walkup(tmp_path):
    """THE LITERAL example-org repro shape: `zeo --mint ruling org-master`, run FROM
    INSIDE org-master, builds the nonexistent path `org-master/org-master`. The OLD
    `_discover_root` returned that bogus Path verbatim and every downstream glob against
    it silently came back empty. The fix walks up from the (possibly nonexistent) explicit
    path exactly like it already does from cwd - a near-miss self-heals to the real root
    instead of reading as 0 ruling homes."""
    corpus = _seed_corpus(tmp_path / "org-master")
    rd = corpus / "ruling"
    _ruling(rd, "045", "last", scope="org")
    # cli.main does not itself chdir; reproduce the repro's exact shape - run FROM INSIDE
    # org-master, passing "org-master" again as the positional (the literal command that
    # was reproduced against example-org).
    import os

    old = os.getcwd()
    try:
        os.chdir(corpus)
        rc = cli.main(["--mint", "ruling", "org-master"])
    finally:
        os.chdir(old)
    assert rc == 0


def test_near_miss_explicit_root_yields_the_measured_46_shape(tmp_path, capsys):
    """The example-org numbers, reproduced synthetically: org-scope rulings below 200 and
    no landed RULING-200 -> `1 + highest`, discovered even through the exact near-miss
    path from the repro (`<root> <root>` while already inside <root>)."""
    corpus = _seed_corpus(tmp_path / "org-master")
    rd = corpus / "ruling"
    _ruling(rd, "045", "last", scope="org")
    import os

    old = os.getcwd()
    try:
        os.chdir(corpus)
        rc = cli.main(["--mint", "ruling", "org-master"])
        out = capsys.readouterr().out
    finally:
        os.chdir(old)
    assert rc == 0
    assert "next ORG-SCOPE ruling id = 46" in out
    assert "id = 200" not in out


def test_explicit_root_with_no_corpus_anywhere_errors_closed(tmp_path, capsys):
    """An explicit path with NO claude-md/CLAUDE.md anywhere in its ancestry (a real
    typo, or a directory that just isn't a sows corpus) must hit the SAME "couldn't find
    the sows repo" guard every other verb already has - never a silent Path() passthrough
    that reads downstream as a valid-but-empty corpus."""
    nowhere = tmp_path / "not-a-corpus" / "deeper"
    nowhere.mkdir(parents=True)
    rc = cli.main(["--mint", "ruling", str(nowhere)])
    cap = capsys.readouterr()
    assert rc == 2
    assert "couldn't find a corpus" in cap.err
    assert "next ORG-SCOPE ruling id" not in cap.out


# -- s3: --mint scans refs, not just landed files; names the claimant ref --


@pytest.fixture
def bare_origin(tmp_path):
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, capture_output=True)
    return origin


def _clone(bare_origin, dest):
    subprocess.run(
        ["git", "clone", "-q", str(bare_origin), str(dest)],
        check=True,
        capture_output=True,
    )
    _git(dest, "config", "user.email", "t@t")
    _git(dest, "config", "user.name", "t")
    return dest


def test_ref_scan_names_the_specific_claimant_branch_on_collision(bare_origin, tmp_path, capsys):
    """RULING-218 s3, the demonstrated shape: a peer's claim isn't invisible - it's on a
    PUSHED ref `--mint` never reads from the working tree. Seat A's corpus has landed
    RULING-217 (so the next free integer is 218); seat B pushed a branch that already
    carries RULING-218 - `--mint` must fetch, find it, and name `origin/<branch>`
    specifically, not a generic race caveat."""
    seat_a = _clone(bare_origin, tmp_path / "seat-a")
    _seed_corpus_inplace(seat_a)
    _ruling(seat_a / "ruling", "217", "a", scope="org")
    _git(seat_a, "add", "-A")
    _git(seat_a, "commit", "-q", "-m", "seed")
    _git(seat_a, "push", "-q", "origin", "HEAD:main")

    seat_b = _clone(bare_origin, tmp_path / "seat-b")
    _git(seat_b, "checkout", "-q", "-b", "ds-6/peer-work")
    _ruling(seat_b / "ruling", "218", "peer", scope="org")
    _git(seat_b, "add", "-A")
    _git(seat_b, "commit", "-q", "-m", "peer claims 218")
    _git(seat_b, "push", "-q", "origin", "ds-6/peer-work")

    rc = cli.main(["--mint", "ruling", str(seat_a)])
    out = capsys.readouterr().out
    assert rc == 0
    # RULING-220 A1.2: the RETURNED VALUE is computed from the WIDEST state read (disk
    # AND refs), never the narrower disk-only read alone - disk said 218, the ref claims
    # 218 too, so the honest next-free integer is 219, and the arithmetic that produced
    # it is shown, not just the warning that a collision exists.
    assert "next ORG-SCOPE ruling id = 219" in out
    assert "disk says 218" in out and "MINTING 219" in out
    assert "REF-COLLISION" in out
    assert "origin/ds-6/peer-work" in out
    assert "RULING-218" in out


def test_ref_scan_reports_clear_when_no_ref_claims_the_proposed_number(bare_origin, tmp_path, capsys):
    seat_a = _clone(bare_origin, tmp_path / "seat-a")
    _seed_corpus_inplace(seat_a)
    _ruling(seat_a / "ruling", "090", "a", scope="org")
    _git(seat_a, "add", "-A")
    _git(seat_a, "commit", "-q", "-m", "seed")
    _git(seat_a, "push", "-q", "origin", "HEAD:main")

    seat_b = _clone(bare_origin, tmp_path / "seat-b")
    _git(seat_b, "checkout", "-q", "-b", "ds-6/unrelated-work")
    _ruling(seat_b / "ruling", "050", "peer", scope="org")  # well below seat-a's next (91)
    _git(seat_b, "add", "-A")
    _git(seat_b, "commit", "-q", "-m", "peer, no collision")
    _git(seat_b, "push", "-q", "origin", "ds-6/unrelated-work")

    rc = cli.main(["--mint", "ruling", str(seat_a)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "next ORG-SCOPE ruling id = 91" in out
    assert "REF-COLLISION" not in out
    assert "still free" in out


def _seed_corpus_inplace(d):
    (d / "claude-md").mkdir(parents=True, exist_ok=True)
    (d / "claude-md" / "CLAUDE.md").write_text("# c\n")


def test_scan_ref_ruling_claims_direct_call_returns_ref_to_int_and_path(bare_origin, tmp_path):
    """Unit-level check of the scan function itself, independent of --mint's framing."""
    seat_a = _clone(bare_origin, tmp_path / "seat-a")
    _seed_corpus_inplace(seat_a)
    _git(seat_a, "add", "-A")
    _git(seat_a, "commit", "-q", "-m", "seed")
    _git(seat_a, "push", "-q", "origin", "HEAD:main")

    seat_b = _clone(bare_origin, tmp_path / "seat-b")
    _git(seat_b, "checkout", "-q", "-b", "rescue/stash-0")
    _ruling(seat_b / "ruling", "206", "peer", scope="org")
    _git(seat_b, "add", "-A")
    _git(seat_b, "commit", "-q", "-m", "peer claims 206")
    _git(seat_b, "push", "-q", "origin", "rescue/stash-0")

    claims = scan_ref_ruling_claims(seat_a)
    matches = [(ref, n, p) for ref, (n, p) in claims.items() if ref.endswith("rescue/stash-0")]
    assert len(matches) == 1
    ref, n, p = matches[0]
    assert n == 206
    assert p.endswith("RULING-206-peer.md")


def test_scan_ref_ruling_claims_on_non_git_dir_degrades_to_empty_not_a_crash(tmp_path):
    """Best-effort per the docstring: no git repo at all (fetch/for-each-ref both fail)
    must not raise - it degrades to no claims found, leaving --mint's landed-file answer
    as the only signal (still correct on its own, just without the ref-scan widening)."""
    d = tmp_path / "not-git"
    d.mkdir()
    assert scan_ref_ruling_claims(d) == {}
