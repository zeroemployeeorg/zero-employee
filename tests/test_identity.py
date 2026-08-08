"""Impl-B acceptance suite — n:/schema_rev: identity, era-aware. Both directions.

Fixtures mirror the REAL docs-sort corpus quirks found in recon DS3-RECON-02
(UPPERCASE prefix, -RevN legacy suffixes, pre-11 files with no n:) to prove the
checks are additive and grandfather legacy rather than break it.
"""

import pathlib
from zero_employee.core import (
    extract_frontmatter,
    check_n,
    check_schema_rev,
    check_corpus,
    parse_current_rev,
    lint_file,
    ERROR,
    WARN,
)


def fm(s):
    return extract_frontmatter(s)


def sev(findings, code):
    return next((f.severity for f in findings if f.code == code), None)


def write(p: pathlib.Path, sow="docs-sort", n=None, schema_rev=None, ledger=None):
    lines = ["---", f"sow: {sow}"]
    if n is not None:
        lines.append(f"n: {n}")
    if schema_rev is not None:
        lines.append(f"schema_rev: {schema_rev}")
    if ledger:
        lines.append(ledger)
    lines += ["---", "body"]
    p.write_text("\n".join(lines))
    return p


REV11 = fm("---\nsow: docs-sort\nn: 31\nschema_rev: 11\n---\nx")
LEGACY = fm("---\nsow: docs-sort\nstatus: DONE\n---\nx")  # pre-11: no n:, no schema_rev


# ── n: acceptance (N1–N8) ──────────────────────────────────────────
def test_N1_conformant_passes(tmp_path):
    p = write(tmp_path / "DOCS-SORT-SOW-31-implb.md", n=31, schema_rev=11)
    assert check_n(p, fm(p.read_text())) == []


def test_N2_n_mismatch_errors(tmp_path):
    p = write(tmp_path / "DOCS-SORT-SOW-27-foo.md", n=26, schema_rev=11)
    assert sev(check_n(p, fm(p.read_text())), "n-mismatch") == ERROR


def test_N3_revsuffix_errors(tmp_path):
    p = write(tmp_path / "DOCS-SORT-SOW-31-foo-Rev2.md", n=31, schema_rev=11)
    assert sev(check_n(p, fm(p.read_text())), "n-revsuffix") == ERROR


def test_N4_bad_pattern_unmigrated_warns(tmp_path):
    # Master ruling (SOW-46/47): a flat/unmigrated file with a bad filename WARNs-to-
    # backfill (project_of None), not ERROR. Canonical bad-name still ERRORs (see arming test).
    p = write(tmp_path / "docs-sort-31-foo.md", n=31, schema_rev=11)  # no -SOW-, flat
    assert sev(check_n(p, fm(p.read_text())), "n-pattern-premigration") == WARN
    assert sev(check_n(p, fm(p.read_text())), "n-pattern") is None


def test_N5_wrong_stream_errors(tmp_path):
    p = write(tmp_path / "worldprops-SOW-31-foo.md", sow="docs-sort", n=31, schema_rev=11)
    assert sev(check_n(p, fm(p.read_text())), "n-stream") == ERROR


def test_N5b_case_difference_is_accepted_silently(tmp_path):
    # F-1: UPPERCASE filename prefix vs lowercase sow: — matched case-insensitively,
    # NO finding (warning corpus-wide would be noise; normalization is Master's call)
    p = write(tmp_path / "DOCS-SORT-SOW-31-foo.md", sow="docs-sort", n=31, schema_rev=11)
    assert check_n(p, fm(p.read_text())) == []


def test_N6_collision_errors(tmp_path):
    a = write(tmp_path / "DOCS-SORT-SOW-31-a.md", n=31, schema_rev=11)
    b = write(tmp_path / "DOCS-SORT-SOW-31-b.md", n=31, schema_rev=11)
    out = check_corpus([(a, fm(a.read_text())), (b, fm(b.read_text()))])
    assert sev(out[a], "n-collision") == ERROR
    assert sev(out[b], "n-collision") == ERROR


def test_N7_gap_warns(tmp_path):
    files = []
    for nn in (28, 29, 30, 33):  # missing 31,32
        p = write(tmp_path / f"DOCS-SORT-SOW-{nn}-x.md", n=nn, schema_rev=11)
        files.append((p, fm(p.read_text())))
    out = check_corpus(files)
    assert any(f.code == "n-gap" and f.severity == WARN for fs in out.values() for f in fs)


