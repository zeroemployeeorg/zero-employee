"""defect (l): the board reports 0 projects when a corpus nests under projects/.

MEASURED at GM-PRE-181 on a clone: baseline 7 projects -> full restructure 0 projects, while
`failed` stayed 21. The identical count is NOT evidence of safety - with project None
everywhere, every file takes the flat-legacy branch, so n-collision reverts to filename-prefix
grouping. Same number, different checks, different meaning.
"""

from zero_employee.core import project_of, _stream_of


def test_projects_container_is_stripped():
    assert project_of("projects/ducktyper/sow/acting/A-SOW-1-x.md") == "ducktyper"


def test_the_FLAT_layout_still_resolves():
    assert project_of("ducktyper/sow/acting/A-SOW-1-x.md") == "ducktyper"


def test_a_true_flat_legacy_file_is_STILL_None():
    """The pre-migration shape must keep returning None - SOW-52's branch depends on it."""
    assert project_of("sow/acting/A-SOW-1-x.md") is None


def test_an_absolute_path_with_a_root_still_resolves():
    assert project_of("/repo/ducktyper/sow/t/A-SOW-1-x.md", root="/repo") == "ducktyper"


def test_absolute_projects_container_resolves():
    assert project_of("/repo/projects/quackverse/sow/rh/A-SOW-1-x.md", root="/repo") == "quackverse"


def test_stream_still_resolves_under_the_container():
    assert _stream_of("projects/ducktyper/sow/acting/A-SOW-1-x.md") == "ACTING"
