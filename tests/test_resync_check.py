"""RULING-097 s3: --resync-check. The TRIGGER the propagation mechanism lacked.

The machinery (re-derivation) and the check (UPSTREAM-SHA) both existed; nothing said
WHEN to run. These pin the four verdicts, especially SKIP - a doctrine file with no
machine-written marker is locally authored and must NEVER be re-derived, which is the
rule a destroyed BOOT-SPARRING paid for (example-org/RULING-001 A3).
"""

import hashlib
from zero_employee.core import resync_check, unwatched_genres


def _corpus(tmp_path):
    up = tmp_path / "up"
    dn = tmp_path / "dn"
    for r in (up, dn):
        (r / "authoring").mkdir(parents=True)
        (r / "roles").mkdir(parents=True)
    return up, dn


def _write(root, rel, body):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_matching_hash_is_CURRENT(tmp_path):
    up, dn = _corpus(tmp_path)
    src = _write(up, "authoring/a-SKILL.md", "canonical body\n")
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    _write(dn, "authoring/a-SKILL.md", f"UPSTREAM-SHA: {sha}\nderived body\n")
    assert [r[1] for r in resync_check(dn, up)] == ["CURRENT"]


def test_upstream_moved_is_STALE_and_reports_BOTH_hashes(tmp_path):
    up, dn = _corpus(tmp_path)
    src = _write(up, "authoring/a-SKILL.md", "OLD\n")
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    _write(dn, "authoring/a-SKILL.md", f"UPSTREAM-SHA: {sha}\nderived\n")
    src.write_text("NEW - a fold landed upstream\n", encoding="utf-8")
    rel, verdict, recorded, current = resync_check(dn, up)[0]
    assert verdict == "STALE"
    assert recorded == sha and current != sha, "both hashes must be reported, not just a flag"


def test_a_locally_authored_file_is_SKIP_never_re_derived(tmp_path):
    """The BOOT-SPARRING rule: no machine-written marker => not ours to re-derive."""
    up, dn = _corpus(tmp_path)
    _write(up, "roles/BOOT-SPARRING.md", "upstream version\n")
    _write(
        dn,
        "roles/BOOT-SPARRING.md",
        "# BOOT - SPARRING (this corpus, purpose-authored)\n",
    )
    assert [r[1] for r in resync_check(dn, up)] == ["SKIP"]


def test_a_PROSE_mention_of_the_banner_does_not_make_a_file_inherited(tmp_path):
    """v2 keyed on a prose phrase; a marker must be machine-written to be a marker."""
    up, dn = _corpus(tmp_path)
    _write(up, "roles/BOOT-SPARRING.md", "upstream\n")
    _write(
        dn,
        "roles/BOOT-SPARRING.md",
        "Your INHERITED DOCTRINE attestation law, discussed here in prose.\n",
    )
    assert [r[1] for r in resync_check(dn, up)] == ["SKIP"]


def test_marker_present_but_upstream_gone_is_MISSING_UPSTREAM(tmp_path):
    up, dn = _corpus(tmp_path)
    _write(dn, "authoring/gone-SKILL.md", "UPSTREAM-SHA: " + "0" * 64 + "\nbody\n")
    assert [r[1] for r in resync_check(dn, up)] == ["MISSING-UPSTREAM"]


def test_non_doctrine_dirs_are_not_scanned(tmp_path):
    """A SOW is not inherited doctrine; the check must not report on the whole corpus."""
    up, dn = _corpus(tmp_path)
    (dn / "projects").mkdir()
    _write(dn, "projects/a-SOW.md", "UPSTREAM-SHA: " + "0" * 64 + "\n")
    assert resync_check(dn, up) == []


# DS6-CHARTER-03 item 6: a genre added AFTER _DOCTRINE_DIRS was written must not be
# structurally invisible - MEASURED live: --resync-check reported example-org/org CURRENT
# with 0 STALE while intake/ existed upstream and was never walked at all.
# "intake" is now a fourth entry in _DOCTRINE_DIRS, so it is walked exactly like the
# historic three - these two tests pin that it is genuinely covered, not just present
# in the tuple's source text.
def test_intake_is_now_covered_and_graded_SKIP_without_a_marker(tmp_path):
    up, dn = _corpus(tmp_path)
    _write(up, "intake/README.md", "the intake ritual doc\n")
    _write(dn, "intake/README.md", "a locally-authored copy with no marker\n")
    # Before the fix this returned [] - correct CURRENT-with-0-STALE, but for the wrong
    # reason: the file was never even seen. Now it is seen and correctly graded SKIP
    # (no machine-written marker - never silently assumed synced).
    assert [r[1] for r in resync_check(dn, up)] == ["SKIP"]


