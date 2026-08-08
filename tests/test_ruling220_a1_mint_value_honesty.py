"""RULING-220 AMENDMENT A1: disclosure is half a fix - the RETURNED VALUE must come from
the WIDEST state an instrument reads, never the narrowest.

MEASURED (profrodai, pre-fix): disk said 44, pushed refs claimed 45 and 46, and --mint
still printed 44 - the ref scan ran, fired correctly, named the specific claimants, and
the number beside all of it stayed the disk-only answer. THE ORDERING WAS THE BUG:
cli.py printed `nxt` before calling scan_ref_ruling_claims at all, so there was no point
in the function where the wider read could have changed what was already on screen.

RULED (A1.2), the exact worked example: disk says 44, refs claim 45 and 46 -> MINTING 47.
These tests reproduce that shape with real git remotes and multiple colliding refs at
different heights, not just the single-collision case test_ruling218_airgap.py already
covers.
"""

import subprocess
import pytest
from zero_employee import cli


def _git(d, *a):
    return subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True, text=True)


def _seed_corpus_inplace(d):
    (d / "claude-md").mkdir(parents=True, exist_ok=True)
    (d / "claude-md" / "CLAUDE.md").write_text("# c\n")


def _ruling(d, num, letter, scope="org"):
    d.mkdir(parents=True, exist_ok=True)
    (d / f"RULING-{num}-{letter}.md").write_text(
        f'---\nruling: "{num}"\ngenre: ruling\nstatus: ACTIVE\nlanding_commit: self\n'
        f"scope: {scope}\nrequested_by: operator directive 2026-08-07 (test)\n---\n\n"
        f"# RULING-{num} - {letter}\nbody\n",
        encoding="utf-8",
    )


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


def test_the_exact_ruled_worked_example_disk_44_refs_45_and_46_mints_47(bare_origin, tmp_path, capsys):
    """A1.2's own worked example, reproduced literally: TWO different peers pushed TWO
    different claims at TWO different heights, both >= the disk-only answer. The minted
    value must clear the HIGHEST of them, not just notice the first one found."""
    seat_a = _clone(bare_origin, tmp_path / "seat-a")
    _seed_corpus_inplace(seat_a)
    _ruling(seat_a / "ruling", "043", "a", scope="org")  # disk-only next = 44
    _git(seat_a, "add", "-A")
    _git(seat_a, "commit", "-q", "-m", "seed, disk says 44")
    _git(seat_a, "push", "-q", "origin", "HEAD:main")

    seat_b = _clone(bare_origin, tmp_path / "seat-b")
    _git(seat_b, "checkout", "-q", "-b", "peer/claims-45")
    _ruling(seat_b / "ruling", "045", "peer-low", scope="org")
    _git(seat_b, "add", "-A")
    _git(seat_b, "commit", "-q", "-m", "peer claims 45")
    _git(seat_b, "push", "-q", "origin", "peer/claims-45")

    seat_c = _clone(bare_origin, tmp_path / "seat-c")
    _git(seat_c, "checkout", "-q", "-b", "peer/claims-46")
    _ruling(seat_c / "ruling", "046", "peer-high", scope="org")
    _git(seat_c, "add", "-A")
    _git(seat_c, "commit", "-q", "-m", "peer claims 46, the higher one")
    _git(seat_c, "push", "-q", "origin", "peer/claims-46")

    rc = cli.main(["--mint", "ruling", str(seat_a)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "next ORG-SCOPE ruling id = 47" in out
    assert "disk says 44" in out
    assert "MINTING 47" in out
    assert "REF-COLLISION" in out
    # BOTH claimants named, not just the one that happened to be checked first
    assert "peer/claims-45" in out and "RULING-45" in out
    assert "peer/claims-46" in out and "RULING-46" in out


def test_a_single_collision_exactly_at_the_disk_answer_still_advances_by_one(bare_origin, tmp_path, capsys):
    """The boundary case: a ref claims EXACTLY the disk-only next integer (not higher) -
    still a real collision (>=), still must advance the minted value past it."""
    seat_a = _clone(bare_origin, tmp_path / "seat-a")
    _seed_corpus_inplace(seat_a)
    _ruling(seat_a / "ruling", "099", "a", scope="org")  # disk-only next = 100
    _git(seat_a, "add", "-A")
    _git(seat_a, "commit", "-q", "-m", "seed")
    _git(seat_a, "push", "-q", "origin", "HEAD:main")

    seat_b = _clone(bare_origin, tmp_path / "seat-b")
    _git(seat_b, "checkout", "-q", "-b", "peer/exact-match")
    _ruling(seat_b / "ruling", "100", "peer", scope="org")  # exactly == disk's next
    _git(seat_b, "add", "-A")
    _git(seat_b, "commit", "-q", "-m", "peer claims exactly 100")
    _git(seat_b, "push", "-q", "origin", "peer/exact-match")

    rc = cli.main(["--mint", "ruling", str(seat_a)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "next ORG-SCOPE ruling id = 101" in out
    assert "disk says 100" in out and "MINTING 101" in out


def test_no_collision_leaves_the_disk_answer_completely_unchanged(bare_origin, tmp_path, capsys):
    """The negative case, pinned explicitly so the fix cannot be a blanket +1: when
    nothing on any ref claims >= the disk answer, the minted value IS the disk answer,
    with no 'disk says / MINTING' arithmetic line at all (nothing to disclose)."""
    seat_a = _clone(bare_origin, tmp_path / "seat-a")
    _seed_corpus_inplace(seat_a)
    _ruling(seat_a / "ruling", "010", "a", scope="org")  # disk-only next = 11
    _git(seat_a, "add", "-A")
    _git(seat_a, "commit", "-q", "-m", "seed")
    _git(seat_a, "push", "-q", "origin", "HEAD:main")

    seat_b = _clone(bare_origin, tmp_path / "seat-b")
    _git(seat_b, "checkout", "-q", "-b", "peer/unrelated")
    _ruling(seat_b / "ruling", "005", "peer", scope="org")  # well below the disk answer
    _git(seat_b, "add", "-A")
    _git(seat_b, "commit", "-q", "-m", "no collision")
    _git(seat_b, "push", "-q", "origin", "peer/unrelated")

    rc = cli.main(["--mint", "ruling", str(seat_a)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "next ORG-SCOPE ruling id = 11" in out
    assert "disk says" not in out
    assert "MINTING" not in out
    assert "REF-COLLISION" not in out
