"""check_sow_repo_placeholder: `sow_repo`/`work_repo` are `Any`-typed in
schemas/sow.py (deliberately -- extra="ignore", every field permissive, so the
live corpus stays gradeable across many real naming conventions). That means
NOTHING upstream could ever fail on the packaged scaffold DEFAULT
(sow_authoring.py's DEFAULT_SOW_REPO = "example-org/org") surviving unedited
into a real filed SOW.

MEASURED live (ducktyper-ai/org, 2026-08-17), reported by a peer Master: all
six of that corpus's real cold-start filings carried
`sow_repo: example-org/org` against a real remote of `ducktyper-ai/org`, and
every one graded GREEN. The peer had to VOID the field by ruling because they
could not fix it upstream and would not hand-edit a landed record. "A gate
that cannot fail on a field is not gating that field."
"""

from __future__ import annotations

import zero_employee.core as core


def _fm(**overrides):
    base = {
        "sow": "some-stream",
        "n": 1,
        "schema_rev": 17,
        "status": "FINDING",
        "genre": "sow",
        "created": "2026-08-17",
        "updated": "2026-08-17",
    }
    base.update(overrides)
    return base


def test_falsification_the_literal_placeholder_previously_passed_clean(tmp_path):
    """Confirms the gap: BEFORE this check existed, nothing in grade_sow /
    check_n / check_schema_rev / check_project / check_b2 looked at sow_repo
    at all -- the placeholder was invisible to every one of them. This test
    calls those directly (bypassing the new check) to prove the OLD chain
    truly had no opinion on the value."""
    from zero_employee.schemas import grade_sow

    fm = _fm(sow_repo="example-org/org", work_repo="example-org/quackvideo")
    findings = grade_sow(fm)
    codes = {f.code for f in findings}
    assert "sow-repo-placeholder" not in codes, "grade_sow must not itself know about this check (wired separately)"
    assert "work-repo-placeholder" not in codes


def test_check_sow_repo_placeholder_warns_on_the_literal_default(tmp_path):
    fm = _fm(sow_repo="example-org/org")
    findings = core.check_sow_repo_placeholder("SOME-SOW-01-x.md", fm)
    codes = {f.code for f in findings}
    assert "sow-repo-placeholder" in codes
    assert all(f.severity == core.WARN for f in findings), "must WARN, never FAIL — many corpora legitimately differ"


def test_check_sow_repo_placeholder_warns_on_the_work_repo_default_prefix(tmp_path):
    fm = _fm(work_repo="example-org/quackvideo")
    findings = core.check_sow_repo_placeholder("SOME-SOW-01-x.md", fm)
    codes = {f.code for f in findings}
    assert "work-repo-placeholder" in codes


def test_check_sow_repo_placeholder_silent_on_a_real_value(tmp_path):
    fm = _fm(sow_repo="ducktyper-ai/org", work_repo="quackvideo")
    findings = core.check_sow_repo_placeholder("SOME-SOW-01-x.md", fm)
    assert findings == []


def test_lint_file_wires_the_check_in_as_a_warn_not_a_fail(tmp_path):
    """End-to-end: a real file on disk with the placeholder still PASSES (WARN,
    not ERROR) -- this must not retroactively fail every SOW the tool's own
    current default already wrote, only surface the gap."""
    (tmp_path / "claude-md").mkdir(parents=True)
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("Rev 17\n")
    d = tmp_path / "quackvideo" / "sow" / "some-stream"
    d.mkdir(parents=True)
    f = d / "SOME-STREAM-SOW-01-x.md"
    f.write_text(
        "---\nsow: some-stream\nn: 1\nschema_rev: 17\nproject: quackvideo\n"
        "status: FINDING\nlifecycle: RECON\ngenre: sow\ncreated: 2026-08-17\n"
        "updated: 2026-08-17\nsow_repo: example-org/org\nwork_repo: example-org/quackvideo\n"
        "---\nbody\n"
    )
    status, findings = core.lint_file(f, root=tmp_path)
    assert status != "FAIL", f"a placeholder sow_repo must WARN, not FAIL: {findings}"
    codes = {fi.code for fi in findings}
    assert "sow-repo-placeholder" in codes
    assert "work-repo-placeholder" in codes
