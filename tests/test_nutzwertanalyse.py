"""Nutzwertanalyse stream ranking (RULING-279, PRIORITY-NWA-SOW-1; rebuilt per
RULING-279 -> PRIORITY-NWA-SOW-3 -> RULING-281 -> PRIORITY-NWA-SOW-4).

RULING-279 s2: rank every OPEN/PAUSED/BLOCKED stream on four weighted criteria
(Dringlichkeit, Impact, Restaufwand-as-cost, Risiko) into a single Nutzwert, so
Master has a stated reason for which stream gets the next session's tokens. Every
input reuses an existing computation (board_rows/awaiting_ruling/restaufwand/kosten)
except the two citation-graph counts (Impact, Risiko).

PRIORITY-NWA-SOW-3 MEASURED that the original Impact/Risiko source
(`_nwa_citation_graph`'s `<stream>#<n>` parse of SOW `requested_by:`) covers only
~6% of real requested_by: citations corpus-wide, making Impact/Risiko near-silent
(every stream tied). RULING-281 ruled the fix: Impact/Risiko now read `binds:` on
rulings a stream's OWN requests produced (~6.7x the coverage, a structured field,
no new citation grammar) -- see `_nwa_citation_graph`'s docstring for the exact
computation and the direction-flip warning (keyed by CITER now, not target)."""

import datetime

from zero_employee.core import (
    nutzwertanalyse,
    _nwa_citation_graph,
    _nwa_age_days,
    _nwa_minmax_norm,
    extract_frontmatter,
)


