"""V1-D 3rd-dimension: n-collision arms per-project (SOW-52 ruling, Option A).
Cross-stream flat-legacy collision -> WARN (namespace artifact migration resolves);
same-stream true duplicate -> ERROR (real, migration does not resolve).
Behavioral proof of Master's condition 4."""

from zero_employee.core import check_corpus, _stream_prefix


def _fm(n):
    return {"n": n}


def _codes(out):
    codes = {}
    for p, findings in out.items():
        for f in findings:
            codes.setdefault(f.code, []).append(p)
    return codes


def test_cross_stream_flat_collision_warns():
    # two DIFFERENT streams share n:34, both flat-legacy -> WARN, not ERROR
    files = [
        ("sow/docs-sort/DOCS-SORT-SOW-34-x.md", _fm(34)),
        ("sow/arch-sep/SEAM-2-Conversion2-Recon-Findings-Rev1.md", _fm(34)),
    ]
    codes = _codes(check_corpus(files, root="sow"))
    assert "n-collision-premigration" in codes, codes
    assert "n-collision" not in codes, f"cross-stream must NOT ERROR: {codes}"


def test_same_stream_flat_duplicate_errors():
    # SAME stream, two files at n:34 -> real duplicate -> ERROR
    files = [
        ("sow/docs-sort/DOCS-SORT-SOW-34-first.md", _fm(34)),
        ("sow/docs-sort/DOCS-SORT-SOW-34-second.md", _fm(34)),
    ]
    codes = _codes(check_corpus(files, root="sow"))
    assert "n-collision" in codes, f"same-stream dup MUST ERROR: {codes}"
    assert "n-collision-premigration" not in codes, codes


def test_mixed_group_errors_the_dup_warns_the_cross():
    # n:1 group: 2 HUD-RECOVERY (same-stream dup -> ERROR) + 1 LS-NOTATION (cross -> WARN)
    files = [
        ("sow/hud-recovery/HUD-RECOVERY-SOW-01-a.md", _fm(1)),
        ("sow/hud-recovery/HUD-RECOVERY-SOW-01-b.md", _fm(1)),
        ("sow/ls-notation/LS-NOTATION-SOW-01-c.md", _fm(1)),
    ]
    out = check_corpus(files, root="sow")
    codes = _codes(out)
    # the two HUD files ERROR; the LS file WARNs
    assert "n-collision" in codes and len(codes["n-collision"]) == 2, codes
    assert "n-collision-premigration" in codes and len(codes["n-collision-premigration"]) == 1, codes


def test_migrated_project_collision_still_errors():
    # canonical shape (project_of non-None): same-project n reuse stays ERROR (V1-D unchanged)
    files = [
        ("sow-repo/docs-sort/sow/t/DOCS-SORT-SOW-9-a.md", _fm(9)),
        ("sow-repo/docs-sort/sow/t/DOCS-SORT-SOW-9-b.md", _fm(9)),
    ]
    # note: project_of keys on '<proj>/sow/' — here 'docs-sort' is the project
    codes = _codes(check_corpus(files, root="sow-repo"))
    assert "n-collision" in codes, f"migrated same-project dup MUST ERROR: {codes}"


def test_stream_prefix_extraction():
    assert _stream_prefix("DOCS-SORT-SOW-34-x.md") == "DOCS-SORT"
    assert _stream_prefix("SEAM-2-Conversion2-Recon-Findings-Rev1.md") == "SEAM-2"
    assert _stream_prefix("HUD-RECOVERY-SOW-01-a.md") == "HUD-RECOVERY"
    assert _stream_prefix("FONT-INFRA-SOW-02-x.md") == "FONT-INFRA"


# ── SOW-53 Option B: rev-chain vs real-duplicate (Master's condition-4 proof) ──


def _fmr(n, rev):
    return {"n": n, "rev": rev}


def test_revchain_same_stream_same_n_passes():
    # HUD-RECOVERY n:1 rev a/c/d — one identity's rev-chain (schema-correct).
    # Distinct revs -> NOT a collision -> NO finding (the false positive SOW-53 fixed).
    files = [
        ("sow/hud-recovery/HUD-RECOVERY-SOW-01-locate.md", _fmr(1, "a")),
        ("sow/hud-recovery/HUD-RECOVERY-SOW-01-scene-rev-c.md", _fmr(1, "c")),
        ("sow/hud-recovery/HUD-RECOVERY-SOW-01-closeout.md", _fmr(1, "d")),
    ]
    out = check_corpus(files, root="sow")
    codes = _codes(out)
    assert "n-collision" not in codes, f"rev-chain must NOT ERROR: {codes}"
    assert "n-collision-premigration" not in codes, f"rev-chain is one stream, not cross-stream: {codes}"


def test_real_duplicate_same_stream_same_n_same_rev_errors():
    # SAME stream, SAME n, SAME rev (rev:a filed twice) -> real duplicate -> ERROR.
    files = [
        ("sow/hud-recovery/HUD-RECOVERY-SOW-01-a-first.md", _fmr(1, "a")),
        ("sow/hud-recovery/HUD-RECOVERY-SOW-01-a-second.md", _fmr(1, "a")),
    ]
    codes = _codes(check_corpus(files, root="sow"))
    assert "n-collision" in codes, f"repeated rev is a real duplicate, MUST ERROR: {codes}"


def test_norev_same_stream_same_n_still_errors():
    # No rev on either (both None) -> indistinguishable identities -> real duplicate -> ERROR.
    files = [
        ("sow/docs-sort/DOCS-SORT-SOW-34-first.md", {"n": 34}),
        ("sow/docs-sort/DOCS-SORT-SOW-34-second.md", {"n": 34}),
    ]
    codes = _codes(check_corpus(files, root="sow"))
    assert "n-collision" in codes, f"same-stream same-n no-rev pair MUST ERROR: {codes}"


def test_migrated_revchain_passes():
    # canonical shape, same project, same n, distinct revs -> rev-chain -> pass (V1-D + Option B)
    files = [
        ("r/docs-sort/sow/t/DOCS-SORT-SOW-9-a.md", _fmr(9, "a")),
        ("r/docs-sort/sow/t/DOCS-SORT-SOW-9-b.md", _fmr(9, "b")),
    ]
    codes = _codes(check_corpus(files, root="r"))
    assert "n-collision" not in codes, f"migrated rev-chain must pass: {codes}"
