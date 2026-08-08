"""V1-A acceptance — project_of() derives the project axis from PATH (ground).
Fixtures mirror the REAL repo path shapes; space-safety at lint_file level is
already covered by test_keystone.test_spaced_path; this suite covers derivation."""

from zero_employee.core import project_of

ROOT = "/tmp/example-org/corpus"


def test_P1_flat_legacy_absolute_is_none():
    assert project_of(f"{ROOT}/sow/docs-sort/x.md", root=ROOT) is None


def test_P2_flat_legacy_relative_is_none():
    assert project_of("sow/docs-sort/x.md") is None


def test_P3_flat_legacy_spaced_task_is_none():
    assert project_of(f"{ROOT}/sow/directional facing/z.md", root=ROOT) is None


def test_P4_canonical_absolute_with_root():
    assert project_of(f"{ROOT}/sovereignagents/sow/docs-sort/x.md", root=ROOT) == "sovereignagents"


def test_P5_canonical_relative():
    assert project_of("sovereignagents/sow/docs-sort/x.md") == "sovereignagents"


def test_P6_canonical_quackverse():
    assert project_of(f"{ROOT}/quackverse/sow/track-a/y.md", root=ROOT) == "quackverse"


def test_P7_canonical_spaced_task():
    assert project_of("sovereignagents/sow/directional facing/z.md") == "sovereignagents"


def test_P8_bare_file_no_sow_segment_is_none():
    assert project_of("DOCS-SORT-SOW-44.md") is None


def test_P9_path_outside_root_falls_back_to_tail_parse():
    assert project_of("quackverse/sow/track-a/y.md", root="/some/other/root") == "quackverse"