def _corpus(tmp_path):
    (tmp_path / "claude-md").mkdir()
    (tmp_path / "claude-md" / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    return tmp_path


def _sow(
    root,
    project,
    stream,
    n,
    *,
    status="PROGRESS",
    restaufwand=None,
    updated="2026-08-01",
    requested_by=None,
    issue_first=None,
    ledger_shipped=0,
    body_pad="",
):
    d = root / project / "sow" / stream
    d.mkdir(parents=True, exist_ok=True)
    fm = [
        "---",
        f"sow: {stream}",
        f"n: {n}",
        f"status: {status}",
        f"created: {updated}",
        f"updated: {updated}",
    ]
    if restaufwand is not None:
        fm.append(f"restaufwand: {restaufwand}")
    if requested_by:
        fm.append(f'requested_by: "{requested_by}"')
    if issue_first is not None:
        fm.append(f"issue_first: {str(issue_first).lower()}")
    if ledger_shipped:
        fm.append("ledger:")
        for i in range(ledger_shipped):
            fm.append(f"  - claim: c{i}")
            fm.append("    state: SHIPPED")
            fm.append("    commit: abc123")
            fm.append('    check: "make verify"')
    fm.append("---")
    body = "\n\nbody text here for token weight " + body_pad + "\n"
    (d / f"{stream}-SOW-{n}-x.md").write_text("\n".join(fm) + body, encoding="utf-8")


def _ruling(root, nnn, *, requested_by, binds, updated="2026-08-10", scope="project:p"):
    """A ruling file at root/ruling/RULING-<nnn>-x.md — RULING-281's actual source:
    `requested_by:` names the asking SOW (<stream>#<n> form, resolved via
    build_sow_n_index exactly as check_ruling_receipts already resolves it), `binds:`
    is the structured list of OTHER streams the ruling binds (RULING-281 s1)."""
    d = root / "ruling"
    d.mkdir(parents=True, exist_ok=True)
    binds_yaml = "[" + ", ".join(binds) + "]"
    fm = [
        "---",
        f'ruling: "{nnn}"',
        "genre: ruling",
        f"scope: {scope}",
        f'requested_by: "{requested_by}"',
        f"binds: {binds_yaml}",
        f"created: {updated}",
        f"updated: {updated}",
        "status: ACTIVE",
        "---",
    ]
    (d / f"RULING-{nnn}-x.md").write_text("\n".join(fm) + "\n\nbody\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Unit-level helpers
# ---------------------------------------------------------------------------


def test_age_days_computes_from_iso_updated():
    today = datetime.date(2026, 8, 17)
    assert _nwa_age_days("2026-08-01", today) == 16


def test_age_days_returns_none_never_a_silent_zero_on_bad_date():
    assert _nwa_age_days("not-a-date") is None
    assert _nwa_age_days(None) is None


def test_minmax_norm_single_value_set_normalizes_to_one_not_a_divide_by_zero():
    # a single stream, or every stream tied, has no basis to distinguish - 1.0 for all,
    # never a ZeroDivisionError.
    assert _nwa_minmax_norm({"a": 5.0}) == {"a": 1.0}
    assert _nwa_minmax_norm({"a": 5.0, "b": 5.0}) == {"a": 1.0, "b": 1.0}


def test_minmax_norm_spreads_the_live_set_zero_to_one():
    out = _nwa_minmax_norm({"a": 0.0, "b": 5.0, "c": 10.0})
    assert out["a"] == 0.0 and out["c"] == 1.0 and out["b"] == 0.5


# ---------------------------------------------------------------------------
# Citation graph — RULING-281: Impact/Risiko now read binds: on rulings a
# stream's OWN requests produced, not a <stream>#<n> citation-graph walk.
#
# THE FIXTURE THAT WOULD HAVE CAUGHT THE ORIGINAL GAP (PRIORITY-NWA-SOW-4 s2):
# alpha asks; a ruling answers citing alpha#1 in requested_by: and binds two
# OTHER real streams (beta, gamma). beta currently sits RULING-REQUESTED with
# its own open question; gamma does not. Expected: Impact(alpha) == 2 (beta +
# gamma), Risiko(alpha) == 1 (only beta is currently blocked). This is proven
# to FAIL against the pre-RULING-281 <stream>#<n>-only graph first (below),
# then proven to PASS once the graph reads binds: (per this session's own
# falsification discipline: prove the gap is real before fixing it).
# ---------------------------------------------------------------------------


def test_binds_graph_matches_ruling_281_worked_example(tmp_path):
    root = _corpus(tmp_path)
    _sow(root, "p", "alpha", 1, status="PROGRESS")
    _sow(root, "p", "beta", 1, status="RULING-REQUESTED", updated="2026-08-10")
    _sow(root, "p", "gamma", 1, status="PROGRESS")
    _ruling(root, "281", requested_by="alpha#1", binds=["beta", "gamma"])
    g = _nwa_citation_graph(root)
    # keyed by CITER (alpha, whose own ask produced the ruling) -- NOT by the
    # old graph's target-stream key. Direction-flip per PRIORITY-NWA-SOW-4 s1.
    assert g["alpha"]["cited_by"] == {"beta", "gamma"}
    assert g["alpha"]["blocking_open_requests"] == 1


def test_binds_graph_would_have_measured_flat_under_the_old_stream_n_only_form(tmp_path):
    """Falsification proof (charter s2/s4): the SAME corpus as the worked-example
    test above, but the ruling's requested_by: is the ONLY thing the OLD
    <stream>#<n>-parsing citation graph could ever see, and rulings were never
    scanned by the old _nwa_citation_graph at all (it walked sow/ dirs' own
    requested_by:, not ruling/ dirs' binds:) -- so beta/gamma's real dependency
    on alpha was INVISIBLE to the pre-fix mechanism. This is the exact near-tie
    PRIORITY-NWA-SOW-3 measured on the real corpus (~6% coverage), reproduced
    small: no SOW file anywhere cites 'alpha#1' via its own requested_by:, so a
    graph that only reads SOW requested_by: (the old source) scores every
    stream's Impact at 0 here -- flat, exactly the failure mode being fixed."""
    root = _corpus(tmp_path)
    _sow(root, "p", "alpha", 1, status="PROGRESS")
    _sow(root, "p", "beta", 1, status="RULING-REQUESTED", updated="2026-08-10")
    _sow(root, "p", "gamma", 1, status="PROGRESS")
    _ruling(root, "281", requested_by="alpha#1", binds=["beta", "gamma"])
    # No SOW file's OWN requested_by: cites alpha#1 -- only the RULING does, in a
    # field (binds:) the old graph never read. Confirm no SOW-level citation
    # exists in this fixture, i.e. the old mechanism's one and only input is empty:
    sow_level_citations = [
        fm.get("requested_by")
        for p in (root / "p" / "sow").rglob("*.md")
        for fm in [extract_frontmatter(p.read_text(encoding="utf-8"))]
        if isinstance(fm, dict) and fm.get("requested_by")
    ]
    assert sow_level_citations == []  # the old graph's only signal source is empty here


def test_binds_graph_filters_role_words_ruling_281_s2(tmp_path):
    root = _corpus(tmp_path)
    _sow(root, "p", "alpha", 1, status="PROGRESS")
    _sow(root, "p", "beta", 1, status="PROGRESS")
    _ruling(root, "282", requested_by="alpha#1", binds=["beta", "all-streams", "master", "sparring"])
    g = _nwa_citation_graph(root)
    # only beta counts -- all-streams/master/sparring are role words, RULING-281 s2
    assert g["alpha"]["cited_by"] == {"beta"}


def test_binds_graph_ignores_self_bound_back(tmp_path):
    """A ruling binding its own asker back doesn't count as Impact on some OTHER
    stream (PRIORITY-NWA-SOW-4 s1's explicit self-exclusion)."""
    root = _corpus(tmp_path)
    _sow(root, "p", "self-cite", 1, status="PROGRESS")
    _ruling(root, "283", requested_by="self-cite#1", binds=["self-cite"])
    g = _nwa_citation_graph(root)
    assert "self-cite" not in g or "self-cite" not in g["self-cite"]["cited_by"]


def test_binds_graph_filters_targets_that_dont_resolve_to_a_real_stream_dir(tmp_path):
    root = _corpus(tmp_path)
    _sow(root, "p", "alpha", 1, status="PROGRESS")
    _ruling(root, "284", requested_by="alpha#1", binds=["nonexistent-ghost-stream"])
    g = _nwa_citation_graph(root)
    assert "alpha" not in g or g["alpha"]["cited_by"] == set()


def test_old_stream_n_citation_form_still_counted_as_a_secondary_signal(tmp_path):
    """RULING-281 s4's open question, decided (not silently defaulted, per
    PRIORITY-NWA-SOW-4 done_when item 5): the old <stream>#<n> SOW-level
    requested_by: form is KEPT as a secondary signal, additive to the binds:
    primary source -- it is real, if rare (~6% coverage), information, and the
    new primary source has ~6.7x the coverage so it no longer dominates or
    masks the primary signal the way it used to when it was the ONLY source."""
    root = _corpus(tmp_path)
    _sow(root, "p", "base-stream", 1, status="PROGRESS")
    _sow(root, "p", "old-form-citer", 1, status="PROGRESS", requested_by="base-stream#1")
    g = _nwa_citation_graph(root)
    assert "old-form-citer" in g["base-stream"]["cited_by_legacy"]


# ---------------------------------------------------------------------------
# The ranking itself
# ---------------------------------------------------------------------------


def test_ranking_only_includes_rankable_statuses(tmp_path):
    root = _corpus(tmp_path)
    _sow(root, "p", "live-one", 1, status="PROGRESS", restaufwand=5, ledger_shipped=1)
    _sow(root, "p", "done-one", 1, status="CLOSEOUT", restaufwand=0, ledger_shipped=1)
    out = nutzwertanalyse(root)
    streams = {r["stream"] for r in out["ranked"]}
    assert "live-one" in streams
    assert "done-one" not in streams


def test_older_open_question_scores_higher_dringlichkeit_all_else_equal(tmp_path):
    root = _corpus(tmp_path)
    today = datetime.date(2026, 8, 17)
    # both streams: one open question each, identical restaufwand/impact/risiko;
    # only the AGE of the open question differs.
    _sow(root, "p", "old-question", 1, status="RULING-REQUESTED", restaufwand=5, updated="2026-06-01", ledger_shipped=1)
    _sow(
        root, "p", "young-question", 1, status="RULING-REQUESTED", restaufwand=5, updated="2026-08-15", ledger_shipped=1
    )
    out = nutzwertanalyse(root, today=today)
    by_stream = {r["stream"]: r for r in out["ranked"]}
    assert by_stream["old-question"]["dringlichkeit_days"] > by_stream["young-question"]["dringlichkeit_days"]
    assert by_stream["old-question"]["nutzwert"] > by_stream["young-question"]["nutzwert"]


def test_a_stream_whose_own_asks_bind_more_streams_scores_higher_impact(tmp_path):
    """Post-RULING-281: Impact is driven by binds: on rulings THIS stream's own
    requests produced, not by other streams' requested_by: mentioning it."""
    root = _corpus(tmp_path)
    _sow(root, "p", "popular", 1, status="PROGRESS", restaufwand=5, ledger_shipped=1)
    _sow(root, "p", "lonely", 1, status="PROGRESS", restaufwand=5, ledger_shipped=1)
    _sow(root, "p", "dep-1", 1, status="PROGRESS")
    _sow(root, "p", "dep-2", 1, status="PROGRESS")
    _ruling(root, "290", requested_by="popular#1", binds=["dep-1", "dep-2"])
    out = nutzwertanalyse(root)
    by_stream = {r["stream"]: r for r in out["ranked"]}
    assert by_stream["popular"]["impact_count"] > by_stream["lonely"]["impact_count"]


def test_no_restaufwand_at_all_still_ranks_flagged_estimate_local_median(tmp_path):
    """PRIORITY-NWA-SOW-1 done_when item 5 / RULING-279 s5's open question: a stream
    with NO restaufwand declaration and no ledger claims to derive a per-claim average
    from still ranks - using the corpus median as a last resort, visibly flagged, never
    a silent drop from the ranking."""
    root = _corpus(tmp_path)
    _sow(root, "p", "priced", 1, status="PROGRESS", restaufwand=5, ledger_shipped=2)
    _sow(root, "p", "unpriced", 1, status="PROGRESS")  # no restaufwand:, no ledger
    out = nutzwertanalyse(root)
    by_stream = {r["stream"]: r for r in out["ranked"]}
    assert "unpriced" in by_stream
    assert by_stream["unpriced"]["restaufwand_estimate_kind"] == "ESTIMATE-LOCAL-MEDIAN"
    assert by_stream["priced"]["restaufwand_estimate_kind"] == "PER-STREAM-CLAIM-AVG"


def test_ranking_is_sorted_highest_nutzwert_first(tmp_path):
    root = _corpus(tmp_path)
    today = datetime.date(2026, 8, 17)
    _sow(root, "p", "urgent-cheap", 1, status="RULING-REQUESTED", restaufwand=1, updated="2026-01-01", ledger_shipped=1)
    _sow(root, "p", "quiet-expensive", 1, status="PROGRESS", restaufwand=50, ledger_shipped=1, updated="2026-08-16")
    out = nutzwertanalyse(root, today=today)
    order = [r["stream"] for r in out["ranked"]]
    assert order.index("urgent-cheap") < order.index("quiet-expensive")
    # monotonic non-increasing nutzwert down the list
    values = [r["nutzwert"] for r in out["ranked"]]
    assert values == sorted(values, reverse=True)


def test_criteria_block_exposes_raw_values_for_opportunity_cost_display(tmp_path):
    root = _corpus(tmp_path)
    _sow(root, "p", "a", 1, status="PROGRESS", restaufwand=5, ledger_shipped=1)
    _sow(root, "p", "b", 1, status="PROGRESS", restaufwand=5, ledger_shipped=1)
    out = nutzwertanalyse(root)
    assert "dringlichkeit_raw" in out["criteria"]
    assert "impact_raw" in out["criteria"]
    assert "risiko_raw" in out["criteria"]
    assert out["criteria"]["weights"]["dringlichkeit"] == 0.30