def test_N8_fresh_increment_clean(tmp_path):
    files = []
    for nn in (28, 29, 30, 31):
        p = write(tmp_path / f"DOCS-SORT-SOW-{nn}-x.md", n=nn, schema_rev=11)
        files.append((p, fm(p.read_text())))
    out = check_corpus(files)
    assert all(f.severity != ERROR for fs in out.values() for f in fs)


# ── schema_rev: acceptance (S1–S5) ─────────────────────────────────
def test_S1_current_passes():
    assert check_schema_rev(fm("---\nn: 31\nschema_rev: 11\n---\nx"), 11) == []


def test_S2_stale_warns_not_errors():
    out = check_schema_rev(fm("---\nn: 5\nschema_rev: 8\n---\nx"), 11)
    assert sev(out, "schema-stale") == WARN
    assert all(f.severity != ERROR for f in out)


def test_S3_ahead_errors():
    assert (
        sev(
            check_schema_rev(fm("---\nn: 1\nschema_rev: 12\n---\nx"), 11),
            "schema-ahead",
        )
        == ERROR
    )


def test_S4_absent_on_rev11_sow_warns():
    assert sev(check_schema_rev({"sow": "x", "n": 31}, 11), "schema-missing") == WARN


def test_S4b_absent_on_legacy_is_silent():
    # legacy file (no n:) — no schema_rev nag, stays quiet (grandfathered)
    assert check_schema_rev(LEGACY, 11) == []


def test_S5_parse_current_rev_from_real_docdate():
    line = "DOC-DATE: 2026-07-11  ·  LAST-REVIEWED: 2026-07-11  ·  (Rev 11, 2026-07-11)  ·  REVIEW-CADENCE: per-sprint"
    assert parse_current_rev(line + "\n...body...") == 11


# ── K: additivity — the keystone must still bite through lint_file ──
SEAM = (
    "---\nsow: docs-sort\nn: 31\nschema_rev: 11\n"
    "ledger:\n  - claim: seam\n    state: SHIPPED\n    commit: abc\n    check:\n---\nbody"
)


def test_K1_keystone_still_bites_empty_check(tmp_path):
    p = tmp_path / "DOCS-SORT-SOW-31-seam.md"
    p.write_text(SEAM)
    status, findings = lint_file(p, current_rev=11)
    assert status == "FAIL"
    assert any(f.code == "keystone" and "EMPTY check" in f.message for f in findings)


def test_K3_valid_rev11_sow_passes(tmp_path):
    good = (
        "---\nsow: docs-sort\nn: 31\nschema_rev: 11\n"
        "ledger:\n  - claim: ok\n    state: SHIPPED\n    commit: repo@abc\n"
        '    check: "uv run pytest → green"\n---\nbody'
    )
    p = tmp_path / "DOCS-SORT-SOW-31-ok.md"
    p.write_text(good)
    status, findings = lint_file(p, current_rev=11)
    assert status == "PASS"
    assert all(f.severity != ERROR for f in findings)


# ── era-gating: the REAL legacy corpus must NOT be broken ──────────
def test_legacy_revsuffix_file_is_grandfathered(tmp_path):
    # DOCS-SORT-SOW-03-readme-seam-Rev1.md, pre-11 (no n:) — WARN backfill, never ERROR
    p = tmp_path / "DOCS-SORT-SOW-03-readme-seam-Rev1.md"
    p.write_text("---\nsow: docs-sort\nstatus: DONE\n---\nbody")
    status, findings = lint_file(p, current_rev=11)
    assert status == "PASS"
    assert all(f.severity != ERROR for f in findings)
    assert any(f.code == "n-missing" and f.severity == WARN for f in findings)


def test_relay_doc_is_skipped(tmp_path):
    # QV-RELAY-to-docs-sort-Rev1.md has no frontmatter → SKIP, not flagged (F-4)
    p = tmp_path / "QV-RELAY-to-docs-sort-Rev1.md"
    p.write_text("# relay note\nsome prose\n")
    status, _ = lint_file(p, current_rev=11)
    assert status == "SKIP"
