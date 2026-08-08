"""n-pattern per-project arming (Master ruling SOW-46/47): a declared-n: file with
a pre-canonical filename WARNs-to-backfill while its project is UNMIGRATED
(project_of None), and ERRORs once the project is CANONICAL (project_of non-None)."""

from zero_employee.core import check_n, extract_frontmatter, WARN

R = "/tmp/example-org/corpus"
FM = "---\nsow: quackverse-track-A\nn: 18\nschema_rev: 12\n---\nbody"


def _fm(s):
    return extract_frontmatter(s)


def sev(fs, code):
    return next((f.severity for f in fs if f.code == code), None)


def test_track_a_unmigrated_warns_not_errors(tmp_path):
    # the real track-a case: flat (project_of None) -> WARN, not ERROR (the 4 FAILs cleared)
    d = tmp_path / "quackverse" / "track-a"
    d.mkdir(parents=True)
    p = d / "SOW-TrackA-core-fs-completion-Rev18.md"
    p.write_text(FM)
    fs = check_n(p, _fm(FM), root=tmp_path)
    assert sev(fs, "n-pattern-premigration") == WARN
    assert sev(fs, "n-pattern") is None


def test_canonical_bad_filename_now_WARNS_per_RULING_093(tmp_path):
    """SUPERSEDED and updated, with the superseding ruling cited.

    The arming ruling (SOW-46/47) made a bad filename under a canonical <project>/sow/ path
    an ERROR. RULING-093 s2 supersedes that: the era-gate must key on the FILENAME's
    migration state, not on project_of(), because the physical restructure moved 313
    never-renamed files under <project>/sow/ and disarmed the grandfathering on files nobody
    had touched. MEASURED: it blocked a 190-file backfill that removed 135 failures.

    The ERROR arm is not softened away - it MOVED to --promote, which does the rename
    transactionally in git birth order and is the only thing that can fix a filename.
    """
    d = tmp_path / "sovereignagents" / "sow" / "ds"
    d.mkdir(parents=True)
    p = d / "badname-no-sow-marker.md"
    p.write_text(FM)
    fs = check_n(p, _fm(FM), root=tmp_path)
    assert sev(fs, "n-pattern-premigration") == WARN
    assert sev(fs, "n-pattern") is None, "093 s2: a legacy filename is WARN-pending-promote"
