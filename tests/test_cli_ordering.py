"""V1-F: the queued CLI-ordering unit test (Fold-1 honest coverage gap, SOW-39).
Governance-docs-first: with --skill, the GOVERNANCE block must print BEFORE the
per-file corpus block. This was CLI-verified but never unit-tested; now it is."""

from zero_employee.cli import main

# main() takes a BARE arg list (no program name at [0]);
# only sys.argv is stripped. Do not prepend "sow-lint" (DS5-DIAG-262).

GOV_MARKER = "GOVERNANCE (graded first"
CORPUS_MARKERS = ["\nWARN: ", "\nFAIL: "]

# a stale skill (Rev 11 < canonical) -> produces a governance line
SKILL_STALE = "# Authoring a canonical SOW\n> **Teaches CLAUDE.md Rev 11** · synced 2026-07-11.\nbody\n"
# a minimal canonical CLAUDE.md so current_rev resolves to 12
CLAUDE_MD = "DOC-DATE: 2026-07-12 · LAST-REVIEWED: 2026-07-12 · (Rev 12, 2026-07-12)\nbody\n"
# a flat-legacy SOW with no project: -> produces a project-backfill WARN (corpus block prints)
SOW_WARN = "---\nsow: docs-sort\nn: 50\nschema_rev: 12\ncreated: 2026-07-10\n---\nbody"


def test_governance_prints_before_corpus(tmp_path, capsys):
    skill = tmp_path / "SKILL.md"
    skill.write_text(SKILL_STALE)
    claude = tmp_path / "CLAUDE.md"
    claude.write_text(CLAUDE_MD)
    sowdir = tmp_path / "sow" / "docs-sort"
    sowdir.mkdir(parents=True)
    (sowdir / "DOCS-SORT-SOW-50-x.md").write_text(SOW_WARN)
    rc = main(["--claude-md", str(claude), "--skill", str(skill), str(sowdir)])
    out = capsys.readouterr().out
    gi = out.find(GOV_MARKER)
    ci = min((out.find(m) for m in CORPUS_MARKERS if out.find(m) >= 0), default=-1)
    assert gi >= 0, f"governance block did not print:\n{out}"
    assert ci >= 0, f"corpus block did not print (fixture must WARN):\n{out}"
    assert gi < ci, f"governance ({gi}) must precede corpus ({ci}):\n{out}"


def test_governance_block_absent_without_skill(tmp_path, capsys):
    # no --skill -> no governance block at all (governance-first only when skill given)
    claude = tmp_path / "CLAUDE.md"
    claude.write_text(CLAUDE_MD)
    sowdir = tmp_path / "sow" / "docs-sort"
    sowdir.mkdir(parents=True)
    (sowdir / "DOCS-SORT-SOW-50-x.md").write_text(SOW_WARN)
    main(["--claude-md", str(claude), str(sowdir)])
    out = capsys.readouterr().out
    assert GOV_MARKER not in out
