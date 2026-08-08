"""RULING-216 s3(2)/s3(3)/s4: SURVIVE (minted_as + a tombstone in ruling-index.md) and
MINT (`--mint ruling|sow <stream>`), end to end through the real CLI - not just the
functions in isolation, the same discipline test_ruling216_detect.py exists to teach
(a wire-in that only passes a direct-call unit test is not shipped).

THE DEMONSTRATED-NOT-ASSERTED ROUND TRIP (the coordinator's own done_when): mint a
name, collide it for real, renumber the loser, append `minted_as:` (a legal RULING-004
append on a landed file, never a rewrite), regenerate the index, and show the OLD
integer resolves to BOTH candidates - the owner AND a dated tombstone - rather than to
silence or to a confident wrong answer. This is run against a disposable tmp_path repo,
not the real org corpus: a demonstration must not fabricate history onto a real landed
ruling (RULING-215 was checked and carries no minted_as - inventing one to manufacture a
tidy demo would be exactly the fabrication-for-a-clean-story CLAUDE.md forbids), and a
synthetic-but-real round trip through the actual CLI is STRONGER evidence than a
one-off manual demo because it is reproducible on every future run.
"""

import subprocess
import pytest
from zero_employee import cli
from zero_employee.core import build_ruling_index, render_ruling_index, next_ruling_id


def _git(d, *a):
    subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n")
    return tmp_path


def _ruling(d, num, letter, scope="org", minted_as=None, title="x"):
    d.mkdir(parents=True, exist_ok=True)
    extra = f'minted_as: "{minted_as}"\n' if minted_as else ""
    (d / f"RULING-{num}-{letter}.md").write_text(
        f'---\nruling: "{num}"\ngenre: ruling\nstatus: ACTIVE\nlanding_commit: self\n'
        f"scope: {scope}\n{extra}"
        "requested_by: operator directive 2026-08-07 (test)\n---\n\n"
        f"# RULING-{num} - {title}\nbody\n",
        encoding="utf-8",
    )


# -- MINT: next-free-id, live-read, race note on every call --


