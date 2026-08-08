"""V1-E / F-A: the -Rev\\d suffix check must distinguish a true trailing chain-marker
(capital-R -RevN, 125 in the corpus) from a descriptive slug word (lowercase -revN,
the SOW-28 impl-a-skill-rev11 case — the ONLY one, DS4-CORPUS-FA-41). This distinction
was UNTESTED before v1; test_N3 only covered the true-positive. Pin both ends."""

from zero_employee.core import check_n, extract_frontmatter, ERROR


def _fm(s):
    return extract_frontmatter(s)


def sev(findings, code):
    return next((f.severity for f in findings if f.code == code), None)


FM11 = "---\nsow: docs-sort\nn: 28\nschema_rev: 12\n---\nbody"


def test_FA_descriptive_lowercase_rev_slug_NOT_flagged(tmp_path):
    # SOW-28 real case: '-rev11' is descriptive ('skill for Rev 11'), NOT a chain-suffix
    p = tmp_path / "DOCS-SORT-SOW-28-impl-a-skill-rev11.md"
    p.write_text(FM11)
    assert sev(check_n(p, _fm(FM11)), "n-revsuffix") is None  # must NOT flag


def test_FA_true_capital_Rev_chain_suffix_STILL_flagged(tmp_path):
    # preserve N3: a real -Rev2 chain-suffix must still ERROR
    fm = "---\nsow: docs-sort\nn: 31\nschema_rev: 12\n---\nbody"
    p = tmp_path / "DOCS-SORT-SOW-31-foo-Rev2.md"
    p.write_text(fm)
    assert sev(check_n(p, _fm(fm)), "n-revsuffix") == ERROR  # must STILL flag


def test_FA_legacy_capital_Rev1_still_flagged(tmp_path):
    fm = "---\nsow: docs-sort\nn: 12\nschema_rev: 12\n---\nbody"
    p = tmp_path / "DOCS-SORT-SOW-12-sowsystem-landed-Rev1.md"
    p.write_text(fm)
    assert sev(check_n(p, _fm(fm)), "n-revsuffix") == ERROR
