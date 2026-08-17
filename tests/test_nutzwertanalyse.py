"""Nutzwertanalyse stream ranking (RULING-279, PRIORITY-NWA-SOW-1).

RULING-279 s2: rank every OPEN/PAUSED/BLOCKED stream on four weighted criteria
(Dringlichkeit, Impact, Restaufwand-as-cost, Risiko) into a single Nutzwert, so
Master has a stated reason for which stream gets the next session's tokens. Every
input reuses an existing computation (board_rows/awaiting_ruling/restaufwand/kosten)
except the two citation-graph counts (Impact, Risiko), which are new here.
"""

import datetime

from zero_employee.core import nutzwertanalyse, _nwa_citation_graph, _nwa_age_days, _nwa_minmax_norm


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
# Citation graph (the genuinely new corpus-wide scan)
# ---------------------------------------------------------------------------


def test_citation_graph_counts_who_cites_a_stream(tmp_path):
    root = _corpus(tmp_path)
    _sow(root, "p", "base-stream", 1, status="PROGRESS")
    _sow(root, "p", "dependent-a", 1, status="RULING-REQUESTED", requested_by="base-stream#1")
    _sow(root, "p", "dependent-b", 1, status="PROGRESS", requested_by="base-stream#1")
    g = _nwa_citation_graph(root)
    assert g["base-stream"]["cited_by"] == {"dependent-a", "dependent-b"}
    # only dependent-a is an OPEN ruling-request tracing back to base-stream
    assert g["base-stream"]["blocking_open_requests"] == 1


def test_citation_graph_ignores_self_citation(tmp_path):
    root = _corpus(tmp_path)
    _sow(root, "p", "self-cite", 2, status="PROGRESS", requested_by="self-cite#1")
    g = _nwa_citation_graph(root)
    assert "self-cite" not in g or "self-cite" not in g["self-cite"]["cited_by"]


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


def test_a_stream_with_more_dependents_scores_higher_impact(tmp_path):
    root = _corpus(tmp_path)
    _sow(root, "p", "popular", 1, status="PROGRESS", restaufwand=5, ledger_shipped=1)
    _sow(root, "p", "lonely", 1, status="PROGRESS", restaufwand=5, ledger_shipped=1)
    _sow(root, "p", "dep-1", 1, status="PROGRESS", requested_by="popular#1")
    _sow(root, "p", "dep-2", 1, status="PROGRESS", requested_by="popular#1")
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