def test_mint_ruling_floors_at_200_and_reads_the_real_corpus(repo, capsys):
    rd = repo / "ruling"
    _ruling(rd, "205", "a", scope="org")
    _ruling(rd, "090", "b", scope="org")  # below-band legacy, must not confuse the max
    rc = cli.main(["--mint", "ruling", str(repo)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "next ORG-SCOPE ruling id = 206" in out


def test_mint_ruling_floor_only_applies_when_ruling_200_is_landed(repo, capsys):
    """RULING-218 s2: the 200 floor is a property of the CORPUS under test, discovered
    from whether RULING-200 is itself a landed file here - never a compiled-in constant.
    With RULING-200 landed, the band holds even against a lower highest-org-scope integer
    (this is what the OLD hardcoded-floor test asserted; it now must be earned by a real
    landed RULING-200, not assumed for every corpus)."""
    rd = repo / "ruling"
    _ruling(rd, "200", "band", scope="org", title="the band-establishing ruling")
    rc = cli.main(["--mint", "ruling", str(repo)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "next ORG-SCOPE ruling id = 201" in out  # 200 is taken; the floor still holds


def test_mint_ruling_no_floor_without_ruling_200_landed(repo, capsys):
    """RULING-218 s2 item 2, the profrodai shape exactly: a corpus with org-scope rulings
    below 200 and NO landed RULING-200 gets 1 + highest existing, full stop - the floor
    must never win uncontested just because the BINARY knows about it."""
    rd = repo / "ruling"
    _ruling(rd, "045", "last", scope="org")
    rc = cli.main(["--mint", "ruling", str(repo)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "next ORG-SCOPE ruling id = 46" in out
    assert "id = 200" not in out


def test_mint_ruling_errors_when_no_ruling_home_discoverable(repo, capsys):
    """RULING-218 s2.3: 0 discoverable ruling homes (no `ruling/` dir anywhere - the
    literal `read from 0 ruling home(s)` signal from the profrodai repro) must REFUSE to
    mint, never fall back to a confident number. This `repo` fixture has claude-md/
    CLAUDE.md (a real corpus root) but has never had a ruling/ directory created."""
    rc = cli.main(["--mint", "ruling", str(repo)])
    cap = capsys.readouterr()
    assert rc != 0
    assert "REFUSED" in (cap.out + cap.err)
    assert "next ORG-SCOPE ruling id" not in cap.out


def test_mint_race_note_prints_every_invocation_never_suppressed(repo, capsys):
    """The convenient-signal-standing-in-for-a-true-one defect (named 5x before this
    session): a bare integer with no caveat reads as a guarantee. Assert the caveat text
    is present, not just that the call succeeds. `ruling/` exists but is genuinely empty -
    a real corpus with no rulings filed yet (distinct from the undiscoverable-corpus case
    above), so the mint succeeds at 1."""
    (repo / "ruling").mkdir()
    rc = cli.main(["--mint", "ruling", str(repo)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "next ORG-SCOPE ruling id = 1" in out
    assert "NOT reserved or locked" in out
    assert "concurrently can claim the same integer" in out


def test_mint_project_scope_has_its_own_counter_no_200_floor(repo, capsys):
    """RULING-200 s2: a project counter is independent and has no reason to be pushed
    into the org band it does not share - proven here against a corpus that HAS landed
    RULING-200 (so the org band is genuinely live), confirming the project counter still
    ignores it entirely."""
    rd = repo / "ruling"
    _ruling(rd, "200", "band", scope="org", title="the band-establishing ruling")
    proj_rd = repo / "projects" / "ducktyper" / "ruling"
    _ruling(proj_rd, "003", "a", scope="project:ducktyper")
    nxt, homes, total = next_ruling_id(repo, project="ducktyper")
    assert nxt == 4
    org_nxt, _, _ = next_ruling_id(repo, project=None)
    assert org_nxt == 201  # unaffected by the project-scope file; floor holds off RULING-200


def test_mint_sow_matches_locate_streams_own_next_n(repo, capsys):
    # find_sow_roots requires <project>/sow/<stream>, NOT a bare <root>/sow/<stream> -
    # a project directory has to sit between root and sow/ for the walk to find it.
    sd = repo / "demo-project" / "sow" / "demo-stream"
    sd.mkdir(parents=True)
    (sd / "DEMO-STREAM-SOW-1-x.md").write_text(
        "---\nsow: demo-stream\nn: 1\nrev: a\nstatus: SHIPPED\ngenre: sow\nlanding_commit: self\n---\nbody\n",
        encoding="utf-8",
    )
    rc = cli.main(["--mint", "sow", "demo-stream", str(repo)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "next demo-stream SOW n = 2" in out


def test_mint_sow_missing_stream_name_fails_closed(repo, monkeypatch, capsys):
    """`--mint sow` with NOTHING after it (the next token is another flag, so nothing is
    consumed as a stream name) must refuse, not guess. cwd is pinned to a real corpus so
    root-discovery succeeds and the refusal under test is the ACTUAL one - a missing
    stream name, not an unrelated root-discovery failure."""
    monkeypatch.chdir(repo)
    rc = cli.main(["--mint", "sow"])
    cap = capsys.readouterr()
    out = cap.out + cap.err
    assert rc == 2
    assert "a stream name is required" in out


# -- SURVIVE: build_ruling_index / render_ruling_index, owner + tombstone --


def test_build_ruling_index_single_owner_no_tombstone(repo):
    rd = repo / "ruling"
    _ruling(rd, "050", "a", scope="org")
    entries = build_ruling_index(repo)
    assert len(entries["050"]) == 1
    assert entries["050"][0]["role"] == "owner"


def test_build_ruling_index_tombstone_from_minted_as(repo):
    """The worked example RULING-216 s3(2) names: an integer collides, the loser is
    renumbered, and `minted_as:` on the renumbered file makes the OLD integer resolve
    to both - the winner at its own number, and a tombstone pointing at the new one."""
    rd = repo / "ruling"
    _ruling(rd, "214", "winner", scope="org", title="the original owner of 214")
    _ruling(
        rd,
        "215",
        "loser-renumbered",
        scope="org",
        minted_as="214",
        title="minted as 214, renumbered after a same-day collision",
    )
    entries = build_ruling_index(repo)
    assert len(entries["214"]) == 2
    roles = {e["role"] for e in entries["214"]}
    assert roles == {"owner", "tombstone"}
    owner = next(e for e in entries["214"] if e["role"] == "owner")
    tomb = next(e for e in entries["214"] if e["role"] == "tombstone")
    assert "RULING-214-winner.md" in owner["path"]
    assert "RULING-215-loser-renumbered.md" in tomb["path"]
    # AND the renumbered file's OWN number (215) is unaffected - it still owns 215 outright.
    assert len(entries["215"]) == 1
    assert entries["215"][0]["role"] == "owner"


def test_build_ruling_index_minted_as_annotated_with_prose_still_keys_by_the_leading_integer(
    repo,
):
    """PAID (2026-08-07, measured against the real org corpus the first time a SECOND and
    THIRD renumber landed): minted_as is not reliably a bare integer. RULING-112 and
    RULING-114 both wrote a full annotated sentence into the field ('111 - RENUMBERED
    BEFORE LANDING. The quackverse Master minted RULING-111...'), using the field's
    latitude to record WHY inline. Using the whole string as the dict key put a paragraph
    in the table's Integer column. Only the leading integer is the identity."""
    rd = repo / "ruling"
    _ruling(
        rd,
        "111",
        "real-owner",
        scope="project:quackverse",
        title="the actual RULING-111",
    )
    _ruling(
        rd,
        "112",
        "renumbered-away-from-111",
        scope="project:ducktyper",
        minted_as="111 - RENUMBERED BEFORE LANDING. Long explanation with, a comma "
        "and | a pipe character that must never reach a markdown table cell",
        title="was minted as 111, renumbered before landing",
    )
    entries = build_ruling_index(repo)
    # the garbage key must NOT exist
    assert not any(k.startswith("111 -") for k in entries)
    assert len(entries["111"]) == 2
    tomb = next(e for e in entries["111"] if e["role"] == "tombstone")
    assert tomb["minted_as"] == "111"
    assert tomb["minted_as_note"] and tomb["minted_as_note"].startswith("RENUMBERED BEFORE LANDING")
    out = render_ruling_index(entries, "abc1234", "2026-08-07")
    # the render must be a valid table: no row's Integer column carries the prose,
    # and the pipe inside the annotation must never have reached the raw output unescaped
    for line in out.splitlines():
        if line.startswith("| `111"):
            assert line.count("|") == 5  # exactly 4 cells, unbroken by an embedded pipe


def test_build_ruling_index_self_referential_minted_as_is_not_a_phantom_tombstone(repo):
    """PHANTOM TOMBSTONE (reported by Master, 2026-08-07, found while verifying the
    previous fix): RULING-114's minted_as reads '114 - checked free at file time. 111 and
    113 were both taken by the quackverse Master DURING this session' - the file's OWN
    ruling: is 114. Nothing was renumbered; a peer seat used minted_as to record a
    near-collision it survived while KEEPING its number, good faith use of an
    underspecified field (RULING-216 s3(2) never said minted_as must differ from the
    file's own number). The old code tombstoned 114 under itself: 'renumbered away from
    114' on the file that IS 114, a false claim from the instrument that exists to stop
    false claims - measured live: 1 of the corpus's 3 real minted_as fields was this
    shape, a 33% false-positive rate on the survivability mechanism's own output.

    The fix is a guard, not a rejection: no tombstone is manufactured, and the real race
    evidence is NOT dropped - it surfaces as mint_provenance on the owner's own row."""
    rd = repo / "ruling"
    _ruling(
        rd,
        "114",
        "self-mint-note",
        scope="project:ducktyper",
        minted_as="114 - checked free at file time. 111 and 113 were both taken by "
        "the quackverse Master DURING this session",
        title="kept 114, recorded a near-collision",
    )
    entries = build_ruling_index(repo)
    # exactly ONE row under 114 - no phantom tombstone manufactured
    assert len(entries["114"]) == 1
    row = entries["114"][0]
    assert row["role"] == "owner"
    assert row["mint_provenance"] and row["mint_provenance"].startswith("checked free at file time")
    out = render_ruling_index(entries, "abc1234", "2026-08-07")
    line_114 = next(l for l in out.splitlines() if "RULING-114-self-mint-note.md" in l)
    assert "TOMBSTONE" not in line_114
    assert "renumbered away from 114" not in line_114
    assert "MINT-PROVENANCE" in line_114
    assert "checked free at file time" in line_114


def test_build_ruling_index_real_renumber_still_tombstones_when_integers_genuinely_differ(
    repo,
):
    """The guard must not overcorrect: a GENUINE renumber (minted_as names a DIFFERENT
    integer than the file's own) still gets a real tombstone - only the self-referential
    shape is suppressed."""
    rd = repo / "ruling"
    _ruling(rd, "214", "winner", scope="org")
    _ruling(rd, "215", "loser-renumbered", scope="org", minted_as="214")
    entries = build_ruling_index(repo)
    assert len(entries["214"]) == 2
    roles = {e["role"] for e in entries["214"]}
    assert roles == {"owner", "tombstone"}


def test_render_ruling_index_has_fence_and_tombstone_note(repo):
    rd = repo / "ruling"
    _ruling(rd, "214", "winner", scope="org")
    _ruling(rd, "215", "loser-renumbered", scope="org", minted_as="214")
    entries = build_ruling_index(repo)
    out = render_ruling_index(entries, "abc1234", "2026-08-07")
    assert out.startswith("<!-- RULING-INDEX:AUTO")
    assert out.rstrip().endswith("<!-- END RULING-INDEX -->")
    assert "TOMBSTONE" in out
    assert "Navigation, not evidence" in out
    assert "RULING-215-loser-renumbered.md" in out


def test_render_ruling_index_owner_of_a_tombstone_pair_is_not_mislabeled_legal_reuse(
    repo,
):
    """PAID (reported by Master, 2026-08-07, from the real corpus): RULING-214's OWNER row
    read 'multiple occupants (legal per-scope reuse, RULING-200 s2)' when its only
    co-occupant was RULING-215's TOMBSTONE, not a second scope's owner — a misleading note
    in the navigation index the mechanism exists to keep honest. An owner+tombstone pair is
    NOT the RULING-200 s2 shape (two OWNERS in different scopes); the owner row of a
    single-owner-plus-tombstone integer must carry no reuse claim at all."""
    rd = repo / "ruling"
    _ruling(rd, "214", "winner", scope="org")
    _ruling(rd, "215", "loser-renumbered", scope="org", minted_as="214")
    entries = build_ruling_index(repo)
    out = render_ruling_index(entries, "abc1234", "2026-08-07")
    owner_line = next(l for l in out.splitlines() if "RULING-214-winner.md" in l)
    assert "legal per-scope reuse" not in owner_line
    tomb_line = next(l for l in out.splitlines() if "RULING-215-loser-renumbered.md" in l)
    assert "TOMBSTONE" in tomb_line


def test_render_ruling_index_genuine_per_scope_reuse_still_labeled_legal(repo):
    """The fix must not overcorrect: TWO real owners in DIFFERENT scopes sharing an
    integer (the actual RULING-200 s2 shape, e.g. the 93/95/96/97 quartet) still needs
    its legal-reuse note - only a tombstone-explained co-occupancy loses it."""
    rd = repo / "ruling"
    _ruling(rd, "093", "org-owner", scope="org")
    proj_rd = repo / "projects" / "ducktyper" / "ruling"
    _ruling(proj_rd, "093", "project-owner", scope="project:ducktyper")
    entries = build_ruling_index(repo)
    out = render_ruling_index(entries, "abc1234", "2026-08-07")
    for l in out.splitlines():
        if "RULING-093" in l:
            assert "legal per-scope reuse" in l


def test_render_ruling_index_same_scope_multi_owner_is_flagged_not_called_legal(repo):
    """A theoretical shape DETECT does not cover (collision detection is org-scope only):
    two OWNERS sharing an integer in the SAME non-org scope. That is a real collision, not
    RULING-200 s2 reuse, and the index must never call it legal."""
    rd = repo / "ruling"
    _ruling(rd, "050", "a", scope="stream:demo")
    _ruling(rd, "050", "b", scope="stream:demo")
    entries = build_ruling_index(repo)
    out = render_ruling_index(entries, "abc1234", "2026-08-07")
    for l in out.splitlines():
        if "RULING-050" in l:
            assert "legal per-scope reuse" not in l
            assert "needs a human look" in l


def test_ruling_index_cli_writes_the_file_and_reports_counts(repo, capsys):
    rd = repo / "ruling"
    _ruling(rd, "214", "winner", scope="org")
    _ruling(rd, "215", "loser-renumbered", scope="org", minted_as="214")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    rc = cli.main(["--ruling-index", str(repo)])
    out = capsys.readouterr().out
    assert rc == 0
    target = repo / "ruling-index.md"
    assert target.is_file()
    body = target.read_text(encoding="utf-8")
    assert "TOMBSTONE" in body
    assert "1 tombstone(s)" in out


def test_full_demonstrated_round_trip_mint_collide_survive_citation_resolves(repo, capsys):
    """THE done_when, literally: mint -> collide -> renumber-with-minted_as -> index
    regenerated -> the OLD integer's row set still contains BOTH files, so a citation to
    the old integer resolves to something real instead of silence or a wrong document.

    RULING-218 s2: this repo fixture never lands RULING-200, so the org band never
    applies here - the demonstration runs at whatever integer a bare corpus's first mint
    actually returns (1), not a hardcoded 200. The race/collide/survive mechanics under
    test do not depend on which integer it is."""
    rd = repo / "ruling"
    (rd).mkdir()  # a real corpus with a ruling/ home that is, so far, empty
    # 1. MINT: read the next free integer live.
    rc = cli.main(["--mint", "ruling", str(repo)])
    mint_out = capsys.readouterr().out
    assert "next ORG-SCOPE ruling id = 1" in mint_out
    # 2. COLLIDE (for real, on disk): two seats both land RULING-001 the same day.
    # (_RULING_NAME_RE requires the zero-padded 3-digit filename shape every landed ruling
    # in the real corpus already uses, e.g. RULING-001 in profrodai itself - so the mint's
    # bare int (1) becomes the filename's padded form (001) exactly as an authoring seat
    # would do it by hand.)
    _ruling(rd, "001", "seat-a", scope="org", title="seat A's ruling, lands first")
    _ruling(rd, "001", "seat-b", scope="org", title="seat B's ruling, same integer")
    rc = cli.main(["--commit-check-corpus", str(repo)])
    detect_out = capsys.readouterr().out
    assert rc == 1
    assert "ruling-collision" in detect_out
    # 3. SURVIVE: renumber the loser (seat B) to the next free integer, append minted_as -
    #    a NEW field on an otherwise-untouched file, a legal RULING-004 append.
    loser = rd / "RULING-001-seat-b.md"
    winner_text = loser.read_text(encoding="utf-8")
    renumbered_text = winner_text.replace('ruling: "001"', 'ruling: "002"').replace(
        "scope: org\n", 'scope: org\nminted_as: "001"\n', 1
    )
    (rd / "RULING-002-seat-b.md").write_text(renumbered_text, encoding="utf-8")
    loser.unlink()
    # collision is gone now that only one file claims 001
    rc = cli.main(["--commit-check-corpus", str(repo)])
    out2 = capsys.readouterr().out
    assert rc == 0, out2
    # 4. Regenerate the index and confirm 001 resolves to BOTH candidates.
    entries = build_ruling_index(repo)
    assert len(entries["001"]) == 2
    roles = {e["role"] for e in entries["001"]}
    assert roles == {"owner", "tombstone"}
    owner = next(e for e in entries["001"] if e["role"] == "owner")
    tomb = next(e for e in entries["001"] if e["role"] == "tombstone")
    assert "RULING-001-seat-a.md" in owner["path"]
    assert "RULING-002-seat-b.md" in tomb["path"]
    # AND 002 is now a clean single owner in its own right.
    assert len(entries["002"]) == 1