def test_intake_with_a_real_marker_is_graded_CURRENT_or_STALE_like_any_other(tmp_path):
    up, dn = _corpus(tmp_path)
    src = _write(up, "intake/README.md", "canonical intake ritual\n")
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    _write(dn, "intake/README.md", f"UPSTREAM-SHA: {sha}\nderived\n")
    assert [r[1] for r in resync_check(dn, up)] == ["CURRENT"]


def test_the_historic_floor_still_applies_when_upstream_root_is_unwalkable(tmp_path):
    """upstream_root pointing nowhere real must not silently disable the check entirely -
    the four named dirs remain the floor."""
    up, dn = _corpus(tmp_path)
    _write(dn, "roles/BOOT-SPARRING.md", "no marker\n")
    missing_upstream_root = tmp_path / "does-not-exist"
    assert [r[1] for r in resync_check(dn, missing_upstream_root)] == ["SKIP"]


# ── unwatched_genres: visibility WITHOUT grading (the false-positive-flood lesson) ──
def test_unwatched_genres_names_an_upstream_dir_resync_check_does_not_walk(tmp_path):
    up, dn = _corpus(tmp_path)
    _write(up, "ruling/RULING-001-x.md", "a ruling, never inherited doctrine\n")
    assert unwatched_genres(up) == ["ruling"]


def test_unwatched_genres_is_empty_once_a_dir_joins_DOCTRINE_DIRS(tmp_path):
    up, dn = _corpus(tmp_path)
    _write(up, "intake/README.md", "covered by the floor already\n")
    assert unwatched_genres(up) == []


def test_unwatched_genres_ignores_a_directory_with_no_md_files(tmp_path):
    up, dn = _corpus(tmp_path)
    (up / "empty-dir").mkdir()
    assert unwatched_genres(up) == []


def test_unwatched_genres_accepts_a_custom_floor_for_testing_the_boundary(tmp_path):
    """The false-positive-flood regression, pinned directly: a naive discovery that swept
    in EVERY upstream top-level .md-bearing dir reported projects/ruling/learnings/tools
    as doctrine on the real org corpus (1100 files where 23 was correct). This function
    must report them as UNWATCHED (advisory), never fold them into resync_check's walk."""
    up, dn = _corpus(tmp_path)
    _write(up, "projects/quackverse/sow/s/f.md", "a SOW, not doctrine\n")
    _write(up, "tools/stream-instruments/README.md", "an instrument note, not doctrine\n")
    # tools is in _DOCTRINE_DIRS, so unwatched_genres only names non-doctrine dirs like projects/
    assert set(unwatched_genres(up)) == {"projects"}
    # and, decisively, resync_check itself never walks stream-instruments or projects even with a fake marker:
    _write(dn, "projects/quackverse/sow/s/f.md", "UPSTREAM-SHA: " + "0" * 64 + "\n")
    _write(dn, "tools/stream-instruments/README.md", "UPSTREAM-SHA: " + "0" * 64 + "\n")
    assert resync_check(dn, up) == []


# ── SOW-24: tools, roles, and script paths cross-repo sync index ──────
def test_tools_hooks_and_doctrine_scripts_are_indexed(tmp_path):
    up, dn = _corpus(tmp_path)
    sh_src = _write(up, "tools/hooks/zeo-digest.sh", "#!/bin/bash\necho digest\n")
    sha = hashlib.sha256(sh_src.read_bytes()).hexdigest()
    _write(
        dn,
        "tools/hooks/zeo-digest.sh",
        f"# UPSTREAM-SHA: {sha}\n#!/bin/bash\necho digest\n",
    )

    doc_src = _write(up, "tools/doctrine/resync.sh", "#!/bin/bash\necho resync\n")

    rows = resync_check(dn, up)
    res_dict = {r[0]: r[1] for r in rows}
    assert res_dict["tools/hooks/zeo-digest.sh"] == "CURRENT"
    assert res_dict["tools/doctrine/resync.sh"] == "MISSING-TARGET"


def test_stream_instruments_is_local_evidence_and_not_indexed(tmp_path):
    up, dn = _corpus(tmp_path)
    _write(up, "tools/stream-instruments/inst.py", "print('instrument')\n")
    _write(dn, "tools/stream-instruments/inst.py", "# UPSTREAM-SHA: " + "0" * 64 + "\n")
    assert resync_check(dn, up) == []


def test_learnings_ruling_projects_are_local_evidence_and_not_indexed(tmp_path):
    up, dn = _corpus(tmp_path)
    _write(dn, "learnings/master/note.md", "UPSTREAM-SHA: " + "0" * 64 + "\n")
    _write(dn, "ruling/RULING-001.md", "UPSTREAM-SHA: " + "0" * 64 + "\n")
    _write(dn, "projects/p/sow/s.md", "UPSTREAM-SHA: " + "0" * 64 + "\n")
    assert resync_check(dn, up) == []
