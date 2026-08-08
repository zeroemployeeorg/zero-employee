"""Regression tests — the keystone rule, encoding the v0 proof cases."""

from zero_employee.core import extract_frontmatter, check_keystone, lint_file


def _fm(s):
    return extract_frontmatter(s)


GOOD = """---
sow: docs-sort
status: SHIPPED
ledger:
  - claim: a
    state: SHIPPED
    commit: repo@abc1234
    check: "wc -l file → 686"
---
body
"""

SEAM_EMPTY_CHECK = """---
sow: t
ledger:
  - claim: the-seam-is-complete
    state: SHIPPED
    commit: abc1234
    check:
---
body
"""

NO_COMMIT = """---
sow: t
ledger:
  - claim: x
    state: SHIPPED
    check: "has a check but no commit"
---
body
"""

CHECK_NONE_OK = """---
sow: t
ledger:
  - claim: taste
    state: SHIPPED
    commit: abc1234
    check: "none — human render verdict, no automated check"
---
body
"""

NO_FRONTMATTER = "# just a heading\nStatus: ACTIVE\n"


def test_good_passes():
    assert check_keystone(_fm(GOOD)) == []


def test_empty_check_is_seam_failure():
    findings = check_keystone(_fm(SEAM_EMPTY_CHECK))
    assert any("EMPTY check" in f for f in findings)


def test_missing_commit_fails():
    findings = check_keystone(_fm(NO_COMMIT))
    assert any("no commit" in f for f in findings)


def test_check_none_reason_passes():
    # explicit 'none — reason' is a valid, non-empty check
    assert check_keystone(_fm(CHECK_NONE_OK)) == []


def test_no_frontmatter_skips(tmp_path):
    p = tmp_path / "old.md"
    p.write_text(NO_FRONTMATTER)
    status, _ = lint_file(p)
    assert status == "SKIP"


def test_spaced_path(tmp_path):
    d = tmp_path / "dir with space"
    d.mkdir()
    p = d / "spaced SOW.md"
    p.write_text(GOOD)
    status, _ = lint_file(p)
    assert status == "PASS"
