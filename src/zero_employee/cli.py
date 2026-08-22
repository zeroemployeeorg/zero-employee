"""Command-line entry point for zeo (v0.3 — keystone + identity + governance).

--skill <path> checks the sow-authoring skill's era first (Fold 1, governance-docs-first):
the currency-enforcer is graded before the corpus it governs.
"""

from __future__ import annotations
import sys
import pathlib
import datetime
import subprocess
import io
import contextlib
import socket
import typer
from .core import (
    promote_plan,
    resync_check,
    resync_apply,
    unwatched_genres,
    citation_scan,
    citation_totals,
    corpus_root,
    project_backfill_plan,
    project_backfill_apply,
    promote_apply,
    locate_stream,
    project_repair_plan,
    extract_frontmatter,
    stream_progress,
    soll_ist,
    restaufwand,
    kosten,
    waste_report,
    nutzwertanalyse,
    binding_rulings_for_stream,
)
from .cost import (
    UnknownModelError,
    append_session_cost_log,
    fixed_tax_sample_texts,
    format_usd,
    get_model_rates,
    make_estimator,
    repo_token_report,
    session_cost_report,
    usd_for_input_tokens,
)
from .hooks import (
    hooks_install,
    run_pre_commit,
    run_pretooluse_git,
    run_session_start,
    run_stop,
    warn_tracked_boards,
)
from .scaffold import (
    equip_repo,
    init_corpus,
    install_bridges,
    parse_tool_flags,
    read_doctrine,
    scaffold_project_stream,
)
from .core import (
    lint_file,
    iter_sow_files,
    migrate_check_render,
    flat_dark_files,
    needs_successor,
    check_corpus,
    check_ruling_corpus,
    find_canonical_claude_md,
    parse_current_rev,
    check_skill_staleness,
    find_authoring_skills,
    ERROR,
    WARN,
    HINT,
    board_rows,
    awaiting_ruling,
    ungraded_streams,
    find_sow_roots,
    render_state_zone,
    splice_state_zone,
    salvage_state_prefix,
    intake_open_rows,
    build_ruling_index,
    render_ruling_index,
    next_ruling_id,
    _MINT_RACE_NOTE,
    _MINT_RESERVED_NOTE,
    scan_ref_ruling_claims,
    reserve_sow_stub,
    reserve_ruling_stub,
    words_to_slug,
    build_stream_index,
    render_stream_index,
    check_binds_corpus,
    build_sow_n_index,
    check_ruling_receipts,
    check_resolves,
    build_stem_index,
    git_ref_state,
    format_ref_disclosure,
    open_questions_summary,
    classify_all_branches,
    LIVE_BEHIND_THRESHOLD,
    check_base_fresh,
)

_SYM = {ERROR: "✗", WARN: "⚠", HINT: "→"}


def _version():
    """The REAL installed version. A hardcoded banner string printed v0.4 against a
    0.10.0 wheel and caused stale-binary false alarms all week (doctrine) -
    including ten blocks lost at 0.9.0 and one of mine at example-stream-PROV-19."""
    for _n in ("zero-employee", "zeo"):
        try:
            from importlib.metadata import version

            return version(_n)
        except Exception:
            continue
    return "unknown"


# NO HARDCODED HOST PATH. The prior constant named `example-org-sows`, a path that
# stopped existing at the projects/ restructure - a dead fallback nobody noticed because
# the walk-up in _discover_root always won first. Machine-pinned paths cost a migration
# every time the host changes (example-host -> example-host, example-user -> example-user).
import os

_ENV_SOWS = "ZEO_SOWS_ROOT"


def _discover_root(explicit):
    # Ergonomics: --board and --inbox should NOT require a path. Resolve in order:
    # (1) an explicit positional if given; (2) walk UP from cwd to a dir containing
    # claude-md/CLAUDE.md (the sows-repo marker the linter already keys on); (3) the
    # ZEO_SOWS_ROOT env var. A stream runs `zeo --inbox example-stream` from anywhere.
    #
    # doctrine(a): an explicit positional used to be returned VERBATIM, unvalidated -
    # `zeo --mint ruling org-master`, run from INSIDE org-master, silently built the
    # nonexistent path `org-master/org-master` and every downstream glob against it came
    # back empty (0 ruling homes) with no error, which is what let the hardcoded 200 floor
    # (item b) win uncontested. An explicit arg now gets the SAME walk-up as cwd/env below -
    # find_canonical_claude_md resolves it, then walks UP from it (or its parent, if it
    # doesn't exist) to the nearest claude-md/CLAUDE.md - so a near-miss path self-heals to
    # the real corpus root exactly like this example-org repro needs, and a path with NO
    # corpus anywhere above it returns None, hitting the SAME "couldn't find the sows repo"
    # guard every call site here already has - discovery fails loudly, never a footnote
    # under a confident number (doctrine).
    if explicit:
        canon = find_canonical_claude_md(explicit)
        return canon.parent.parent if canon else None
    here = pathlib.Path.cwd()
    for d in (here, *here.parents):
        if (d / "claude-md" / "CLAUDE.md").is_file():
            return d
    env = os.environ.get(_ENV_SOWS)
    if env:
        k = pathlib.Path(env).expanduser()
        if (k / "claude-md" / "CLAUDE.md").is_file():
            return k
    return None


def _load_spec_json(spec_src):
    """Read --spec (stdin via '-', or a file path) and parse it as JSON.

    MEASURED (docs/tutorial build, 2026-08-17): all four `--spec` call sites
    (`sow new`, `intake new`, `intake propose`, `intake promote`) called
    `_json.loads(raw)` with no error handling — a real user piping plain
    prose into `--spec -` (the natural mistake, since `zeo intake mission`'s
    own printed instructions read like they want free text) got a raw Python
    traceback (`json.decoder.JSONDecodeError`) instead of a clean message,
    the only unguarded failure path in an otherwise consistently-guarded
    command family (every sibling error here — a missing file, a missing
    flag — prints one line and returns a real exit code).

    Returns (spec_dict, None) on success, or (None, error_message) on any
    failure — file not found, JSON syntax error, or valid JSON that isn't an
    object. Never raises; every call site turns the second element into the
    same `print(..., file=sys.stderr); return 1` shape it already uses for
    its other guarded errors.
    """
    import json as _json

    try:
        raw = sys.stdin.read() if spec_src == "-" else pathlib.Path(spec_src).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, f"--spec file not found: {spec_src}"
    except OSError as exc:
        return None, f"--spec file could not be read: {spec_src} ({exc})"
    try:
        spec = _json.loads(raw)
    except _json.JSONDecodeError as exc:
        return None, (
            f"--spec is not valid JSON ({exc}). "
            "This flag takes a JSON object, not free-form prose — "
            'e.g. --spec - <<<\'{"key": "value"}\'. '
            "If you have prose notes, put them inside a JSON string value."
        )
    if not isinstance(spec, dict):
        return None, f"--spec must be a JSON object (got {type(spec).__name__})"
    return spec, None


def _inbox(root, stream) -> int:
    """A stream's own view: open questions + rulings that answered it. The reliable
    form of the hand-grep that returns false-silence on a syntax slip (DS5-INBOX-239)."""
    files_fm = []
    for f in iter_sow_files(root):
        fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if isinstance(fm, dict):
            files_fm.append((str(f), fm))
    aw = [r for r in awaiting_ruling(files_fm, root=root) if str(r["stream"]).lower() == stream.lower()]
    # THREE closure states (doctrine): a SOW leaves OPEN if a ruling answered it (answered)
    # OR a verified resolved_by closed it (resolved). Supersession is the one self-serving
    # resolver - its own section for sampled human audit (Sparring addition 2, binding).
    #
    # PRECEDENCE FIX (paid 2026-08-16, editorial-recon SOW-1 / RULING-067): `resolved` and
    # `superseded` both correctly excluded `answered`, but `ans` did not exclude `resolved` -
    # so once a ruling's requested_by cited a SOW, that row was PERMANENTLY stuck at
    # "answered-by-ruling" even after the stream did exactly what the message told it to
    # ("cite it in your next SOW to close the loop") and wrote a valid, gate-verified
    # resolved_by back. The receipt could never be seen. `resolved_by` is the STRONGER
    # signal (check_resolved_by verifies it against ground; answered_by only checks a
    # ruling's requested_by names the file) so it must win when both are present.
    resolved = [r for r in aw if r.get("resolved") and not r.get("supersession")]
    ans = [r for r in aw if r.get("answered") and not r.get("resolved")]
    superseded = [r for r in aw if r.get("supersession") and not r.get("answered")]
    openq = [r for r in aw if not r.get("answered") and not r.get("resolved")]
    # COVERAGE (doctrine / Sparring s2): the inbox must DECLARE its blind spot. A
    # confident "0 open" that actually means "I can't parse this stream" is the false-ANSWERED
    # class - blindness reading as health. Count the stream's raw .md files vs the ones with
    # parseable frontmatter; the gap is INVISIBLE (pre-schema, migration pending).
    _raw = [f for f in iter_sow_files(root) if str(f).lower().rfind(f"/{stream.lower()}/") != -1]
    _readable = 0
    for f in _raw:
        fm = extract_frontmatter(pathlib.Path(f).read_text(encoding="utf-8", errors="replace"))
        if isinstance(fm, dict):
            _readable += 1
    _invisible = len(_raw) - _readable
    print(f"INBOX: {stream}")
    # doctrine: this reads pathlib off disk, zero git (correct - a seat must see its
    # own uncommitted work), but "disk" is a CHECKOUT and the question is usually about the
    # TRUNK. Name which one this is, every invocation.
    print(f"  {format_ref_disclosure(git_ref_state(root))}")
    if _invisible:
        print(
            f"  ⚠ COVERAGE: {len(_raw)} documents · {_readable} readable · "
            f"{_invisible} INVISIBLE (pre-schema — migration pending, not counted below)"
        )
    else:
        print(f"  COVERAGE: {len(_raw)} documents, all readable")
    print(
        f"  {len(openq)} truly open · {len(ans)} answered-by-ruling · "
        f"{len(resolved)} resolved · {len(superseded)} by-supersession"
    )
    print("")
    print("OPEN (awaiting a ruling — nothing has closed these):")
    for r in sorted(openq, key=lambda x: str(x["rev"])):
        print(f"  SOW-{r['rev']:<4} asked {r['updated']}   {r['file']}")
    if not openq:
        print("  (none)")
    print("")
    print("ANSWERED-BY-RULING (cite it in your next SOW to close the loop):")
    for r in sorted(ans, key=lambda x: str(x["rev"])):
        nnn, upd = r["answered"]
        print(f"  SOW-{r['rev']:<4} <- RULING-{nnn} ({upd})   {r['file']}")
    if not ans:
        print("  (none)")
    print("")
    print("RESOLVED (closed by implementation/doctrine, verified resolver — not awaiting anything):")
    for r in sorted(resolved, key=lambda x: str(x["rev"])):
        k, tgt = r["resolved"]
        print(f"  SOW-{r['rev']:<4} <- {k}: {tgt}   {r['file']}")
    if not resolved:
        print("  (none)")
    print("")
    print("RESOLVED-BY-SUPERSESSION (self-declared — sampled human audit, Sparring addition 2):")
    for r in sorted(superseded, key=lambda x: str(x["rev"])):
        k, tgt = r["resolved"]
        print(f"  SOW-{r['rev']:<4} <- {tgt}   {r['file']}")
    if not superseded:
        print("  (none)")
    print("")
    # RULING-268 s1 / charter Phase 1 item 3: per-file open_questions: rollup, independent
    # of the RULING-REQUESTED-only `aw` list above (a file can carry open_questions: at
    # any status — awaiting_ruling()'s filter does not apply here). Additive: a stream
    # with no open_questions: anywhere prints the same "(none)" every prior inbox run
    # already printed nothing for, so a file with zero open_questions: rows is untouched.
    oq_rows = []
    for path, fm in files_fm:
        if str(fm.get("sow") or "").lower() != stream.lower():
            continue
        summary = open_questions_summary(fm)
        if summary is None:
            continue
        oq_rows.append((path, fm, summary))
    print("OPEN QUESTIONS (per-file open_questions: rollup — RULING-268):")
    for path, fm, summary in sorted(oq_rows, key=lambda t: str(t[1].get("updated", "?"))):
        tag = summary["tag"]
        # Phase 2 fixture proof (charter's own literal DoD line) found this printing a
        # bare tag ("RESOLVED", no fraction) for the all-resolved/all-open cases, while
        # the charter's Phase 2 acceptance text names "RESOLVED (3/3)" verbatim as what
        # --inbox must report once the second ruling lands. Only PARTIAL ever carried
        # the fraction before; RESOLVED and OPEN did not, and no test exercised those
        # two tags' printed string before this fix (test_open_questions_inbox.py only
        # asserted the dict shape for them, never the CLI's rendered line). Always
        # showing the fraction is strictly more informative and matches the charter's
        # own worked example string exactly, so this makes every tag consistent rather
        # than special-casing PARTIAL.
        label = f"{tag} ({summary['resolved']}/{summary['total']})"
        print(f"  {label:<14} {pathlib.Path(path).name}")
    if not oq_rows:
        print("  (none)")
    print("")
    # BINDING RULINGS: the gap MEASURED live in ducktyper-ai/org (2026-08-17) — a
    # fresh Master read --inbox's own doctrine literally ("built only from SOWs that
    # asked a question") and correctly concluded the tool's relay duty was
    # structurally unmet for a PROACTIVE fleet-binding ruling (`binds: [all-streams]`
    # or a direct stream id, no `requested_by:` naming this stream at all — nobody
    # asked, Master just ruled). Everything above this line answers "what did I ask
    # and did it get answered." This section answers a DIFFERENT question: "what
    # binds me that I never asked about." Same receipt doctrine as the rest of this
    # corpus (citation is the receipt) — NOT-YET-CITED is not a fault on its own,
    # it is the honest state of a binding ruling this stream has not yet acted on.
    binding = binding_rulings_for_stream(files_fm, stream, root)
    print("BINDING RULINGS (bind you via `binds:` — asked or not; cite one in your next SOW to acknowledge):")
    for r in binding:
        tag = "ACKNOWLEDGED" if r["acknowledged"] else "NOT-YET-CITED"
        title = f" — {r['title']}" if r["title"] else ""
        print(f"  RULING-{r['ruling']:<5} {tag:<14} ({r['updated']})   {pathlib.Path(r['path']).name}{title}")
    if not binding:
        print("  (none)")
    return 0


def _triage(root) -> int:
    """The operator worklist: whom do I help today (doctrine).

    ASSEMBLY, NOT CONSTRUCTION (example-stream doctrine): every classification here
    already exists in core. In particular the NEEDS-SUCCESSOR bucket CALLS
    awaiting_ruling(), whose consumed-ruling filter (l977-1014) is MANDATED by
    doctrine - a stream that moved past the answered SOW is not listed. The
    board-triage.sh prototype over-reported precisely because a shell script
    scraping STATE.md cannot reach that filter.

    The prototype is the LAYOUT spec (s2.3), not the implementation - and its awk
    hardcodes `(example-project|governance-layer|example-project|zeo)`, so it is structurally
    blind to three projects holding dark files. Projects are DERIVED here.
    """
    files_fm = []
    for f in iter_sow_files(root):
        fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if isinstance(fm, dict):
            files_fm.append((str(f), fm))
    rows = board_rows(files_fm)
    aw = awaiting_ruling(files_fm, root=root)
    sow_roots = find_sow_roots(root)
    ug = [u for r in sow_roots for u in ungraded_streams(r)]
    flat = [x for r in sow_roots for x in flat_dark_files(r)]

    def by_status(*want):
        return [r for r in rows if str(r["status"]).upper().split("-SEE")[0] in want]

    openq = [r for r in aw if not r.get("answered") and not r.get("resolved")]
    ans, suppressed = needs_successor(aw, rows)  # doctrine, MANDATED
    # MEASURED (this session, worldprops SOW-25): by_status("RULING-REQUESTED") counts
    # every row whose status: STRING says RULING-REQUESTED, independent of whether
    # awaiting_ruling() already found it answered/resolved. A stream whose status:
    # field was never flipped after its own resolved_by landed showed up here with
    # "1 streams, 0 open questions" printed together -- the stream-count and the
    # question-list disagreed because they read two different signals. needs_master
    # must be the set of STREAMS that actually own an unresolved openq row, not a
    # raw status-string scan; a stream present in `rows` at RULING-REQUESTED but with
    # every one of its questions already answered/resolved is not owed a ruling.
    needs_master_streams = {q["stream"] for q in openq}
    needs_master = [r for r in by_status("RULING-REQUESTED") if r["stream"] in needs_master_streams]
    paused = by_status("HELD", "HANDOVER")
    blocked = by_status("BLOCKED")
    dark_rows = by_status("UNKNOWN")
    resting = by_status("CLOSEOUT", "SHIPPED", "SUPERSEDED", "VOIDED", "STALE", "FINDING")
    working = by_status("DRAFT", "DESIGN", "PROGRESS")

    intake_open = intake_open_rows(root)

    print(f"BOARD TRIAGE - {len(rows)} streams across {len(sow_roots)} projects")
    print("")
    print(
        f"INTAKE - unconverted operator intent, OPEN only ({len(intake_open)}; "
        f"doctrine item 3 - a projection, not evidence, doctrine)"
    )
    for x in intake_open:
        print(f"   {x['project']}  {x['intake']}  filed {x['created']}")
    print("")
    print(f"NEEDS MASTER - a ruling is owed ({len(needs_master)} streams, {len(openq)} open questions)")
    for r in needs_master:
        print(f"   {r['project']}/{r['stream']} SOW-{r['latest']}  ({r['updated']})")
    for q in openq:
        print(f"     OPEN  {q['stream']} SOW-{q['rev']}  asked {q['updated']}")
    print("")
    print(
        f"NEEDS A SUCCESSOR - ruled, maybe unread ({len(ans)}; "
        f"{len(suppressed)} suppressed as already-acted per doctrine)"
    )
    for r in ans:
        nnn, upd = r["answered"]
        print(f"   {r['stream']} SOW-{r['rev']} -> RULING-{nnn} ({upd})")
    print("")
    print(f"PAUSED - held/handover, waiting to be picked up ({len(paused)})")
    for r in paused:
        print(f"   {r['project']}/{r['stream']} SOW-{r['latest']}  {r['status']}")
    print("")
    print(f"BLOCKED - external obstruction ({len(blocked)})")
    for r in blocked:
        print(f"   {r['project']}/{r['stream']} SOW-{r['latest']}")
    print("")
    dark_total = len(dark_rows) + len(ug) + len(flat)
    print(f"DARK - invisible to the board; the migration burn-down meter (doctrine): {dark_total}")
    for r in dark_rows:
        print(f"   UNKNOWN-rev  {r['project']}/{r['stream']}")
    for u in ug:
        print(f"   pre-schema   {u['project']}/{u['stream']}  ({u['files']} files)")
    if flat:
        print(
            f"   FLAT files directly under <project>/sow/ - no stream dir ({len(flat)}); invisible to the stream walk:"
        )
        for x in flat:
            print(f"      {x['project']}/{x['file']}")
    print("")
    print(
        f"RESTING - done, not your attention: {len(resting)} streams "
        f"(still-working DRAFT/DESIGN/PROGRESS: {len(working)})"
    )
    return 0


def _priority(root, *, top_n=3, near_m=3, json_out=False) -> int:
    """RULING-279: rank every OPEN/PAUSED/BLOCKED stream by Nutzwertanalyse and name
    what a Master session would fund next AND what it would trade off (s3
    Opportunitätskosten — a ranking that shows only the winner hides the decision's
    real cost). Tokens throughout, never currency, per the ruling's own instruction.

    Deliberately a SEPARATE verb from --triage (RULING-279 s5 leans this way: triage
    stays the fast unopinionated read, priority is the considered one you consult
    deliberately — this does not change --triage's own sort order).
    """
    out = nutzwertanalyse(root)
    ranked = out["ranked"]
    if json_out:
        import json as _json

        payload = {
            "kind": "nutzwertanalyse",
            "weights": out["criteria"].get("weights", {}),
            "funded": ranked[:top_n],
            "near_miss": ranked[top_n : top_n + near_m],
            "honesty": "Nutzwert = weighted(Dringlichkeit,Impact,Risiko) / Restaufwand_tokens; "
            "ESTIMATE tokens, never currency",
        }
        print(_json.dumps(payload, indent=2, default=str))
        return 0

    if not ranked:
        print("NUTZWERTANALYSE - no OPEN/PAUSED/BLOCKED stream to rank.")
        return 0

    print(f"NUTZWERTANALYSE (RULING-279) - {len(ranked)} rankable stream(s)")
    w = out["criteria"].get("weights", {})
    print(
        "  Nutzwert = ({:.2f}*Dringlichkeit + {:.2f}*Impact + {:.2f}*Risiko) / Restaufwand_tokens "
        "(first-cut weights, RULING-279 s5 - revisable)".format(
            w.get("dringlichkeit", 0), w.get("impact", 0), w.get("risiko", 0)
        )
    )
    print("")
    funded = ranked[:top_n]
    near_miss = ranked[top_n : top_n + near_m]
    print(f"FUNDED - top {len(funded)} for the next session's tokens:")
    for i, r in enumerate(funded, 1):
        print(
            "  {}. {:<28} nutzwert={:.6f}  dringlichkeit={}d  impact={}  risiko={}  restaufwand~{:.0f}tok [{}]".format(
                i,
                r["stream"],
                r["nutzwert"],
                int(r["dringlichkeit_days"]),
                int(r["impact_count"]),
                int(r["risiko_count"]),
                r["restaufwand_tokens"],
                r["restaufwand_estimate_kind"],
            )
        )
    print("")
    print(
        f"OPPORTUNITÄTSKOSTEN - next {len(near_miss)} near-miss stream(s), NOT funded this round "
        "(RULING-279 s3: the ranking's real cost, stated not implied):"
    )
    if not near_miss:
        print("  (none - fewer than top_n+near_m rankable streams)")
    last_funded_score = funded[-1]["nutzwert"] if funded else 0.0
    for i, r in enumerate(near_miss, 1):
        delta = last_funded_score - r["nutzwert"]
        print("  {}. {:<28} nutzwert={:.6f}  delta-to-last-funded=-{:.6f}".format(i, r["stream"], r["nutzwert"], delta))
    return 0


def _atomic_write_text(target: pathlib.Path, text: str) -> None:
    """Write TARGET atomically: temp file in the same dir, then os.replace() over it.

    Same technique as migrate.atomic_replace() (mkstemp beside the target + fsync +
    os.replace), minus its compare-and-swap precondition — STATE.md is regenerated
    WHOLE on every run rather than incrementally migrated, so there is no prior
    content to verify against, only a partial write to prevent. An interrupted write
    leaves the original file (or no file) in place; it can never leave a truncated one.
    """
    import tempfile

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    temporary_path = pathlib.Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _board(root, repair: bool = False) -> int:
    files_fm = []
    for f in iter_sow_files(root):
        fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if isinstance(fm, dict):
            files_fm.append((str(f), fm))
    rows = board_rows(files_fm)
    aw = awaiting_ruling(files_fm, root=root)
    ug = [u for r in find_sow_roots(root) for u in ungraded_streams(r)]
    head = (
        subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        or "UNKNOWN-not-a-git-repo"
    )
    # doctrine (applied here, not just where s2 named it): captured BEFORE this
    # verb's own write - the disclosure must describe the state that was READ, not get
    # contaminated by the file this same call is about to create (a fresh STATE.md is
    # itself an uncommitted change the moment it lands, which would make every run report
    # "dirty" regardless of what the corpus looked like beforehand).
    ref_state = git_ref_state(root)
    zone = render_state_zone(rows, head, datetime.date.today(), aw, ug)
    target = pathlib.Path(root) / "STATE.md"
    existing = target.read_text(encoding="utf-8", errors="replace") if target.is_file() else None
    try:
        out = splice_state_zone(existing, zone, title=pathlib.Path(root).resolve().name)
    except ValueError as e:
        if not repair:
            print(f"FATAL: {e}", file=sys.stderr)
            return 2
        # --repair (opt-in only, RULING-target of this stream): best-effort salvage of
        # whatever hand-authored content sits before the first marker found, then a
        # fresh well-formed fence. The default (non-repair) path above is UNCHANGED —
        # still FATAL/exit-2/no-write — this branch only runs when the caller asked.
        salvaged = salvage_state_prefix(existing)
        out = splice_state_zone(salvaged, zone, title=pathlib.Path(root).resolve().name)
        print(f"REPAIRED: {e}", file=sys.stderr)
    _atomic_write_text(target, out)
    o = len([x for x in aw if not x.get("answered")])
    a = len(aw) - o
    print(f"board written: {target}")
    print(f"  {format_ref_disclosure(ref_state)}")
    print(
        f"  {len(rows)} streams across {len(find_sow_roots(root))} projects · "
        f"{o} open questions · {a} ruled-but-maybe-unread · {len(ug)} ungraded streams"
    )
    print("")
    print(f"{'PROJECT':<18} {'STREAM':<22} {'LATEST':>6}  {'STATUS':<17} UPDATED")
    for r in rows:
        print(
            f"{str(r['project'])[:18]:<18} {str(r['stream'])[:22]:<22} "
            f"{str(r['latest']):>6}  {str(r['status'])[:17]:<17} {r['updated']}"
        )
    return 0


def _commit_check_corpus(root) -> int:
    """doctrine(1): DETECT at the commit path, corpus-wide - the corpus-level twin of
    --commit-check's per-file pass, invoked ONCE PER COMMIT (by the hook, after its per-file
    loop) rather than once per staged file. This is a SEPARATE verb, not --commit-check made
    corpus-aware in general (s7's open question, example-stream's call): re-scanning the WHOLE ruling
    namespace on every one of a commit's staged files would be O(files-staged x corpus-size)
    for no benefit, since --commit-check's own per-file contract (fast, gates ONE file's own
    keystone/requested_by shape) is unrelated to a cross-file collision. One pass, once,
    beside it.

    THE BOUND, stated here because doctrine(1) requires it stated in the code, not just
    the ruling: this catches a same-tree ruling-number collision at the FIRST commit after
    BOTH colliding files exist on disk together. It does NOT catch the cross-seat case at the
    moment either individual seat commits - the peer's file is not on disk yet, and no
    per-commit gate on either side of a two-seat race can see the other seat's uncommitted
    work. What this closes is everything downstream of the race itself: today NOTHING catches
    the collision, ever, until a human happens to notice (which is what actually happened);
    after this, the first commit that lands both files - typically minutes after the race,
    not weeks - fails closed.
    """
    homes = [
        pathlib.Path(root) / "ruling",
        *pathlib.Path(root).glob("projects/*/ruling"),
        *pathlib.Path(root).glob("*/ruling"),
    ]
    files_fm = []
    for h in homes:
        if not h.is_dir():
            continue
        for f in sorted(h.glob("RULING-*.md")):
            fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
            if isinstance(fm, dict):
                files_fm.append((str(f), fm))
    ruling_collisions = check_ruling_corpus(files_fm)

    # SOW n-collision, same shape, same gap, fixed at the same time it was found:
    # check_corpus (n-collision) had the IDENTICAL cross-file blindness this function
    # was built to close for rulings - defined, tested, callable, but never reachable
    # from the actual pre-commit hook path, because that path only ever sees ONE
    # staged file at a time (--commit-check) or was gated to run only when a RULING
    # was among the staged files (this function, historically). A staged SOW that
    # collides with an already-committed SOW's n/rev was invisible to every commit,
    # forever - proven live: two real SOWs in two different corpora both landed this
    # way and sat undetected until a full corpus `zeo .` scan happened to be run by
    # hand. Fixed by
    # extending this SAME once-per-commit corpus pass to the SOW namespace, not a
    # second bolt-on gate - one collision-detection pass, both namespaces.
    sow_files_fm = []
    for f in iter_sow_files(pathlib.Path(root)):
        fm = extract_frontmatter(pathlib.Path(f).read_text(encoding="utf-8", errors="replace"))
        if isinstance(fm, dict):
            sow_files_fm.append((str(f), fm))
    sow_collisions = check_corpus(sow_files_fm, root=root)
    sow_collisions = {p: [fi for fi in fis if fi.code == "n-collision"] for p, fis in sow_collisions.items()}
    sow_collisions = {p: fis for p, fis in sow_collisions.items() if fis}

    from .execution import iter_execution_receipts, validate_receipt_path

    receipt_errors: list[str] = []
    receipt_files = iter_execution_receipts(pathlib.Path(root))
    for rp in receipt_files:
        _rec, errs = validate_receipt_path(rp)
        receipt_errors.extend(errs)

    if not ruling_collisions and not sow_collisions and not receipt_errors:
        extra = ""
        if receipt_files:
            extra = f", {len(receipt_files)} execution receipt(s) valid"
        print(
            f"COMMIT-CHECK-CORPUS: 0 ruling-number collisions across {len(files_fm)} ruling "
            f"file(s), 0 SOW n-collisions across {len(sow_files_fm)} SOW file(s){extra}"
        )
        return 0
    if ruling_collisions:
        print(f"COMMIT-CHECK-CORPUS: {len(ruling_collisions)} file(s) in a ruling-number collision")
        for path, findings in sorted(ruling_collisions.items()):
            for fi in findings:
                print(f"    {_SYM.get(fi.severity, '?')} [{fi.code}] {path}: {fi.message}")
    if sow_collisions:
        print(f"COMMIT-CHECK-CORPUS: {len(sow_collisions)} file(s) in a SOW n-collision")
        for path, findings in sorted(sow_collisions.items()):
            for fi in findings:
                print(f"    {_SYM.get(fi.severity, '?')} [{fi.code}] {path}: {fi.message}")
    if receipt_errors:
        print(f"COMMIT-CHECK-CORPUS: {len(receipt_errors)} execution receipt error(s)")
        for e in receipt_errors:
            print(f"    {_SYM.get(ERROR, '?')} [execution-receipt] {e}")
    return 1


def _ruling_index(root) -> int:
    """doctrine(2)/s4: regenerate ruling-index.md WHOLE at the corpus root, same
    pattern as --board's STATE.md - the file is entirely machine-owned (no human-authored
    content to splice around, unlike STATE.md's zone-within-a-larger-doc), so a whole-file
    write is correct here, not a truncation risk."""
    entries = build_ruling_index(root)
    head = (
        subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        or "UNKNOWN-not-a-git-repo"
    )
    # doctrine: captured BEFORE the write below, so this run's own fresh
    # ruling-index.md (uncommitted the instant it lands) never contaminates the reading.
    ref_state = git_ref_state(root)
    out = render_ruling_index(entries, head, datetime.date.today())
    target = pathlib.Path(root) / "ruling-index.md"
    target.write_text(out, encoding="utf-8")
    # Same criterion render_ruling_index uses per-row (PAID: Master reported the per-row
    # note calling an owner+tombstone pair "legal per-scope reuse" when the tombstone, not
    # a second scope's owner, was the only co-occupant) - this summary line had the SAME
    # bug one level up: counting ALL rows sharing an integer, tombstones included, as if
    # every one were doctrine reuse. Legal reuse is specifically 2+ OWNER rows in
    # DIFFERENT scopes; keep the two counts (reuse vs tombstone-explained) separate so the
    # headline never claims more "legal reuse" than actually exists.
    reuse = 0
    for rows in entries.values():
        owners = [r for r in rows if r["role"] == "owner"]
        if len(owners) > 1 and len({r.get("scope") for r in owners}) > 1:
            reuse += 1
    tomb = sum(1 for rows in entries.values() for r in rows if r["role"] == "tombstone")
    print(f"ruling-index written: {target}")
    print(f"  {format_ref_disclosure(ref_state)}")
    print(
        f"  {len(entries)} integer(s) tracked · {reuse} with multiple owners "
        f"(legal per-scope reuse, doctrine) · {tomb} tombstone(s) (renumbered-away)"
    )
    return 0


def _mint(root, kind, stream, words: str | None = None) -> int:
    """Mint the next free id and, when --words is given, RESERVE it by writing a stub.

    Without --words: advisory print only (legacy doctrine behavior + race note).
    With --words: exclusive stub create under the canonical name; peer mints see the file.
    """
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    if kind == "ruling":
        if words:
            path, detail = reserve_ruling_stub(root, words)
            if path is None:
                print(f"MINT: REFUSED - {detail}", file=sys.stderr)
                return 1
            print(f"MINT: RESERVED ruling at {path}")
            print(f"  {detail}")
            print("  slug: " + words_to_slug(words))
            print("  " + _MINT_RESERVED_NOTE.format(path=path))
            return 0
        nxt, homes, total = next_ruling_id(root, project=None)
        if not homes:
            print(
                f"MINT: REFUSED - 0 ruling home(s) discoverable under {root}",
                file=sys.stderr,
            )
            print(
                "  no `ruling/` directory found at the root or under any project - this "
                "corpus cannot be read, so no number is minted (doctrine): a "
                "fallback firing on a failed read is how a discovery bug becomes a "
                "doctrine bug.",
                file=sys.stderr,
            )
            return 1
        ref_claims = scan_ref_ruling_claims(root)
        colliding = {ref: (n, p) for ref, (n, p) in ref_claims.items() if n >= nxt}
        disk_nxt = nxt
        if colliding:
            widest_claim = max(n for n, _p in colliding.values())
            nxt = max(disk_nxt, widest_claim + 1)
        print(f"MINT: next ORG-SCOPE ruling id = {nxt}")
        if colliding:
            print(f"  disk says {disk_nxt}, {len(colliding)} pushed ref(s) claim up to {widest_claim} -> MINTING {nxt}")
        print(f"  read from {len(homes)} ruling home(s), {total} existing ruling file(s) seen")
        print("  " + _MINT_RACE_NOTE.format(kind="ruling", ts=ts))
        print('  tip: pass --words "four to five words" to RESERVE a canonical RULING-NNN-<slug>.md stub on disk')
        if colliding:
            print(
                f"  ⚠ REF-COLLISION: {len(colliding)} pushed ref(s) already claimed >= "
                f"the disk-only answer ({disk_nxt}) - accounted for in the number above:"
            )
            for ref, (n, p) in sorted(colliding.items(), key=lambda kv: -kv[1][0]):
                print(f"      {ref} already carries RULING-{n} at {p}")
        elif ref_claims:
            top_ref, (top_n, top_p) = max(ref_claims.items(), key=lambda kv: kv[1][0])
            print(f"  ref scan: highest claim on any ref is RULING-{top_n} ({top_ref}) - {nxt} is still free")
        else:
            print(
                "  ref scan: no ruling claims found on any refs/remotes/* ref "
                "(no remotes, fetch failed, or none carry one)"
            )
        return 0
    if kind == "sow":
        if not stream:
            print(
                "zeo --mint sow <stream>: a stream name is required",
                file=sys.stderr,
            )
            return 2
        if words:
            path, detail = reserve_sow_stub(root, stream, words)
            if path is None:
                print(f"MINT: REFUSED - {detail}", file=sys.stderr)
                return 1
            print(f"MINT: RESERVED sow at {path}")
            print(f"  {detail}")
            print("  slug: " + words_to_slug(words))
            print("  " + _MINT_RESERVED_NOTE.format(path=path))
            return 0
        L = locate_stream(root, stream)
        if L["ambiguous"]:
            print(
                f"MINT: AMBIGUOUS - {len(L['candidates'])} dirs named {stream!r}, a human rules this, not the mint",
                file=sys.stderr,
            )
            return 1
        if L["next_n"] is not None:
            nxt = L["next_n"]
        elif not L["chain_dir"]:
            nxt = 1  # brand-new stream, no chain dir exists yet - its first SOW is n:1
        else:
            print(
                f"MINT: {stream}'s chain dir exists but no filed SOW carries an n: - "
                "cannot derive a next integer safely, walk the chain by hand",
                file=sys.stderr,
            )
            return 1
        print(f"MINT: next {stream} SOW n = {nxt}")
        print("  " + _MINT_RACE_NOTE.format(kind="sow", ts=ts))
        print(
            f'  tip: pass --words "four to five words" to RESERVE a canonical {stream}-SOW-{nxt}-<slug>.md stub on disk'
        )
        return 0
    print(
        f"zeo --mint: unknown kind {kind!r} - expected 'ruling' or 'sow'",
        file=sys.stderr,
    )
    return 2


def _stream_index_cmd(root) -> int:
    """doctrine: generate stream-index.md WHOLE at the sows root - the mechanism
    that makes `binds:`, and doctrine's `<stream>#<n>` form, dereferenceable at all."""
    entries = build_stream_index(root)
    head = (
        subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        or "UNKNOWN-not-a-git-repo"
    )
    # doctrine: captured BEFORE the write below, same reasoning as _board/_ruling_index
    # - this run's own fresh stream-index.md must not contaminate its own disclosure.
    ref_state = git_ref_state(root)
    out = render_stream_index(entries, head, datetime.date.today())
    target = pathlib.Path(root) / "stream-index.md"
    target.write_text(out, encoding="utf-8")
    amb = [k for k, v in entries.items() if v["ambiguous"]]
    pre = [k for k, v in entries.items() if v["preschema"]]
    print(f"stream-index.md written: {target}")
    print(f"  {format_ref_disclosure(ref_state)}")
    print(
        f"  {len(entries)} stream id(s) · {len(amb)} ambiguous (recorded, not resolved) · "
        f"{len(pre)} pre-schema (matched by dirname)"
    )
    if amb:
        print(f"  ambiguous: {', '.join(sorted(amb))}")
    return 0


def _digest(root, since) -> int:
    """example-stream-CHARTER-03 register item 4: `zeo --digest [since]`. FOLDS IN
    tools/hooks/zeo-digest.sh's own logic - ported section by section, the BOUNDING logic
    (what counts as "this session") is NOT rewritten, only translated from bash to Python,
    per the coordinator's explicit instruction. Every section below is traceable to one
    named block in the shell script; nothing here is a reinterpretation of what "session"
    or "owed" means.

    THE BOUNDING RULE, unchanged: a SESSION is a run of commits by ONE author since the
    last commit by someone else - which is what a reviewer means by "what did it do".
    `git --since` filters on AUTHOR DATE, which a rebase preserves while moving the
    commit, so a clock window lies after a rebase; the author-boundary walk does not.
    When `since` IS given (e.g. "4h", "1d"), that literal `--since` filter is used
    instead - exactly the same bash branch, not a new mode invented here.
    """
    root = str(pathlib.Path(root).resolve())

    def _git(*args):
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else ""

    if not since:
        me = _git("log", "-1", "--format=%an").strip()
        bound = None
        for line in _git("log", "--format=%H %an").splitlines():
            h, _, an = line.partition(" ")
            if an != me:
                bound = h
                break
        rng = f"{bound}..HEAD" if bound else "HEAD"
        log = lambda *a: _git("log", rng, *a)  # noqa: E731
        since_label = ""
    else:
        log = lambda *a: _git("log", f"--since={since}", *a)  # noqa: E731
        since_label = since

    host = socket.gethostname().split(".")[0]
    today = datetime.date.today().isoformat()
    out = [
        f"===== ZEO SESSION DIGEST · since {since_label} · "
        f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} · {host} ====="
    ]

    out += ["", "--- COMMITS ---"]
    commit_lines = [l[:118] for l in log("--format=  %h %an  %s").splitlines()]
    out += commit_lines if commit_lines else ["  none"]
    total = len(log("--oneline").splitlines())
    out.append(f"  total: {total}")

    out += ["", "--- RULINGS FILED ---"]
    added = sorted(
        set(l for l in log("--diff-filter=A", "--name-only", "--format=", "--", "ruling/*.md").splitlines() if l)
    )
    if added:
        for f in added:
            fp = pathlib.Path(root) / f
            if not fp.is_file():
                continue
            title = ""
            for l in fp.read_text(encoding="utf-8", errors="replace").splitlines():
                if l.startswith("title:"):
                    title = l[7:157]
                    break
            out.append(f"  {fp.name}")
            out.append(f"      {title}")
    else:
        out.append("  none")

    out += ["", "--- SOWs FILED ---"]
    sow_added = sorted(
        set(l for l in log("--diff-filter=A", "--name-only", "--format=", "--", "*/sow/*").splitlines() if l)
    )
    out += [f"  {pathlib.Path(f).name}" for f in sow_added] if sow_added else ["  none"]

    out += [
        "",
        "--- SELF-CORRECTIONS AND RETRACTIONS (what a reviewer reads FIRST) ---",
    ]
    import re as _re

    kw = _re.compile(r"correct|retract|wrong|falsif|my own|i paid|mine|error|withdraw", _re.I)
    sc = [l[:118] for l in log("--format=%h %s").splitlines() if kw.search(l)]
    out += [f"  {l}" for l in sc] if sc else ["  none"]

    out += ["", "--- WHAT IS OWED NOW ---"]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            _triage(pathlib.Path(root))
        triage_lines = buf.getvalue().splitlines()[:16]
        out += [f"  {l}" for l in triage_lines] if triage_lines else ["  (zeo not on PATH)"]
    except Exception:
        out.append("  (zeo not on PATH)")

    out += [
        "",
        "--- UNCOSIGNED ORG-SCOPE RULINGS (doctrine: not in force until co-signed) ---",
    ]
    n = 0
    rd = pathlib.Path(root) / "ruling"
    if rd.is_dir():
        for f in sorted(rd.glob("RULING-*.md")):
            text = f.read_text(encoding="utf-8", errors="replace")
            if "\nscope: org" not in text and not text.startswith("scope: org"):
                continue
            if _re.search(r"COSIGNED|SPARRING-COSIGN", text, _re.I):
                continue
            out.append(f"  {f.name}")
            n += 1
    out.append(f"  count: {n}")

    out += ["", "--- TREE STATE (anything a seat left behind) ---"]
    status = [l for l in _git("status", "--short").splitlines() if not l.startswith("??")][:8]
    out += status if status else ["  clean"]
    unpushed_raw = subprocess.run(
        ["git", "-C", root, "log", "--oneline", "@{u}..HEAD"],
        capture_output=True,
        text=True,
    )
    unpushed = len(unpushed_raw.stdout.splitlines()) if unpushed_raw.returncode == 0 else 0
    out.append(f"  unpushed: {unpushed}")

    out += ["", "--- SESSION COST ---"]
    costlog = pathlib.Path(root) / "tools" / "stream-instruments" / "session-costs.jsonl"
    if costlog.is_file():
        try:
            sc = session_cost_report(cost_log=costlog)
            out.append(
                "  DERIVED {}  in={} out={} cache_r={} events={}  model={} as_of={}".format(
                    format_usd(sc["usd"]),
                    sc["input_tokens"],
                    sc["output_tokens"],
                    sc["cache_read_tokens"],
                    sc["events"],
                    sc["model"],
                    sc["as_of"],
                )
            )
            out.append(f"  ({sc['honesty']})")
        except Exception:
            tail = costlog.read_text(encoding="utf-8", errors="replace").splitlines()[-4:]
            out += [f"  {l}" for l in tail] if tail else ["  no log"]
    else:
        out.append("  no log")

    out += ["", "===== END DIGEST ====="]
    print("\n".join(out))
    return 0


_USAGE = """zeo (zero-employee) - portable SOW governance tooling

Orientation (preferred entry points)
  zeo                        Human orientation dashboard
  zeo orient [--json]        Same briefing; --json for agents
  zeo new                    Start intake / SOW / project
  zeo work [stream]          Continue governed work
  zeo next [--json]          Highest-priority next action
  zeo help                   Progressive help (this file: zeo help --all)
  zeo triage | zeo board     Operator views (legacy: --triage / --board)

USAGE
  zeo <file-or-dir>          Lint a SOW / ruling / boot doc (grades it against canonical).
  zeo --board [path]         Write local STATE.md (gitignored). Path optional (auto-found).
  zeo --triage [path]        The operator worklist: who needs a ruling, a successor, unsticking.
  zeo --promote <stream-dir>  Plan the canonical renames (dry-run, writes nothing).
  zeo --resync-check <upstream> [target]
                                  Report CURRENT / STALE / SKIP per inherited file.
  zeo --resync-apply <upstream> [target]
                                  RE-DERIVE inherited files (UPSTREAM-SHA + transforms).
                                  Skips locally authored files. Never commits or pushes.
  zeo hooks install [path]   Write thin tools/hooks stubs + .git/hooks/pre-commit;
                                  gitignore STATE.md / stream-index.md (local views).
  zeo hooks pre-commit       Run the pre-commit gate (called by the thin stub).
  zeo hooks session-start    SessionStart orientation + local board refresh.
  zeo hooks stop             Stop hook: session-cost log + uncommitted advisory.
  zeo hooks pretooluse-git   PreToolUse advisory before git commit/push.
  zeo init [path] [--cursor|--codex|--gemini|--claude|--agents|--all]
                                  Scaffold a corpus: claude-md/CLAUDE.md marker + root
                                  CLAUDE.md (@import). Tool bridges are opt-in.
  zeo scaffold <project> <stream> [n] [title] [--cursor|--codex|--gemini|--claude|--agents|--all]
                                  Create projects/<project>/CLAUDE.md + Rev-17 SOW under
                                  sow/<stream>/ (wrapper around `zeo sow new`). Bridges opt-in.
  zeo sow new <project> <stream> --title "..." [options]
                                  Create a valid Rev-17 SOW without writing YAML.
                                  Options: --status --done-when --restaufwand --body-from
                                  --spec -|--json|--edit|--interactive
  zeo sow set|add|remove FILE KEY VALUE
                                  Mutate one frontmatter field (or list membership) safely.
  zeo sow draft <project> <stream> --title "..." [--peer human|agent] [--prompt FILE]
                                  Ollama body draft loop; ZEO owns frontmatter.
  zeo sow from-intake FILE [project] [stream]
                                  Lower-level alias for `zeo intake promote`.
  zeo intake [new|open|edit|doctor|context|mission|propose|promote] ...
                                  Frictionless intent capture → grounded SOW promotion.
                                  `zeo intake "title"` creates OPEN intake without YAML.
  zeo doctor PATH | zeo doctor --changed
                                  Actionable readiness check for one SOW (or git-changed files).
  zeo bridges [path] --cursor|--codex|--gemini|--claude|--agents|--all
                                  Install/refresh selected IDE/agent bridges only.
                                  Distinct from --resync-* (doctrine SHA sync).
  zeo equip <repo> [--force|--diff]
                                  Install .claude/ (settings, trunk-guard hook, agents)
                                  + CLAUDE.md into a work repo. Never clobbers by default.
  zeo cold-start <repo-path> [--sows-root PATH] [--project NAME]
                                  RULING-278 s3 Ist-Aufnahme, PARTIAL: checklist items
                                  1/3/8/9/10 only (items 2,4-7 need the stack detector,
                                  not yet shipped -- deferred and named in the output).
                                  Read-only against the target repo; writes ONE SOW,
                                  status: FINDING, into the SOWS repo, never the work repo.
  zeo seat [init|use NAME]
                                  Named GitHub-identity switching (docs/seats.md).
  zeo execution validate PATH | zeo execution import PATH [--out PATH]
                                  Validate or canonicalize a JSON execution receipt.
  zeo dispatch acquire|check-remote|cleanup
                                  Exclusive ownership for unattended mutation (library).
  zeo --inbox <stream> [path]
                                  Show ONE stream's open questions + rulings that answered it.
                                  Path optional - run it from anywhere: zeo --inbox example-stream
  zeo --commit-check-corpus [path]
                                  doctrine(1): a corpus-level pass, once per commit, that
                                  catches a same-tree ruling-number collision --commit-check's
                                  per-file gate cannot see. Does NOT catch the cross-seat race
                                  at either individual commit - the bound is in its own --help
                                  text and in the code, not just this ruling.
  zeo --ruling-index [path]  doctrine(2)/s4: regenerate ruling-index.md WHOLE -
                                  every ruling integer's current owner, plus a TOMBSTONE row
                                  for any integer a `minted_as:` field renumbered away from.
                                  Navigation, not evidence (same caveat as stream-index.md).
  zeo --mint ruling [path]   doctrine(3): the next free ORG-SCOPE ruling integer,
                                  read live off disk. NOT reserved - a concurrent peer can
                                  claim the same one; the race limitation prints on every call.
  zeo --mint sow <stream> [path]
                                  The next SOW n: for one stream (same read locate_stream
                                  already does). Same race limitation, printed every call.
  zeo mint ruling|sow …      Canonical subcommand form of --mint (legacy flags kept).
  zeo index streams|rulings  Canonical form of --stream-index / --ruling-index.
  zeo --stream-index [path]  Write local stream-index.md (gitignored) - stream id → path
                                  (doctrine). Regenerated WHOLE on every run.
  zeo --digest [since] [path]
                                  What happened in a session, read-only, pasteable - folds
                                  in tools/hooks/zeo-digest.sh, same bounding logic (one
                                  author's commits since the last commit by someone else,
                                  or an explicit --since window like 4h/1d).

OPTIONS
  --board            Regenerate local STATE.md (gitignored) from every SOW's frontmatter.
  --stream-index     Regenerate local stream-index.md (gitignored; doctrine) - id-to-path map
                     that `binds:` and requested_by's <stream>#<n> form resolve through.
  --inbox <stream>   A stream's own view: what it's waiting on, what was ruled for it,
                     AND what proactively binds it via `binds:` whether it asked or not.
  --triage           The operator worklist: whom do I help today (six buckets).
  --priority [path]  RULING-279: Nutzwertanalyse ranking of every OPEN/PAUSED/BLOCKED
                     stream (Dringlichkeit/Impact/Restaufwand/Risiko, tokens only,
                     never currency) - top-N funded + next-M near-miss with their
                     Nutzwert delta (s3 opportunity cost, stated not implied). A
                     SEPARATE verb from --triage by design (s5) - does not change
                     --triage's own sort order.
  --top <N>          Funded-stream count for --priority (default 3).
  --near-miss <M>    Near-miss stream count for --priority (default 3).
  --commit-check     At the commit path: a ghost requested_by is an ERROR, not a WARN
                     (doctrine - gate the future; landed ghosts stay WARN).
  --commit-check-corpus [path]
                     doctrine(1): ruling-number collisions, corpus-wide, once per
                     commit - beside --commit-check's per-file pass, not folded into it.
  --ruling-index [path]
                     doctrine(2)/s4: regenerate ruling-index.md whole (owner + any
                     tombstone rows from a `minted_as:` renumber). Navigation, not evidence.
  --mint ruling|sow <stream> [path]
                     Next free integer. Pass --words "four to five words" to
                     RESERVE a canonical stub on disk (exclusive create).
  --words "..."      Slug words for --mint reservation (kebab-normalized).
  --digest [since] [path]
                     example-stream-CHARTER-03 item 4: what happened in a session - commits, rulings
                     and SOWs filed, self-corrections, what's owed, uncosigned org-scope
                     rulings, tree state, session cost. Ports zeo-digest.sh's sections and
                     its author-boundary bounding logic unchanged.
  --quiet            Suppress the per-file SKIP diagnosis blocks (genre-unknown,
                     preschema-block) on a lint run; the named-cause summary counts
                     still print (doctrine item 2).
  --migrate <file>   Generate schema-16 frontmatter for a PRE-SCHEMA file (Class-A only).
                     The body is never regenerated; the gate is the only exit.
  --model <tag>      Claimant model for --migrate (default: gemma4:latest).
  --migrate-check <file>
                     Grade a file as if it must be a conformant SOW (the gate).
  --promote <dir>    DRY-RUN the rename plan for one stream dir: n in git birth order,
                     predecessor, corpus. Writes NOTHING; refuses on any collision.
  --resync-check <upstream> [target]
                     Is an inherited doctrine corpus current? Compares each file's
                     recorded UPSTREAM-SHA against the upstream file now.
  --resync-apply <upstream> [target]
                     Re-derive inherited doctrine from upstream (writes files; no commit).
  hooks install [path]
                     Install thin hook stubs + .git/hooks/pre-commit; gitignore boards.
  hooks pre-commit|session-start|stop|pretooluse-git
                     Hook runners (logic lives in the package; stubs just exec these).
  init [path] [--cursor|--codex|--gemini|--claude|--agents|--all]
                     Scaffold corpus marker + CLAUDE.md entrypoint; bridges opt-in.
  scaffold <project> <stream> [n] [title] [--cursor|--codex|--gemini|--claude|--agents|--all]
                     Scaffold a project workstream SOW (Rev 17); bridges opt-in.
  bridges [path] --cursor|--codex|--gemini|--claude|--agents|--all
                     Install selected IDE/agent bridges (not doctrine --resync-*).
  equip <repo> [--force|--diff]
                     Install .claude/ + CLAUDE.md ALWAYS-tier files. Never clobbers by default.
  --kosten [stream]   Corpus artifact token ESTIMATE + DERIVED USD (fixed tax, SOWs,
                     rulings, waste). Session tokens are NOT here — use --session-cost.
  --repo-cost [path] Ahead-of-work: estimate tokens in a repo/tree and DERIVE USD at
                     --model rates (input-only). Default path: cwd.
  --session-cost     After a run: usage from --transcript or --cost-log × dated rates.
  --transcript <p>   Claude Code JSONL transcript for --session-cost.
  --cost-log <p>     session-costs.jsonl for --session-cost (default under corpus).
  --append-cost-log <p>
                     Append one JSONL session-cost record (for Stop hooks).
  --count-via local|anthropic
                     Token estimator for --kosten/--repo-cost (default local=tiktoken
                     proxy). anthropic uses the free count_tokens endpoint (API key).
  --calibrate        With local estimator: sample fixed-tax files via Anthropic and
                     scale the walk by the ratio (needs an Anthropic API credential).
  --api-key-env <VARNAME>
                     Env var name to read the Anthropic API key from for
                     --count-via anthropic / --calibrate (default ANTHROPIC_API_KEY).
                     RULING-279 s4/s5: a narrow escape hatch for a credential under a
                     non-default variable name — NOT full ant-CLI-equivalent
                     credential-chain resolution, which is out of scope.
  --json             Machine-readable JSON for --repo-cost / --session-cost / --kosten.
  --model <id>       Rate-table model for cost verbs (default from model_rates.toml);
                     also the claimant model tag for --migrate.
  --claude-md <p>    Override the canonical CLAUDE.md path (default: auto-discovered).
  --skill <p>        Grade a specific skill/boot doc for currency.

The sows repo is auto-discovered by walking up to a claude-md/CLAUDE.md marker,
so --board and --inbox need NO path when you're in or near the repo.

Legacy aliases remain supported (--board, --triage, --stream-index, --ruling-index, --digest, --mint)."""


def _wants_help(argv: list[str]) -> bool:
    """RULING-329: a shared, explicit -h/--help check for any mutating verb whose own
    positional-argument requirements are too loose to catch a bare --help by accident
    (e.g. `init`/`equip` both accept ZERO required positionals - a bare `zeo init`
    is legitimate, "scaffold cwd" - so `--help` alone used to fall through
    `positionals = [a for a in argv if not a.startswith("-")]` as an EMPTY list,
    indistinguishable from "no target given, use cwd", and the real mutation ran.
    MEASURED live: `zeo init --help` in an empty directory wrote a full corpus scaffold
    to disk instead of printing usage. Any verb whose argument-count check alone cannot
    already reject a bare --help (scaffold/bridges are safe BY ACCIDENT - they both
    require a non-optional positional/flag argv --help can never satisfy) must call
    this before touching disk."""
    return "-h" in argv or "--help" in argv


def _cmd_init(argv: list[str]) -> int:
    if _wants_help(argv):
        print(
            "Usage: zeo init [path] [--cursor] [--codex] [--gemini] [--claude] [--agents] [--all]\n"
            "  Scaffold a corpus: claude-md/CLAUDE.md marker + root CLAUDE.md.\n"
            "  path defaults to the current directory. Read-only with -h/--help.",
            file=sys.stderr,
        )
        return 0
    tools = parse_tool_flags(argv)
    positionals = [a for a in argv if not str(a).startswith("-")]
    target = pathlib.Path(positionals[0]).resolve() if positionals else pathlib.Path(".").resolve()
    info = init_corpus(target, tools=tools)
    print(f"INIT: corpus at {info['root']}")
    for c in info["created"]:
        print(f"  + {c}")
    if not info["created"]:
        print("  (marker/entrypoint already present)")
    b = info["bridges"]
    if b.get("tools"):
        print(f"  bridges: {', '.join(b['tools'])}")
        for act in b.get("actions", []):
            print(f"    {act['action']}: {act['path']}")
    else:
        print("  bridges: (none — pass --cursor/--codex/--gemini/--claude/--agents/--all)")
    print("")
    print("Next:")
    print("")
    print("  Human:")
    print("    zeo")
    print("")
    print("  Claude Code / Codex:")
    print("    zeo orient --json")
    print("")
    print("Try it now:")
    print("    zeo new")
    return 0


def _cmd_help(argv: list[str]) -> int:
    from .orient import HELP_TOPICS, render_help_root

    if any(a in ("--all", "-a") for a in argv):
        print(_USAGE)
        return 0
    topic = next((a for a in argv if not str(a).startswith("-")), None)
    if topic:
        body = HELP_TOPICS.get(topic.lower())
        if body is None:
            print(f"zeo help: unknown topic {topic!r}", file=sys.stderr)
            print("Topics: " + ", ".join(sorted(HELP_TOPICS)), file=sys.stderr)
            print("Or: zeo help --all", file=sys.stderr)
            return 2
        print(body, end="" if body.endswith("\n") else "\n")
        return 0
    print(render_help_root(), end="")
    return 0


def _cmd_orient(argv: list[str]) -> int:
    from .orient import (
        build_orientation,
        dumps_json,
        orientation_to_dict,
        render_orientation_human,
    )

    want_json = "--json" in argv
    stream = None
    i = 0
    while i < len(argv):
        if argv[i] == "--stream" and i + 1 < len(argv):
            stream = argv[i + 1]
            i += 2
        elif argv[i] == "--json":
            i += 1
        elif argv[i] in ("--help", "-h"):
            print("Usage: zeo orient [--stream NAME] [--json]")
            return 0
        elif not str(argv[i]).startswith("-"):
            # optional path
            i += 1
        else:
            i += 1
    path_args = [a for a in argv if not str(a).startswith("-") and a != stream]
    explicit = path_args[0] if path_args else None
    root = _discover_root(explicit)
    o = build_orientation(root=root, stream=stream)
    if want_json:
        print(dumps_json(orientation_to_dict(o)), end="")
        return 0
    print(render_orientation_human(o), end="")
    return 0


def _cmd_new(argv: list[str]) -> int:
    from .orient import NEW_CHOICES, dumps_json, new_choices_to_dict, render_new_menu_human

    want_json = "--json" in argv
    if want_json:
        print(dumps_json(new_choices_to_dict()), end="")
        return 0

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(render_new_menu_human(), end="")
        return 0

    print(render_new_menu_human(), end="")
    try:
        choice = input("Choice [1-3]: ").strip()
    except EOFError:
        return 0
    if not choice:
        return 0
    try:
        n = int(choice)
    except ValueError:
        print(f"zeo new: invalid choice {choice!r}", file=sys.stderr)
        return 2
    selected = next((c for c in NEW_CHOICES if c["id"] == n), None)
    if selected is None:
        print("zeo new: choose 1, 2, or 3", file=sys.stderr)
        return 2

    if selected["key"] == "intake":
        title = input("Intake title: ").strip()
        if not title:
            print("zeo new: title required", file=sys.stderr)
            return 2
        return _cmd_intake(["new", "--title", title])
    if selected["key"] == "sow":
        project = input("Project: ").strip()
        stream = input("Stream: ").strip()
        title = input("Title: ").strip()
        if not project or not stream or not title:
            print("zeo new: project, stream, and title are required", file=sys.stderr)
            return 2
        return _cmd_sow(["new", project, stream, "--title", title])
    if selected["key"] == "project":
        project = input("Project: ").strip()
        stream = input("Stream: ").strip()
        title = input("Title [Initial Workstream SOW]: ").strip() or "Initial Workstream SOW"
        if not project or not stream:
            print("zeo new: project and stream are required", file=sys.stderr)
            return 2
        return _cmd_scaffold([project, stream, "1", title])
    return 2


def _cmd_work(argv: list[str]) -> int:
    from .orient import (
        build_stream_detail,
        build_work_listing,
        dumps_json,
        render_stream_detail_human,
        render_work_listing_human,
    )

    want_json = "--json" in argv
    args = [a for a in argv if a != "--json" and a not in ("--help", "-h")]
    if any(a in ("--help", "-h") for a in argv):
        print("Usage: zeo work [stream|.] [--json]")
        return 0

    root = _discover_root(None)
    if root is None:
        print(
            "zeo work: couldn't find a corpus. Run from inside one or set ZEO_SOWS_ROOT.",
            file=sys.stderr,
        )
        return 2

    target = args[0] if args else None
    if target in (None,):
        listing = build_work_listing(root)
        if want_json:
            from dataclasses import asdict

            print(
                dumps_json(
                    {
                        "protocol_version": 1,
                        "active": [asdict(x) for x in listing.active],
                        "waiting_on_you": [asdict(x) for x in listing.waiting_on_you],
                        "recently_touched": [asdict(x) for x in listing.recently_touched],
                        "open_intakes": listing.open_intakes,
                    }
                ),
                end="",
            )
            return 0
        print(render_work_listing_human(listing), end="")
        return 0

    stream = target
    if target == ".":
        from .orient import build_orientation

        o = build_orientation(root=root)
        ctx = o.active_context
        if not ctx or ctx.kind != "stream" or not ctx.stream:
            print("zeo work .: not inside a stream directory", file=sys.stderr)
            return 2
        stream = ctx.stream

    detail = build_stream_detail(root, stream)
    if want_json:
        print(dumps_json(detail), end="")
        return 0 if detail.get("found") else 2
    print(render_stream_detail_human(detail), end="")
    return 0 if detail.get("found") else 2


def _cmd_next(argv: list[str]) -> int:
    from .orient import build_next_action, dumps_json, next_action_to_dict, render_next_action_human

    want_json = "--json" in argv
    stream = None
    i = 0
    while i < len(argv):
        if argv[i] == "--stream" and i + 1 < len(argv):
            stream = argv[i + 1]
            i += 2
        else:
            i += 1
    root = _discover_root(None)
    n = build_next_action(root=root, stream=stream)
    if want_json:
        print(dumps_json(next_action_to_dict(n)), end="")
        return 0
    print(render_next_action_human(n), end="")
    return 0


def _cmd_board_alias(argv: list[str]) -> int:
    repair = "--repair" in argv
    path = next((a for a in argv if not str(a).startswith("-")), None)
    root = _discover_root(path)
    if root is None:
        print("zeo board: couldn't find a corpus.", file=sys.stderr)
        return 2
    return _board(root, repair=repair)


def _cmd_branches(argv: list[str]) -> int:
    """zeo branches [path] [--trunk NAME] [--json]

    Classifies every branch (excluding trunk) in the git repo at `path` (default:
    cwd, walked up like every other verb) into exactly one of the five RULING-324
    states: LIVE / STALE-BASE / ORPHANED / MERGED / RESCUE. REPORTS ONLY — this
    verb never mutates, never deletes, never touches a ref. Charter's own explicit
    line: "never auto-delete, rescue/* least of all."

    Note this operates on a plain git repo, not necessarily a SOW corpus — unlike
    board/triage/digest it does NOT require `claude-md/CLAUDE.md` to resolve `path`
    (a work_repo like zero-employee or ducktyper is a valid, expected target and
    carries no such marker). An explicit path (or cwd) is used as-is if it is a git
    repo; the corpus-marker walk-up is only a fallback for the bare, no-path case.
    """
    positionals = [a for a in argv if not str(a).startswith("-")]
    trunk = "main"
    want_json = "--json" in argv
    if "--trunk" in argv:
        ti = argv.index("--trunk")
        if ti + 1 < len(argv):
            trunk = argv[ti + 1]
            if trunk in positionals:
                positionals.remove(trunk)
    path = positionals[0] if positionals else None
    root = pathlib.Path(path).resolve() if path else pathlib.Path(".").resolve()
    toplevel = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if toplevel.returncode != 0:
        print(f"zeo branches: {root} is not a git repo.", file=sys.stderr)
        return 2
    root = pathlib.Path(toplevel.stdout.strip())

    rows = classify_all_branches(root, trunk=trunk)
    if want_json:
        import json

        print(json.dumps({"root": str(root), "trunk": trunk, "branches": rows}, indent=2))
        return 0

    print(f"branches: {root}  (trunk=origin/{trunk}, LIVE_BEHIND_THRESHOLD={LIVE_BEHIND_THRESHOLD})")
    if not rows:
        print("  (no branches other than trunk)")
        return 0
    width = max(len(r["branch"]) for r in rows)
    for r in rows:
        ab = f"ahead={r['ahead']}, behind={r['behind']}" if r["ahead"] is not None else "ahead=?, behind=?"
        print(f"  {r['branch']:<{width}}  {r['state']:<11}  {ab}")
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    print("  --")
    print("  " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return 0


def _cmd_check_base_fresh(argv: list[str]) -> int:
    """zeo check-base-fresh [path] [--trunk NAME]

    branch-gates charter item 3. Exit 0 when HEAD's merge-base with origin/<trunk>
    IS origin/<trunk>'s current tip (nothing to rebase onto); exit 1 when it is NOT
    (stale — rebase before continuing); exit 2 when freshness cannot be determined
    (no origin/<trunk> ref, unreadable HEAD, unrelated history) — a caller that
    cannot prove freshness must not report success. Designed for a boot-time
    one-liner (see `make check-base-fresh`) so a seat's FIRST act can fail loudly
    on a stale base rather than build on one silently.
    """
    positionals = [a for a in argv if not str(a).startswith("-")]
    trunk = "main"
    if "--trunk" in argv:
        ti = argv.index("--trunk")
        if ti + 1 < len(argv):
            trunk = argv[ti + 1]
            if trunk in positionals:
                positionals.remove(trunk)
    path = positionals[0] if positionals else None
    root = pathlib.Path(path).resolve() if path else pathlib.Path(".").resolve()
    toplevel = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if toplevel.returncode != 0:
        print(f"zeo check-base-fresh: {root} is not a git repo.", file=sys.stderr)
        return 2
    root = pathlib.Path(toplevel.stdout.strip())

    result = check_base_fresh(root, trunk=trunk)
    if result["fresh"] is None:
        print(f"check-base-fresh: UNKNOWN — {result['reason']}", file=sys.stderr)
        return 2
    if result["fresh"]:
        print(f"check-base-fresh: FRESH — {result['reason']}")
        return 0
    print(f"check-base-fresh: STALE — {result['reason']}", file=sys.stderr)
    print(f"  Fix: git fetch origin && git rebase {result['trunk_ref']}", file=sys.stderr)
    return 1


def _cmd_triage_alias(argv: list[str]) -> int:
    path = next((a for a in argv if not str(a).startswith("-")), None)
    root = _discover_root(path)
    if root is None:
        print("zeo triage: couldn't find a corpus.", file=sys.stderr)
        return 2
    return _triage(root)


def _cmd_digest_alias(argv: list[str]) -> int:
    # Optional since duration, optional path — mirror --digest parsing
    since = None
    path = None
    positionals = [a for a in argv if not str(a).startswith("-")]
    if positionals:
        first = positionals[0]
        if not pathlib.Path(first).exists() and not first.startswith("/") and len(first) < 8:
            # treat as duration like 4h/1d when it doesn't look like a path
            since = first
            path = positionals[1] if len(positionals) > 1 else None
        else:
            path = first
    root = _discover_root(path)
    if root is None:
        print("zeo digest: couldn't find a corpus.", file=sys.stderr)
        return 2
    return _digest(root, since)


def _cmd_index(argv: list[str]) -> int:
    if not argv or argv[0] in ("--help", "-h"):
        print("Usage: zeo index streams|rulings [path]", file=sys.stderr)
        return 2
    kind = argv[0]
    path = next((a for a in argv[1:] if not str(a).startswith("-")), None)
    root = _discover_root(path)
    if root is None:
        print("zeo index: couldn't find a corpus.", file=sys.stderr)
        return 2
    if kind in ("streams", "stream"):
        return _stream_index_cmd(root)
    if kind in ("rulings", "ruling"):
        return _ruling_index(root)
    print(f"zeo index: unknown kind {kind!r} (streams|rulings)", file=sys.stderr)
    return 2


def _cmd_mint_alias(argv: list[str]) -> int:
    if not argv or argv[0] in ("--help", "-h"):
        print("Usage: zeo mint ruling|sow [stream] [--words '...'] [path]", file=sys.stderr)
        return 2
    kind = argv[0]
    rest = argv[1:]
    words = None
    stream = None
    path = None
    i = 0
    positionals: list[str] = []
    while i < len(rest):
        if rest[i] == "--words" and i + 1 < len(rest):
            words = rest[i + 1]
            i += 2
        elif not str(rest[i]).startswith("-"):
            positionals.append(rest[i])
            i += 1
        else:
            i += 1
    if kind == "sow":
        if not positionals:
            print("Usage: zeo mint sow <stream> [path]", file=sys.stderr)
            return 2
        stream = positionals[0]
        path = positionals[1] if len(positionals) > 1 else None
    else:
        path = positionals[0] if positionals else None
    if kind not in ("ruling", "sow"):
        print(f"zeo mint: unknown kind {kind!r}", file=sys.stderr)
        return 2
    root = _discover_root(path)
    if root is None:
        print("zeo mint: couldn't find a corpus.", file=sys.stderr)
        return 2
    return _mint(root, kind, stream, words=words)


def _cmd_scaffold(argv: list[str]) -> int:
    tools = parse_tool_flags(argv)
    positionals = [a for a in argv if not str(a).startswith("-")]
    if len(positionals) < 2:
        print(
            "Usage: zeo scaffold <project> <stream> [n] [title] [--cursor] [--codex] [--gemini] [--claude] [--agents] [--all]",
            file=sys.stderr,
        )
        return 2
    project, stream = positionals[0], positionals[1]
    sow_num = 1
    title = "Initial Workstream SOW"
    rest = positionals[2:]
    if rest and rest[0].isdigit():
        sow_num = int(rest[0])
        rest = rest[1:]
    if rest:
        title = " ".join(rest)
    root = _discover_root(None) or pathlib.Path(".").resolve()
    # Prefer cwd if it already has the marker (scaffold into current corpus).
    cwd = pathlib.Path(".").resolve()
    if (cwd / "claude-md" / "CLAUDE.md").is_file():
        root = cwd
    try:
        info = scaffold_project_stream(root, project, stream, sow_num=sow_num, title=title, tools=tools)
    except FileNotFoundError as e:
        print(f"scaffold: {e}", file=sys.stderr)
        return 2
    tool_str = f" with tools: {', '.join(info['bridges']['tools'])}" if info["bridges"].get("tools") else " (core only)"
    print(f"SCAFFOLD: {info.get('sow')}{tool_str}")
    for c in info["created"]:
        print(f"  + {c}")
    for act in info["bridges"].get("actions", []):
        print(f"  {act['action']}: {act['path']}")
    return 0


def _cmd_bridges(argv: list[str]) -> int:
    tools = parse_tool_flags(argv)
    if not tools:
        print(
            "Usage: zeo bridges [path] --cursor|--codex|--gemini|--claude|--agents|--all",
            file=sys.stderr,
        )
        return 2
    positionals = [a for a in argv if not str(a).startswith("-")]
    target = pathlib.Path(positionals[0]).resolve() if positionals else pathlib.Path(".").resolve()
    info = install_bridges(target, tools=tools)
    print(f"BRIDGES: {', '.join(info['tools'])} at {info['root']}")
    for act in info.get("actions", []):
        print(f"  {act['action']}: {act['path']}")
    return 0


def _cmd_cold_start(argv: list[str]) -> int:
    """COLD-START-SOW-2: `zeo cold-start <repo-path>` — RULING-278 s3 checklist
    items 1, 3, 8, 9, 10 only (items 2, 4-7 need REPO-EQUIP-SOW-1's stack
    detector, not yet shipped; deferred and named plainly in the output SOW).

    SAFETY (RULING-278 s5 / COLD-START-SOW-1 s3, the load-bearing property):
    zero commits, zero file writes, into the TARGET work repo. Every survey
    item below is a read-only git/gh/grep/test call; the ONE write this verb
    performs lands in the SOWS repo, under
    projects/<project>/sow/cold-start/<PROJECT>-COLD-START-SOW-01-ist-aufnahme.md
    -- never under the surveyed repo itself.
    """
    from .cold_start import derive_project_name, run_partial_survey, write_ist_aufnahme_sow

    positionals = [a for a in argv if not str(a).startswith("-")]
    if not positionals:
        print("Usage: zeo cold-start <repo-path> [--sows-root PATH] [--project NAME]", file=sys.stderr)
        return 2
    target = pathlib.Path(positionals[0]).resolve()
    if not target.is_dir():
        print(f"zeo cold-start: not a directory: {target}", file=sys.stderr)
        return 2

    sows_root_override = None
    project_override = None
    i = 0
    while i < len(argv):
        if argv[i] == "--sows-root" and i + 1 < len(argv):
            sows_root_override = pathlib.Path(argv[i + 1]).resolve()
            i += 2
            continue
        if argv[i] == "--project" and i + 1 < len(argv):
            project_override = argv[i + 1]
            i += 2
            continue
        i += 1

    sows_root = sows_root_override or _discover_root(None)
    if sows_root is None:
        print(
            "zeo cold-start: couldn't find the SOWS repo (no claude-md/CLAUDE.md above cwd). "
            "Pass --sows-root or run from inside the sows corpus.",
            file=sys.stderr,
        )
        return 2

    try:
        survey = run_partial_survey(target)
    except FileNotFoundError as e:
        print(f"zeo cold-start: {e}", file=sys.stderr)
        return 2

    project = project_override or derive_project_name(target)
    result = write_ist_aufnahme_sow(sows_root, project, survey)
    if not result["ok"]:
        print(f"zeo cold-start: SOW write failed: {result['reason']}", file=sys.stderr)
        for f in result.get("findings") or []:
            print(f"    {_SYM.get(f.severity, '?')} [{f.code}] {f.message}", file=sys.stderr)
        return 1

    print(f"COLD-START: partial Ist-Aufnahme survey of {target}")
    print(f"  ran items: {', '.join(str(i) for i in survey['ran_items'])}")
    print(
        f"  deferred items: {', '.join(str(n) for n, _name, _why in survey['deferred_items'])} (need the stack detector)"
    )
    print(f"  SOW written: {result['path']}")
    print("  zero commits, zero writes made to the target work repo (survey is read-only)")
    return 0


def _cmd_equip(argv: list[str]) -> int:
    """REPO-EQUIP-SOW-5 (step 2 of REPO-EQUIP-SOW-1): `zeo equip <repo>`.

    Installs the ALWAYS-tier .claude/ + CLAUDE.md files into a work repo.
    Never clobbers by default; `--force` overwrites; `--diff` previews only.
    --gates / override layer / --resync-check visibility / --all are NOT
    built here -- steps 3-6 of the charter, out of scope for this verb today.
    """
    if _wants_help(argv):
        print(
            "Usage: zeo equip [repo] [--force] [--diff]\n"
            "  Install the ALWAYS-tier .claude/ + CLAUDE.md files into a work repo.\n"
            "  repo defaults to the current directory. Read-only with -h/--help.",
            file=sys.stderr,
        )
        return 0
    force = "--force" in argv
    show_diff = "--diff" in argv
    if force and show_diff:
        print("zeo equip: --force and --diff are mutually exclusive", file=sys.stderr)
        return 2
    positionals = [a for a in argv if not str(a).startswith("-")]
    target = pathlib.Path(positionals[0]).resolve() if positionals else pathlib.Path(".").resolve()
    if not target.is_dir():
        print(f"zeo equip: not a directory: {target}", file=sys.stderr)
        return 2

    info = equip_repo(target, force=force, diff=show_diff)
    label = "DIFF" if show_diff else "EQUIP"
    print(f"{label}: {info['root']}")
    exit_code = 0
    for act in info["actions"]:
        action = act["action"]
        if show_diff:
            if action == "would-create":
                print(f"  would create: {act['path']}")
                exit_code = exit_code or 1
            elif action == "would-change":
                print(f"  would change: {act['path']}")
                diff_text = act.get("diff") or ""
                for line in diff_text.splitlines():
                    print(f"    {line}")
                exit_code = exit_code or 1
            else:
                print(f"  unchanged: {act['path']}")
        else:
            print(f"  {action}: {act['path']}")
    return exit_code


def _parse_sow_flags(argv: list[str]) -> tuple[list[str], dict]:
    """Return (positionals, flags) for sow subcommands."""
    flags: dict = {
        "title": None,
        "status": None,
        "lifecycle": None,
        "done_when": None,
        "restaufwand": None,
        "body_from": None,
        "prompt": None,
        "spec": None,
        "json": False,
        "edit": False,
        "interactive": False,
        "peer": "human",
        "model": None,
        "project": None,
        "stream": None,
        "changed": False,
    }
    positionals: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--title" and i + 1 < len(argv):
            flags["title"] = argv[i + 1]
            i += 2
            continue
        if a == "--status" and i + 1 < len(argv):
            flags["status"] = argv[i + 1]
            i += 2
            continue
        if a == "--lifecycle" and i + 1 < len(argv):
            flags["lifecycle"] = argv[i + 1]
            i += 2
            continue
        if a in ("--done-when", "--done_when") and i + 1 < len(argv):
            flags["done_when"] = argv[i + 1]
            i += 2
            continue
        if a == "--restaufwand" and i + 1 < len(argv):
            flags["restaufwand"] = argv[i + 1]
            i += 2
            continue
        if a == "--body-from" and i + 1 < len(argv):
            flags["body_from"] = argv[i + 1]
            i += 2
            continue
        if a == "--prompt" and i + 1 < len(argv):
            flags["prompt"] = argv[i + 1]
            i += 2
            continue
        if a == "--spec" and i + 1 < len(argv):
            flags["spec"] = argv[i + 1]
            i += 2
            continue
        if a == "--peer" and i + 1 < len(argv):
            flags["peer"] = argv[i + 1]
            i += 2
            continue
        if a == "--model" and i + 1 < len(argv):
            flags["model"] = argv[i + 1]
            i += 2
            continue
        if a == "--project" and i + 1 < len(argv):
            flags["project"] = argv[i + 1]
            i += 2
            continue
        if a == "--stream" and i + 1 < len(argv):
            flags["stream"] = argv[i + 1]
            i += 2
            continue
        if a == "--json":
            flags["json"] = True
            i += 1
            continue
        if a == "--edit":
            flags["edit"] = True
            i += 1
            continue
        if a == "--interactive":
            flags["interactive"] = True
            i += 1
            continue
        if a == "--changed":
            flags["changed"] = True
            i += 1
            continue
        if a.startswith("-"):
            print(f"zeo sow: unknown flag {a}", file=sys.stderr)
            return [], {"_error": 2}
        positionals.append(a)
        i += 1
    return positionals, flags


def _print_sow_created(result, *, as_json: bool = False) -> None:
    import json as _json

    from .sow_authoring import SCHEMA_REV

    if as_json:
        print(_json.dumps(result.model_dump(), indent=2))
        return
    print("Created:")
    print(f"  {result.path}")
    print()
    print(f"schema_rev: {SCHEMA_REV}")
    print(f"project: {result.project}")
    print(f"sow: {result.sow}")
    print(f"n: {result.n}")
    print(f"status: {result.status}")
    print(f"lifecycle: {result.lifecycle}")
    print()
    for check in result.checks:
        print(f"✓ {check}")


def _interactive_sow_prompts(flags: dict) -> dict:
    from .sow_authoring import KIND_MAP

    title = flags.get("title") or input("Title: ").strip()
    print("What kind of work is this?")
    print("  1. Design")
    print("  2. Implementation")
    print("  3. Finding")
    print("  4. Handover")
    print("  5. Closeout")
    kind = input("> ").strip().lower() or "1"
    status, lifecycle = KIND_MAP.get(kind, ("DESIGN", "DESIGN-MEMO"))
    done_when = flags.get("done_when") or input("Done when:\n> ").strip()
    rest_raw = flags.get("restaufwand") or input("Estimated remaining units:\n> ").strip() or "1"
    return {
        "title": title,
        "status": status,
        "lifecycle": lifecycle,
        "done_when": done_when,
        "restaufwand": rest_raw,
    }


def _cmd_sow(argv: list[str]) -> int:
    import os

    from .ollama_client import DEFAULT_MODEL
    from .sow_authoring import (
        add_list_value,
        create_sow,
        create_sow_from_spec,
        draft_sow,
        remove_list_value,
        set_field,
    )

    if not argv:
        print(
            "Usage: zeo sow new|set|add|remove|draft|from-intake|doctor ...",
            file=sys.stderr,
        )
        return 2

    sub = argv[0]
    rest = argv[1:]
    positionals, flags = _parse_sow_flags(rest)
    if flags.get("_error"):
        return 2

    root = _discover_root(None) or pathlib.Path(".").resolve()
    cwd = pathlib.Path(".").resolve()
    if (cwd / "claude-md" / "CLAUDE.md").is_file():
        root = cwd

    if sub == "doctor":
        return _cmd_doctor(positionals, flags, root)

    if sub == "new":
        if flags.get("spec") is not None:
            spec, spec_err = _load_spec_json(flags["spec"])
            if spec_err:
                print(f"zeo sow new: {spec_err}", file=sys.stderr)
                return 1
            result, err = create_sow_from_spec(root, spec, cwd=cwd)
            if result is None:
                print(f"✗ SOW not written\nReason: {err}", file=sys.stderr)
                return 1
            _print_sow_created(result, as_json=flags["json"])
            return 0

        project = flags.get("project")
        stream = flags.get("stream")
        if len(positionals) >= 2:
            project, stream = positionals[0], positionals[1]
        elif len(positionals) == 1 and not project:
            stream = positionals[0]

        if flags.get("interactive"):
            answers = _interactive_sow_prompts(flags)
            flags.update(answers)

        title = flags.get("title")
        if not title:
            print("zeo sow new: --title is required (or use --interactive / --spec)", file=sys.stderr)
            return 2

        body = None
        if flags.get("body_from"):
            body = pathlib.Path(flags["body_from"]).read_text(encoding="utf-8")

        status = flags.get("status") or "DESIGN"
        lifecycle = flags.get("lifecycle")
        if flags.get("interactive") and not lifecycle:
            lifecycle = flags.get("lifecycle")

        restaufwand = flags.get("restaufwand")
        if restaufwand is not None and str(restaufwand).isdigit():
            restaufwand = int(restaufwand)

        result, err = create_sow(
            root,
            project=project,
            stream=stream,
            title=title,
            status=status,
            lifecycle=lifecycle,
            done_when=flags.get("done_when"),
            restaufwand=restaufwand,
            body=body,
            cwd=cwd,
        )
        if result is None:
            print(f"✗ SOW not written\nReason: {err}", file=sys.stderr)
            return 1
        _print_sow_created(result, as_json=flags["json"])
        path = root / result.path
        if flags.get("edit"):
            editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
            subprocess.call([editor, str(path)])
        elif sys.stdin.isatty() and not flags["json"]:
            try:
                ans = input("\nEdit body now? [Y/n] ").strip().lower()
            except EOFError:
                ans = "n"
            if ans in ("", "y", "yes"):
                editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
                subprocess.call([editor, str(path)])
        return 0

    if sub == "set":
        if len(positionals) < 3:
            print("Usage: zeo sow set FILE KEY VALUE", file=sys.stderr)
            return 2
        path = pathlib.Path(positionals[0]).resolve()
        key, value = positionals[1], " ".join(positionals[2:])
        ok, reason = set_field(path, key, value, root=root)
        if not ok:
            print(f"✗ SOW not updated\nReason: {reason}", file=sys.stderr)
            return 1
        print(f"Updated {path}: {key}={value}")
        return 0

    if sub == "add":
        if len(positionals) < 3:
            print("Usage: zeo sow add FILE KEY VALUE", file=sys.stderr)
            return 2
        path = pathlib.Path(positionals[0]).resolve()
        key, value = positionals[1], " ".join(positionals[2:])
        ok, reason = add_list_value(path, key, value, root=root)
        if not ok:
            print(f"✗ SOW not updated\nReason: {reason}", file=sys.stderr)
            return 1
        print(f"Added {value!r} to {key} in {path}")
        return 0

    if sub == "remove":
        if len(positionals) < 3:
            print("Usage: zeo sow remove FILE KEY VALUE", file=sys.stderr)
            return 2
        path = pathlib.Path(positionals[0]).resolve()
        key, value = positionals[1], " ".join(positionals[2:])
        ok, reason = remove_list_value(path, key, value, root=root)
        if not ok:
            print(f"✗ SOW not updated\nReason: {reason}", file=sys.stderr)
            return 1
        print(f"Removed {value!r} from {key} in {path}")
        return 0

    if sub == "draft":
        project = flags.get("project")
        stream = flags.get("stream")
        if len(positionals) >= 2:
            project, stream = positionals[0], positionals[1]
        title = flags.get("title")
        if not title and flags["peer"] == "human":
            print("zeo sow draft: --title is required", file=sys.stderr)
            return 2
        seed = ""
        if flags.get("prompt"):
            seed = pathlib.Path(flags["prompt"]).read_text(encoding="utf-8")
        restaufwand = flags.get("restaufwand")
        if restaufwand is not None and str(restaufwand).isdigit():
            restaufwand = int(restaufwand)
        result, err = draft_sow(
            root,
            project=project,
            stream=stream,
            title=title or "Draft SOW",
            status=flags.get("status") or "DESIGN",
            done_when=flags.get("done_when"),
            restaufwand=restaufwand,
            peer=flags.get("peer") or "human",
            model_tag=flags.get("model") or DEFAULT_MODEL,
            seed_prompt=seed,
        )
        if result is None:
            print(f"✗ SOW not written\nReason: {err}", file=sys.stderr)
            return 1
        if flags["json"]:
            _print_sow_created(result, as_json=True)
        return 0

    if sub == "from-intake":
        return _cmd_intake(["promote", *rest])

    print(f"zeo sow: unknown subcommand {sub!r}", file=sys.stderr)
    return 2


def _cmd_intake(argv: list[str]) -> int:
    """Frictionless intake capture and grounded promotion."""
    import json as _json
    import os
    import tempfile

    from .intake_authoring import (
        build_mission,
        create_intake,
        create_intake_from_spec,
        doctor_intake,
        gather_context,
        intake_identity,
        list_intakes,
        load_intake,
        load_proposal,
        open_editor_template,
        parse_intake_sections,
        promote_intake,
        propose_intake,
        resolve_intake_path,
        status_counts,
    )

    root = _discover_root(None) or pathlib.Path(".").resolve()
    cwd = pathlib.Path(".").resolve()
    if (cwd / "claude-md" / "CLAUDE.md").is_file():
        root = cwd

    def _want_json(args: list[str]) -> bool:
        return "--json" in args

    def _parse_intake_new_flags(args: list[str]) -> tuple[list[str], dict]:
        flags: dict = {
            "title": None,
            "what": None,
            "why": None,
            "done_when": None,
            "not_this": [],
            "context": [],
            "spec": None,
            "from": None,
            "stdin": False,
            "json": False,
            "project_hint": None,
            "stream_hint": None,
            "edit": False,
        }
        positionals: list[str] = []
        i = 0
        while i < len(args):
            a = args[i]
            if a == "--title" and i + 1 < len(args):
                flags["title"] = args[i + 1]
                i += 2
            elif a == "--what" and i + 1 < len(args):
                flags["what"] = args[i + 1]
                i += 2
            elif a == "--why" and i + 1 < len(args):
                flags["why"] = args[i + 1]
                i += 2
            elif a in ("--done-when", "--done_when") and i + 1 < len(args):
                flags["done_when"] = args[i + 1]
                i += 2
            elif a in ("--not-this", "--not_this") and i + 1 < len(args):
                flags["not_this"].append(args[i + 1])
                i += 2
            elif a == "--context" and i + 1 < len(args):
                flags["context"].append(args[i + 1])
                i += 2
            elif a == "--spec" and i + 1 < len(args):
                flags["spec"] = args[i + 1]
                i += 2
            elif a == "--from" and i + 1 < len(args):
                flags["from"] = args[i + 1]
                i += 2
            elif a == "--stdin":
                flags["stdin"] = True
                i += 1
            elif a == "--json":
                flags["json"] = True
                i += 1
            elif a == "--edit":
                flags["edit"] = True
                i += 1
            elif a in ("--project-hint", "--project") and i + 1 < len(args):
                flags["project_hint"] = args[i + 1]
                i += 2
            elif a in ("--stream-hint", "--stream") and i + 1 < len(args):
                flags["stream_hint"] = args[i + 1]
                i += 2
            elif a.startswith("-"):
                print(f"zeo intake: unknown flag {a}", file=sys.stderr)
                flags["_error"] = True
                return positionals, flags
            else:
                positionals.append(a)
                i += 1
        return positionals, flags

    if not argv:
        counts = status_counts(root)
        for st, n in counts.items():
            print(f"{st:12}{n}")
        return 0

    known = {
        "new",
        "open",
        "edit",
        "doctor",
        "context",
        "mission",
        "investigate",
        "propose",
        "promote",
        "list",
        "status",
    }
    if argv[0] not in known and not argv[0].startswith("-"):
        result, err = create_intake(root, title=" ".join(argv))
        if result is None:
            print(f"✗ intake not written\nReason: {err}", file=sys.stderr)
            return 1
        print(f"Created {result.path}")
        return 0

    sub = argv[0]
    rest = argv[1:]

    if sub == "status":
        counts = status_counts(root)
        for st, n in counts.items():
            print(f"{st:12}{n}")
        return 0

    if sub in ("open", "list"):
        rows = [r for r in list_intakes(root) if r["status"] == "OPEN"]
        if _want_json(rest):
            print(_json.dumps(rows, indent=2, default=str))
            return 0
        if not rows:
            print("(no OPEN intakes)")
            return 0
        for r in rows:
            print(f"OPEN  {r['id']}  project={r['project']}  filed {r['created']}")
        return 0

    if sub == "new":
        positionals, flags = _parse_intake_new_flags(rest)
        if flags.get("_error"):
            return 2
        if flags.get("spec") is not None:
            spec, spec_err = _load_spec_json(flags["spec"])
            if spec_err:
                print(f"zeo intake new: {spec_err}", file=sys.stderr)
                return 1
            result, err = create_intake_from_spec(root, spec)
            if result is None:
                print(f"✗ intake not written\nReason: {err}", file=sys.stderr)
                return 1
            if flags["json"]:
                print(result.model_dump_json(indent=2))
            else:
                print(f"Created {result.path}")
            return 0

        raw_body = None
        if flags["stdin"]:
            raw_body = sys.stdin.read()
        elif flags.get("from"):
            raw_body = pathlib.Path(flags["from"]).read_text(encoding="utf-8")
        elif not sys.stdin.isatty() and not flags.get("what") and not flags.get("title") and not positionals:
            raw_body = sys.stdin.read()

        title = flags.get("title")
        if positionals and not title:
            title = " ".join(positionals)

        only_title = (
            title
            and not flags.get("what")
            and raw_body is None
            and not flags.get("why")
            and not flags.get("done_when")
            and not flags.get("not_this")
            and not flags.get("context")
        )
        if only_title and sys.stdin.isatty() and not flags["json"]:
            editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
            with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False, encoding="utf-8") as tmp:
                tmp.write(open_editor_template(title))
                tmp_path = tmp.name
            try:
                rc = subprocess.call([editor, tmp_path])
                if rc != 0:
                    print("editor exited non-zero", file=sys.stderr)
                    return 1
                raw_body = pathlib.Path(tmp_path).read_text(encoding="utf-8")
            finally:
                pathlib.Path(tmp_path).unlink(missing_ok=True)
            result, err = create_intake(
                root,
                title=title,
                raw_body=raw_body,
                project_hint=flags.get("project_hint"),
                stream_hint=flags.get("stream_hint"),
            )
        else:
            result, err = create_intake(
                root,
                title=title,
                what=flags.get("what"),
                why=flags.get("why"),
                done_when=flags.get("done_when"),
                not_this=flags.get("not_this") or None,
                context=flags.get("context") or None,
                raw_body=raw_body,
                project_hint=flags.get("project_hint"),
                stream_hint=flags.get("stream_hint"),
            )
        if result is None:
            print(f"✗ intake not written\nReason: {err}", file=sys.stderr)
            return 1
        if flags["json"]:
            print(result.model_dump_json(indent=2))
        else:
            print(f"Created {result.path}")
        return 0

    if sub == "edit":
        if not rest:
            print("Usage: zeo intake edit FILE|latest", file=sys.stderr)
            return 2
        try:
            path = resolve_intake_path(root, rest[0])
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
        return subprocess.call([editor, str(path)])

    if sub == "doctor":
        if not rest:
            print("Usage: zeo intake doctor FILE|latest", file=sys.stderr)
            return 2
        try:
            path = resolve_intake_path(root, rest[0])
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        ready, errors, advice = doctor_intake(path, root=root)
        for e in errors:
            print(f"✗ {e}")
        for a in advice:
            print(f"· {a}")
        if ready:
            print("✓ parseable / WHAT present / status known")
            print("Ready for SOW refinement.")
            return 0
        print("Not ready.")
        return 1

    if sub == "context":
        if not rest:
            print("Usage: zeo intake context FILE [--json]", file=sys.stderr)
            return 2
        try:
            path = resolve_intake_path(root, rest[0])
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        ctx = gather_context(root, path)
        if _want_json(rest):
            print(_json.dumps(ctx, indent=2))
            return 0
        print(f"Intake: {ctx['intake']}")
        print("Terms extracted:")
        for t in ctx.get("terms") or []:
            print(f"  {t}")
        print("Likely code matches:")
        for p in ctx.get("likely_code_matches") or []:
            print(f"  {p}")
        print("Likely tests:")
        for p in ctx.get("likely_tests") or []:
            print(f"  {p}")
        if ctx.get("recent_commits"):
            print("Recent commits touching matches:")
            for c in ctx["recent_commits"]:
                print(f"  {c}")
        return 0

    if sub in ("mission", "investigate"):
        if not rest:
            print(f"Usage: zeo intake {sub} FILE [--json]", file=sys.stderr)
            return 2
        try:
            path = resolve_intake_path(root, rest[0])
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        mission = build_mission(root, path)
        if _want_json(rest):
            print(_json.dumps(mission, indent=2))
            return 0
        print(f"Mission for {mission['intake']}")
        print(f"Goal: {mission['goal']}")
        print(f"repo_head: {mission.get('repo_head')}")
        print("Questions:")
        for q in mission["questions"]:
            print(f"  - {q}")
        print(f"Submit: {mission['submission']['command']}")
        print(f"Then:   {mission['submission']['then']}")
        return 0

    if sub == "propose":
        if not rest:
            print("Usage: zeo intake propose FILE --spec -|path", file=sys.stderr)
            return 2
        file_ref = rest[0]
        spec_src = None
        i = 1
        while i < len(rest):
            if rest[i] == "--spec" and i + 1 < len(rest):
                spec_src = rest[i + 1]
                i += 2
            else:
                i += 1
        if spec_src is None:
            print("zeo intake propose: --spec is required", file=sys.stderr)
            return 2
        try:
            path = resolve_intake_path(root, file_ref)
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        spec, spec_err = _load_spec_json(spec_src)
        if spec_err:
            print(f"zeo intake propose: {spec_err}", file=sys.stderr)
            return 1
        out_path, proposal, err = propose_intake(root, path, spec)
        if err:
            print(f"✗ proposal rejected\nReason: {err}", file=sys.stderr)
            return 1
        print(f"✓ proposal saved {out_path}")
        print(f"  observations: {len(proposal.observations)}")
        return 0

    if sub == "promote":
        if not rest:
            print("Usage: zeo intake promote FILE [--spec ...] [--project P] [--stream S]", file=sys.stderr)
            return 2
        file_ref = rest[0]
        flags = {
            "spec": None,
            "project": None,
            "stream": None,
            "title": None,
            "allow_ungrounded": False,
            "json": False,
        }
        i = 1
        while i < len(rest):
            a = rest[i]
            if a == "--spec" and i + 1 < len(rest):
                flags["spec"] = rest[i + 1]
                i += 2
            elif a == "--project" and i + 1 < len(rest):
                flags["project"] = rest[i + 1]
                i += 2
            elif a == "--stream" and i + 1 < len(rest):
                flags["stream"] = rest[i + 1]
                i += 2
            elif a == "--title" and i + 1 < len(rest):
                flags["title"] = rest[i + 1]
                i += 2
            elif a == "--allow-ungrounded":
                flags["allow_ungrounded"] = True
                i += 1
            elif a == "--json":
                flags["json"] = True
                i += 1
            else:
                if flags["project"] is None:
                    flags["project"] = a
                elif flags["stream"] is None:
                    flags["stream"] = a
                i += 1
        try:
            path = resolve_intake_path(root, file_ref)
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        spec = None
        if flags["spec"] is not None:
            spec, spec_err = _load_spec_json(flags["spec"])
            if spec_err:
                print(f"zeo intake promote: {spec_err}", file=sys.stderr)
                return 1

        if sys.stdin.isatty() and not flags["json"] and spec is None:
            fm, body = load_intake(path)
            sections = parse_intake_sections(body)
            iid = intake_identity(fm, path)
            prop = load_proposal(root, iid)
            print("Intake:")
            print(f"  {sections.get('WHAT') or iid}")
            proj = (
                flags["project"]
                or fm.get("project_hint")
                or fm.get("project")
                or (prop.destination.project if prop and prop.destination else "?")
            )
            strm = (
                flags["stream"]
                or fm.get("stream_hint")
                or (prop.destination.stream if prop and prop.destination else "?")
            )
            print("Suggested project:")
            print(f"  {proj}")
            print("Suggested stream:")
            print(f"  {strm}")
            print("Done when:")
            print(f"  {sections.get('DONE WHEN') or '(from proposal)'}")
            try:
                ans = input("Create SOW? [Y/n] ").strip().lower()
            except EOFError:
                ans = "y"
            if ans not in ("", "y", "yes"):
                print("Aborted.")
                return 1

        result, err = promote_intake(
            root,
            path,
            spec=spec,
            project=flags["project"],
            stream=flags["stream"],
            title=flags["title"],
            allow_ungrounded=flags["allow_ungrounded"],
            cwd=cwd,
        )
        if result is None:
            print(f"✗ promote failed\nReason: {err}", file=sys.stderr)
            return 1
        if flags["json"]:
            print(result.model_dump_json(indent=2))
            return 0
        for c in result.checks:
            print(f"✓ {c}")
        print("")
        print(result.sow_path)
        print("")
        print("✓ intake marked PROMOTED")
        return 0

    print(f"zeo intake: unknown subcommand {sub!r}", file=sys.stderr)
    return 2


def _cmd_doctor(argv: list[str] | None = None, flags: dict | None = None, root: pathlib.Path | None = None) -> int:
    from .sow_authoring import doctor_file, git_changed_markdown

    if flags is not None and root is not None:
        argv_positionals = argv or []
        argv_flags = flags
        argv_root = root
    else:
        argv_positionals, argv_flags = _parse_sow_flags(argv or [])
        if argv_flags.get("_error"):
            return 2
        argv_root = _discover_root(None) or pathlib.Path(".").resolve()
        cwd = pathlib.Path(".").resolve()
        if (cwd / "claude-md" / "CLAUDE.md").is_file():
            argv_root = cwd

    paths: list[pathlib.Path] = []
    if argv_flags.get("changed"):
        paths = git_changed_markdown(argv_root)
        if not paths:
            print("doctor: no changed SOW/ruling markdown")
            return 0
    elif argv_positionals:
        paths = [pathlib.Path(p).resolve() for p in argv_positionals]
    else:
        print("Usage: zeo doctor PATH | zeo doctor --changed", file=sys.stderr)
        return 2

    exit_rc = 0
    for path in paths:
        ready, oks, fails = doctor_file(path, root=argv_root)
        if ready:
            print(f"SOW READY — {path}")
            for line in oks:
                print(f"✓ {line}")
        else:
            exit_rc = 1
            print(f"SOW NOT READY — {path}")
            for line in oks:
                print(f"✓ {line}")
            for line in fails:
                print(f"✗ {line}")
        if len(paths) > 1:
            print()
    return exit_rc


def _cmd_seat(argv: list[str]) -> int:
    """zeo seat -- named-identity switching for a two-(or-more)-account review
    split. `zeo seat init` writes a commented .zeo/seats.toml template; `zeo
    seat use <name>` prints `export ...` lines for `eval "$(zeo seat use
    <name>)"`; `zeo seat` (bare) shows the current shell's seat and every
    configured seat. No real account names live in this tool -- see
    docs/seats.md and seats.SeatsConfigError for the config contract.
    """
    from . import seats as seats_mod

    root = _discover_root(None)

    if not argv:
        current = seats_mod.current_seat_name()
        try:
            configured = seats_mod.load_seats(root)
        except seats_mod.SeatsConfigError as exc:
            print(f"zeo seat: {exc}", file=sys.stderr)
            return 1
        if current:
            print(f"current seat: {current}")
        else:
            print("current seat: (none set -- $ZEO_SEAT is unset)")
        if configured:
            print("configured seats:")
            for name, acct in sorted(configured.items()):
                marker = " *" if name == current else ""
                login = f" ({acct.account_login})" if acct.account_login else ""
                print(f"  {name}{login}{marker}")
        else:
            path = seats_mod.seats_file_path(root)
            if path.is_file():
                # a real file exists but names zero real (uncommented) seats
                # -- e.g. straight after `zeo seat init`, before it's edited.
                # Distinct message from "no file at all" so a user who just
                # ran init isn't told to run it again.
                print(f"{path} exists but names no seats yet -- edit it to add [seats.<name>] entries")
            else:
                print(f"no seats.toml found at {path} (or $ZEO_SEATS_FILE) -- run `zeo seat init`")
        return 0

    sub, rest = argv[0], argv[1:]

    if sub == "init":
        from .intake_authoring import ensure_zeo_gitignore

        force = "--force" in rest
        try:
            path = seats_mod.write_seats_template(root, force=force)
        except FileExistsError as exc:
            print(f"zeo seat init: {exc}", file=sys.stderr)
            return 1
        # This file names real account identifiers -- ensure it's gitignored
        # HERE, unconditionally, rather than relying on `zeo hooks install`/
        # `zeo init` having already run in this corpus. Neither is a
        # precondition of `zeo seat init` itself, and a user who skips
        # straight to seat setup (a real, normal path -- someone adopting
        # just the review-identity feature on an already-initialized corpus)
        # must not be told their real account names are protected when they
        # are not.
        gitignored = ensure_zeo_gitignore(root) if root else False
        print(f"wrote {path}")
        if gitignored:
            print(f"added .zeo/ to {pathlib.Path(root).resolve() / '.gitignore'} -- it names real accounts.")
        elif root:
            print(".zeo/ already gitignored -- it names real accounts, keep it that way.")
        else:
            print(
                "WARNING: no corpus root found (not inside a claude-md/CLAUDE.md tree) -- "
                "could not confirm .zeo/ is gitignored here. It names real accounts; "
                "add '.zeo/' to your own .gitignore by hand before editing it."
            )
        print("edit it to name your own seats (see docs/seats.md).")
        return 0

    if sub == "use":
        if not rest:
            print("Usage: zeo seat use <name>", file=sys.stderr)
            return 2
        name = rest[0]
        try:
            seat = seats_mod.resolve_seat(name, root)
        except seats_mod.SeatsConfigError as exc:
            print(f"zeo seat use: {exc}", file=sys.stderr)
            return 1
        sys.stdout.write(seats_mod.render_seat_use_script(seat))
        return 0

    print(f"zeo seat: unknown subcommand {sub!r}. Usage: zeo seat [init [--force] | use <name>]", file=sys.stderr)
    return 2


def _cmd_artifact(argv: list[str]) -> int:
    """Thin alias: zeo artifact set → zeo sow set (SOW genre)."""
    if not argv:
        print("Usage: zeo artifact set FILE KEY VALUE", file=sys.stderr)
        return 2
    if argv[0] == "set":
        return _cmd_sow(["set", *argv[1:]])
    print(f"zeo artifact: unknown subcommand {argv[0]!r}", file=sys.stderr)
    return 2


def _cmd_execution(argv: list[str]) -> int:
    """zeo execution validate|import PATH — governed JSON receipts, not transcripts."""
    from .execution import import_receipt_json, validate_receipt_path, write_canonical_receipt

    if not argv or argv[0] in ("-h", "--help"):
        print("Usage: zeo execution validate PATH | zeo execution import PATH [--out PATH]", file=sys.stderr)
        return 0 if argv and argv[0] in ("-h", "--help") else 2
    sub = argv[0]
    rest = argv[1:]
    if sub == "validate":
        if not rest:
            print("Usage: zeo execution validate PATH", file=sys.stderr)
            return 2
        path = pathlib.Path(rest[0])
        receipt, errors = validate_receipt_path(path)
        if errors:
            for e in errors:
                print(e, file=sys.stderr)
            return 1
        print(f"valid: {path} execution_id={receipt.execution_id} termination={receipt.termination}")
        return 0
    if sub == "import":
        out = None
        paths = []
        i = 0
        while i < len(rest):
            if rest[i] == "--out" and i + 1 < len(rest):
                out = pathlib.Path(rest[i + 1])
                i += 2
                continue
            paths.append(rest[i])
            i += 1
        if not paths:
            print("Usage: zeo execution import PATH [--out PATH]", file=sys.stderr)
            return 2
        source = pathlib.Path(paths[0])
        try:
            receipt = import_receipt_json(source)
        except ValueError:
            from .adapters.sandcastle import SandcastleEvidenceAdapter

            try:
                receipt = SandcastleEvidenceAdapter().import_receipt(source)
            except Exception as exc:
                print(f"zeo execution import: {exc}", file=sys.stderr)
                return 1
        dest = out or source.with_suffix(".canonical.execution.json")
        if dest.suffix != ".json":
            dest = dest.with_name(dest.name + ".execution.json")
        write_canonical_receipt(receipt, dest)
        print(f"imported: {dest} execution_id={receipt.execution_id}")
        return 0
    print(f"zeo execution: unknown subcommand {sub!r}", file=sys.stderr)
    return 2


def _cmd_dispatch(argv: list[str]) -> int:
    """zeo dispatch acquire|check-remote|cleanup — unattended ownership (library, not a bot)."""
    from . import dispatch as dispatch_mod

    if not argv or argv[0] in ("-h", "--help"):
        print(
            "Usage: zeo dispatch acquire --repo PATH --branch NAME --execution-id ID [--stream NAME]\n"
            "       zeo dispatch check-remote --repo PATH --branch NAME --expect-sha SHA\n"
            "       zeo dispatch cleanup --repo PATH --key KEY [--authorize]",
            file=sys.stderr,
        )
        return 0 if argv and argv[0] in ("-h", "--help") else 2

    def _flag(name: str, default: str | None = None) -> str | None:
        key = f"--{name}"
        if key in argv:
            i = argv.index(key)
            if i + 1 < len(argv):
                return argv[i + 1]
        return default

    sub = argv[0]
    try:
        if sub == "acquire":
            repo = pathlib.Path(_flag("repo") or ".")
            branch = _flag("branch")
            stream = _flag("stream")
            execution_id = _flag("execution-id")
            if not execution_id or not (branch or stream):
                print("zeo dispatch acquire requires --execution-id and --branch or --stream", file=sys.stderr)
                return 2
            repo_name = _git_repo_name(repo)
            key = dispatch_mod.ownership_key(repository=repo_name, branch=branch, stream=stream)
            result = dispatch_mod.acquire(repo, key=key, execution_id=execution_id, branch=branch or f"stream/{stream}")
            if not result.acquired:
                print(f"REFUSED key={key} lock_held_by={result.lock.get('execution_id')} receipt={result.receipt_path}")
                return 1
            print(f"ACQUIRED key={key} execution_id={execution_id} head={result.lock.get('head_sha')}")
            return 0
        if sub == "check-remote":
            repo = pathlib.Path(_flag("repo") or ".")
            branch = _flag("branch")
            expect = _flag("expect-sha")
            if not branch or not expect:
                print("zeo dispatch check-remote requires --branch and --expect-sha", file=sys.stderr)
                return 2
            dispatch_mod.check_remote_advancement(repo, branch, expect)
            print(f"REMOTE-OK {branch} still at {expect}")
            return 0
        if sub == "cleanup":
            repo = pathlib.Path(_flag("repo") or ".")
            key = _flag("key")
            authorize = "--authorize" in argv
            if not key:
                print("zeo dispatch cleanup requires --key", file=sys.stderr)
                return 2
            lock = dispatch_mod.cleanup(repo, key, authorize=authorize)
            print(f"CLEANED key={key} status={lock.get('status')}")
            return 0
    except dispatch_mod.DispatchError as exc:
        print(f"zeo dispatch: {exc}", file=sys.stderr)
        return 1
    print(f"zeo dispatch: unknown subcommand {sub!r}", file=sys.stderr)
    return 2


def _git_repo_name(repo: pathlib.Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        return pathlib.Path(proc.stdout.strip()).name
    return repo.resolve().name


def _print_hooks_install(info: dict) -> None:
    print(f"HOOKS-INSTALL: wrote {len(info['written'])} template(s) under tools/hooks/")
    for w in info["written"]:
        print(f"  {w}")
    if info.get("gitignore_updated"):
        print("  .gitignore: STATE.md + stream-index.md (local views, not committed)")
    else:
        print("  .gitignore: board entries already present")
    if info["git_hook"]:
        print(f"  git pre-commit: {info['git_hook']}")
    else:
        print("  git pre-commit: skipped (no .git dir)")
    warn_tracked_boards(pathlib.Path(info["hooks_dir"]).parent.parent)


def _cmd_hooks(argv: list[str]) -> int:
    if not argv:
        print("zeo hooks: install | pre-commit | session-start | stop | pretooluse-git", file=sys.stderr)
        return 2
    sub = argv[0]
    rest = argv[1:]
    if sub == "install":
        path = rest[0] if rest and not str(rest[0]).startswith("-") else None
        root = _discover_root(path)
        if root is None:
            print("zeo hooks install: run from inside the corpus (or pass a path)", file=sys.stderr)
            return 2
        try:
            info = hooks_install(root)
        except Exception as e:
            print(f"zeo hooks install: {e}", file=sys.stderr)
            return 2
        _print_hooks_install(info)
        return 0
    if sub == "pre-commit":
        path = rest[0] if rest and not str(rest[0]).startswith("-") else None
        root = _discover_root(path) if path else None
        return run_pre_commit(root)
    if sub == "session-start":
        path = rest[0] if rest and not str(rest[0]).startswith("-") else None
        root = _discover_root(path) if path else None
        return run_session_start(root)
    if sub == "stop":
        path = rest[0] if rest and not str(rest[0]).startswith("-") else None
        root = _discover_root(path) if path else None
        return run_stop(root)
    if sub == "pretooluse-git":
        return run_pretooluse_git()
    print(f"zeo hooks: unknown subcommand {sub!r}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    # sys.argv has the program name at [0] (strip it); an explicitly-passed list
    # (tests, direct calls) is ALREADY bare and must NOT be stripped. The old
    # 'args = argv[1:]' stripped BOTH, so main(['--help']) became [] -> usage-error 2
    # (diag). This is the arg-convention bug the new CLI tests exposed.
    args = sys.argv[1:] if argv is None else argv

    # Orientation OS front door: bare `zeo` is the human dashboard, not help.
    if not args:
        return _cmd_orient([])

    if args and args[0] == "help":
        return _cmd_help(args[1:])
    if args and args[0] == "orient":
        return _cmd_orient(args[1:])
    if args and args[0] == "new":
        return _cmd_new(args[1:])
    if args and args[0] == "work":
        return _cmd_work(args[1:])
    if args and args[0] == "next":
        return _cmd_next(args[1:])
    if args and args[0] == "board":
        return _cmd_board_alias(args[1:])
    if args and args[0] == "branches":
        return _cmd_branches(args[1:])
    if args and args[0] == "check-base-fresh":
        return _cmd_check_base_fresh(args[1:])
    if args and args[0] == "triage":
        return _cmd_triage_alias(args[1:])
    if args and args[0] == "digest":
        return _cmd_digest_alias(args[1:])
    if args and args[0] == "index":
        return _cmd_index(args[1:])
    if args and args[0] == "mint":
        return _cmd_mint_alias(args[1:])
    if args and args[0] == "hooks":
        return _cmd_hooks(args[1:])
    if args and args[0] == "init":
        return _cmd_init(args[1:])
    if args and args[0] == "scaffold":
        return _cmd_scaffold(args[1:])
    if args and args[0] == "bridges":
        return _cmd_bridges(args[1:])
    if args and args[0] == "equip":
        return _cmd_equip(args[1:])
    if args and args[0] == "cold-start":
        return _cmd_cold_start(args[1:])
    if args and args[0] == "sow":
        return _cmd_sow(args[1:])
    if args and args[0] == "intake":
        return _cmd_intake(args[1:])
    if args and args[0] == "doctor":
        return _cmd_doctor(args[1:])
    if args and args[0] == "seat":
        return _cmd_seat(args[1:])
    if args and args[0] == "artifact":
        return _cmd_artifact(args[1:])
    if args and args[0] == "execution":
        return _cmd_execution(args[1:])
    if args and args[0] == "dispatch":
        return _cmd_dispatch(args[1:])
    backfill_project = None
    locate_stream_name = None
    want_progress = None
    want_sollist = None
    want_restauf = None
    want_kosten = None
    want_repo_cost = None  # False-ish None; "" = cwd; str = path
    want_session_cost = False
    transcript_path = None
    cost_log_path = None
    append_cost_log_path = None
    count_via = "local"
    api_key_env = "ANTHROPIC_API_KEY"
    want_calibrate = False
    want_json = False
    repair_project = None
    apply_flag = False
    limit_n = None
    resync_upstream = None
    resync_apply_upstream = None
    promote_dir = None
    if any(a in ("--help", "-h") for a in args):
        return _cmd_help([])
    claude_md_override = None
    skill_path = None
    board = False
    board_repair = False
    triage = False
    priority = False
    priority_top_n = 3
    priority_near_m = 3
    commit_check_corpus = False
    ruling_index = False
    mint_requested = False
    mint_kind = None
    mint_stream = None
    mint_words = None
    stream_index = False
    want_digest = False
    digest_since = None
    inbox_stream = None
    migrate_check_path = None
    want_incarnation = False
    migrate_path = None
    commit_check = False
    quiet = False
    model_tag = None
    positional = []
    i = 0
    while i < len(args):
        if args[i] == "--claude-md" and i + 1 < len(args):
            claude_md_override = args[i + 1]
            i += 2
        elif args[i] == "--skill" and i + 1 < len(args):
            skill_path = args[i + 1]
            i += 2
        elif args[i] == "--board":
            board = True
            i += 1
        elif args[i] == "--repair":
            board_repair = True
            i += 1
        elif args[i] == "--commit-check-corpus":
            commit_check_corpus = True
            i += 1
        elif args[i] == "--ruling-index":
            ruling_index = True
            i += 1
        elif args[i] == "--digest":
            # `[since]` is OPTIONAL and, when given, is a duration like "4h"/"1d" - never
            # a path (a path is the ROOT positional, same convention as --restaufwand
            # etc.). A bare "--digest" (no since) uses the author-boundary walk.
            nxt = args[i + 1] if i + 1 < len(args) else ""
            if not nxt or nxt.startswith("--") or pathlib.Path(nxt).exists():
                want_digest = True
                digest_since = None
                i += 1
            else:
                want_digest = True
                digest_since = nxt
                i += 2
        elif args[i] == "--mint":
            # BUG (diag/mint-bare, RULING-326): the old `and i + 1 < len(args)` guard
            # meant a bare trailing `--mint` (no kind after it) never matched this
            # branch at all - the loop fell through to the lint-mode fallback below,
            # which then reported "path does not exist: --mint", actively implying
            # the flag itself was unrecognized rather than that it needed an argument.
            # `--mint` is ALWAYS consumed here now, tracked by the separate
            # `mint_requested` flag (mint_kind alone can't carry "requested but no
            # kind given" - both None and "" are falsy and `if mint_kind:` below would
            # skip dispatch either way, repeating the same fall-through bug with a
            # different symptom). A missing kind now reaches `_mint`'s own actionable
            # "unknown kind" message instead of the generic lint-mode path error.
            mint_requested = True
            if i + 1 < len(args):
                mint_kind = args[i + 1]
                j = i + 2
                if mint_kind == "sow" and j < len(args) and not args[j].startswith("--"):
                    mint_stream = args[j]
                    j += 1
                i = j
            else:
                i += 1
        elif args[i] == "--words" and i + 1 < len(args):
            mint_words = args[i + 1]
            i += 2
        elif args[i] == "--triage":
            triage = True
            i += 1
        elif args[i] == "--priority":
            priority = True
            i += 1
        elif args[i] == "--top" and i + 1 < len(args):
            priority_top_n = int(args[i + 1])
            i += 2
        elif args[i] == "--near-miss" and i + 1 < len(args):
            priority_near_m = int(args[i + 1])
            i += 2
        elif args[i] == "--stream-index":
            stream_index = True
            i += 1
        elif args[i] == "--inbox" and i + 1 < len(args):
            inbox_stream = args[i + 1]
            i += 2
        elif args[i] == "--apply":
            apply_flag = True
            i += 1
        elif args[i] == "--limit" and i + 1 < len(args):
            limit_n = int(args[i + 1])
            i += 2
        elif args[i] == "--restaufwand":
            nxt = args[i + 1] if i + 1 < len(args) else ""
            if not nxt or nxt.startswith("--") or pathlib.Path(nxt).exists():
                want_restauf = ""
                i += 1
            else:
                want_restauf = nxt
                i += 2
        elif args[i] == "--kosten":
            nxt = args[i + 1] if i + 1 < len(args) else ""
            if not nxt or nxt.startswith("--") or pathlib.Path(nxt).exists():
                want_kosten = ""
                i += 1
            else:
                want_kosten = nxt
                i += 2
        elif args[i] == "--repo-cost":
            nxt = args[i + 1] if i + 1 < len(args) else ""
            if not nxt or nxt.startswith("--"):
                want_repo_cost = ""
                i += 1
            else:
                want_repo_cost = nxt
                i += 2
        elif args[i] == "--session-cost":
            want_session_cost = True
            i += 1
        elif args[i] == "--transcript" and i + 1 < len(args):
            transcript_path = args[i + 1]
            i += 2
        elif args[i] == "--cost-log" and i + 1 < len(args):
            cost_log_path = args[i + 1]
            i += 2
        elif args[i] == "--append-cost-log" and i + 1 < len(args):
            append_cost_log_path = args[i + 1]
            i += 2
        elif args[i] == "--count-via" and i + 1 < len(args):
            count_via = args[i + 1]
            i += 2
        elif args[i] == "--api-key-env" and i + 1 < len(args):
            api_key_env = args[i + 1]
            i += 2
        elif args[i] == "--calibrate":
            want_calibrate = True
            i += 1
        elif args[i] == "--json":
            want_json = True
            i += 1
        elif args[i] in ("--soll-ist", "--drift"):
            nxt = args[i + 1] if i + 1 < len(args) else ""
            if not nxt or nxt.startswith("--") or pathlib.Path(nxt).exists():
                want_sollist = ""
                i += 1
            else:
                want_sollist = nxt
                i += 2
        elif args[i] == "--progress":
            # PAID (GM-example-stream-211): `--progress .` took "." as a STREAM NAME, filtered for a
            # stream called "." and printed `0 stream(s)` against a full corpus - a silent zero
            # reading as health, the exact failure this verb exists to catch. An argument that
            # EXISTS ON DISK is a PATH, never a stream name.
            nxt = args[i + 1] if i + 1 < len(args) else ""
            if not nxt or nxt.startswith("--") or pathlib.Path(nxt).exists():
                want_progress = ""
                i += 1
            else:
                want_progress = nxt
                i += 2
        elif args[i] == "--locate" and i + 1 < len(args):
            locate_stream_name = args[i + 1]
            i += 2
        elif args[i] == "--repair-project":
            repair_project = args[i + 1] if i + 1 < len(args) else "."
            i += 2 if i + 1 < len(args) else 1
        elif args[i] == "--backfill-project":
            backfill_project = args[i + 1] if i + 1 < len(args) else "."
            i += 2 if i + 1 < len(args) else 1
        elif args[i] == "--resync-check" and i + 1 < len(args):
            resync_upstream = args[i + 1]
            i += 2
        elif args[i] == "--resync-apply" and i + 1 < len(args):
            resync_apply_upstream = args[i + 1]
            i += 2
        elif args[i] == "--hooks-install":
            path = args[i + 1] if i + 1 < len(args) and not args[i + 1].startswith("-") else None
            if path:
                i += 2
            else:
                i += 1
            root = _discover_root(path)
            if root is None:
                print("zeo --hooks-install: run from inside the corpus", file=sys.stderr)
                return 2
            try:
                info = hooks_install(root)
            except Exception as e:
                print(f"zeo --hooks-install: {e}", file=sys.stderr)
                return 2
            _print_hooks_install(info)
            return 0
        elif args[i] == "--promote" and i + 1 < len(args):
            promote_dir = args[i + 1]
            i += 2
        elif args[i] == "--incarnation":
            want_incarnation = True
            i += 1
        elif args[i] == "--migrate-check" and i + 1 < len(args):
            migrate_check_path = []
            j = i + 1
            while j < len(args) and not args[j].startswith("--"):
                migrate_check_path.append(args[j])
                j += 1
            i = j
        elif args[i] == "--migrate" and i + 1 < len(args):
            migrate_path = args[i + 1]
            i += 2
        elif args[i] == "--model" and i + 1 < len(args):
            model_tag = args[i + 1]
            i += 2
        elif args[i] == "--commit-check":
            commit_check = True
            i += 1
        elif args[i] == "--quiet":
            # doctrine item 2: printing the genre-unknown/preschema-block WARN
            # for every SKIPped file can be loud on a corpus-wide run — the counts in
            # the summary line stand either way; --quiet drops only the per-file blocks.
            quiet = True
            i += 1
        else:
            positional.append(args[i])
            i += 1
    # --board and --inbox auto-discover the sows repo; a path is OPTIONAL for them.
    # --migrate-check takes a FILE and needs no repo root — dispatch before the
    # board/inbox root-discovery guard (which else-branches to a positional check
    # and prints usage, the diag fall-through that made the flag unreachable).
    # --resync-check and --promote take PATHS and need no repo-root discovery; dispatch
    # before the board/inbox guard (the diag fall-through that made a flag unreachable).
    #
    # doctrine: this block (restaufwand/kosten/soll-ist/progress/locate) used to
    # fall back to the LITERAL STRING "." when no positional was given — not None, unlike
    # --board/--inbox below (line ~706). _discover_root("."), given a truthy explicit arg,
    # returns Path(".") UNCONDITIONALLY without walking up to find claude-md/CLAUDE.md, so
    # these five verbs FAILED OPEN from a wrong cwd ("0 streams") no matter what a caller
    # passed - removing a hook's OWN "." argument (cc-session-start.sh) fixed NOTHING here,
    # because the fallback was baked into this file, not the caller. MEASURED before this
    # fix: `cd /tmp && zeo --restaufwand` (zero args) already printed "0 of 0" instead
    # of refusing, identically to `--restaufwand .` - proven wrong by the ONE verb that WAS
    # already correct (`--triage`, zero args, correctly printed "couldn't find the sows
    # repo"). Now `else None`, matching that correct sibling exactly.
    if want_restauf is not None:
        r = _discover_root(positional[0] if positional else None)
        if r is None:
            print("zeo --restaufwand: run from inside the corpus", file=sys.stderr)
            return 2
        rows = restaufwand(r, want_restauf or None)
        order = {
            "RISING": 0,
            "FLAT": 1,
            "SINGLE-POINT": 2,
            "FALLING": 3,
            "UNDECLARED": 4,
        }
        rows.sort(key=lambda x: (order.get(x["verdict"], 9), x["stream"]))
        und = [x for x in rows if x["verdict"] == "UNDECLARED"]
        dw = [x for x in rows if x["needs_done_when"]]
        print("  RESTAUFWAND - what is LEFT, and whether it is falling (doctrine)")
        print("  {:<24}{:>10}{:>8}  {}".format("stream", "remaining", "delta", "verdict"))
        for x in rows:
            rem = "-" if x["remaining"] is None else str(x["remaining"])
            dl = "" if x["delta"] is None else ("%+d" % x["delta"])
            print("  {:<24}{:>10}{:>8}  {}".format(x["stream"], rem, dl, x["verdict"]))
            if x["done_when"]:
                print("      done_when: {}".format(str(x["done_when"])[:78]))
            elif x["needs_done_when"]:
                print("      NO done_when on a {} status - this stream cannot state when it stops".format(x["status"]))
        print("  {} of {} declare NO restaufwand - DISTANCE IS UNMEASURABLE for those".format(len(und), len(rows)))
        print("  {} WORKING stream(s) carry no done_when (doctrine requires one)".format(len(dw)))
        return 0

    if want_kosten is not None:
        r = _discover_root(positional[0] if positional else None)
        if r is None:
            print("zeo --kosten: run from inside the corpus", file=sys.stderr)
            return 2
        if count_via not in ("local", "anthropic"):
            print(f"zeo --count-via: expected local|anthropic, got {count_via!r}", file=sys.stderr)
            return 2
        try:
            rates = get_model_rates(model_tag)
        except UnknownModelError as e:
            print(f"zeo --kosten: {e}", file=sys.stderr)
            return 2
        samples = fixed_tax_sample_texts(r) if (want_calibrate or count_via == "anthropic") else None
        # Full-tree Anthropic is out of v1: --count-via anthropic on --kosten means calibrate.
        use_calibrate = want_calibrate or count_via == "anthropic"
        try:
            estimate, tok_label, ratio = make_estimator(
                "local",
                model=rates["model"],
                calibrate=use_calibrate,
                calibrate_samples=samples,
                api_key_env=api_key_env,
            )
        except Exception as e:
            print(f"zeo --kosten: estimator failed: {e}", file=sys.stderr)
            return 2
        K = kosten(r, want_kosten or None, estimate=estimate)
        W = waste_report(r, want_kosten or None, estimate=estimate)
        artifact = K["fixed_total"] + K["corpus_total"] + K["ruling_tokens"]
        usd = usd_for_input_tokens(artifact, rates)
        payload = {
            "kind": "kosten",
            "tokenizer": tok_label,
            "calibrate_ratio": ratio,
            "model": rates["model"],
            "as_of": rates["as_of"],
            "source": rates["source"],
            "fixed": K["fixed"],
            "fixed_total": K["fixed_total"],
            "corpus_total": K["corpus_total"],
            "ruling_tokens": K["ruling_tokens"],
            "artifact_tokens": artifact,
            "usd": usd,
            "waste": W,
            "honesty": "ESTIMATE tokens x DERIVED USD (input rate); session tokens not included",
        }
        if want_json:
            import json as _json

            print(_json.dumps(payload, indent=2, default=str))
            return 0
        print(f"  KOSTENRECHNUNG (ESTIMATE — {tok_label})")
        print(
            f"  rates: model={rates['model']} as_of={rates['as_of']}  {format_usd(usd)} DERIVED for ~{artifact} artifact tokens (input-only)"
        )
        print("  --- TAX: paid by EVERY session of EVERY stream. MINIMISE HARD (s12) ---")
        for name, tok in sorted(K["fixed"].items(), key=lambda x: -x[1])[:6]:
            print("    {:<44} ~{:>6}".format(name, tok))
        print("    {:<44} ~{:>6}".format("TOTAL", K["fixed_total"]))
        print("  --- ARTIFACT ---")
        print("    SOWs ~{}   rulings ~{}".format(K["corpus_total"], K["ruling_tokens"]))
        wt = sum(x["tokens"] for x in W)
        print(
            "  --- WASTE: {} rev(s), ~{} tok ({:.1f}% of SOW tokens). MINIMISE ---".format(
                len(W), wt, 100.0 * wt / max(K["corpus_total"], 1)
            )
        )
        for x in sorted(W, key=lambda x: -x["tokens"])[:5]:
            print("    {:<20} n{:<4} ~{:>6}  {}".format(x["stream"], x["n"], x["tokens"], ",".join(x["kinds"])))
        print("  INVESTMENT - recon, checks, reading the source - is NOT minimised (doctrine).")
        print("  NO TOKEN TARGET IS EVER SET ON A STREAM. A SELF-CORRECTION IS NEVER WASTE.")
        print("  SESSION tokens: use zeo --session-cost (transcript / session-costs.jsonl).")
        return 0

    if want_repo_cost is not None:
        root = pathlib.Path(want_repo_cost).resolve() if want_repo_cost else pathlib.Path.cwd().resolve()
        if not root.exists():
            print(f"zeo --repo-cost: path not found: {root}", file=sys.stderr)
            return 2
        if count_via not in ("local", "anthropic"):
            print(f"zeo --count-via: expected local|anthropic, got {count_via!r}", file=sys.stderr)
            return 2
        try:
            rates = get_model_rates(model_tag)
        except UnknownModelError as e:
            print(f"zeo --repo-cost: {e}", file=sys.stderr)
            return 2
        calibrate = want_calibrate or count_via == "anthropic"
        samples = None
        if calibrate:
            # Prefer corpus fixed-tax samples if this path is (or contains) a corpus;
            # else take the first few text files as calibration samples.
            corp = _discover_root(str(root))
            if corp is not None:
                samples = fixed_tax_sample_texts(corp)
            if not samples:
                from .cost import iter_repo_text_files

                files = iter_repo_text_files(root)[:5]
                samples = []
                for f in files:
                    try:
                        samples.append(f.read_text(encoding="utf-8", errors="replace")[:8000])
                    except OSError:
                        pass
        try:
            estimate, tok_label, ratio = make_estimator(
                "local",
                model=rates["model"],
                calibrate=calibrate,
                calibrate_samples=samples,
                api_key_env=api_key_env,
            )
        except Exception as e:
            print(f"zeo --repo-cost: estimator failed: {e}", file=sys.stderr)
            return 2
        report = repo_token_report(root, estimate=estimate, model=rates["model"])
        report["tokenizer"] = tok_label
        report["calibrate_ratio"] = ratio
        if want_json:
            import json as _json

            print(_json.dumps(report, indent=2, default=str))
            return 0
        print(f"  REPO-COST (ESTIMATE — {tok_label})")
        print(f"  root: {report['root']}")
        print(
            "  files={}  tokens~{}  DERIVED {}  model={} as_of={}".format(
                report["files"],
                report["tokens"],
                format_usd(report["usd"]),
                report["model"],
                report["as_of"],
            )
        )
        print(f"  ({report['honesty']})")
        if report["top"]:
            print("  --- heaviest paths ---")
            for row in report["top"][:10]:
                print("    ~{:>8}  {}".format(row["tokens"], row["path"]))
        return 0

    if want_session_cost:
        tpath = transcript_path
        clog = cost_log_path
        if tpath is None and clog is None:
            r = _discover_root(positional[0] if positional else None)
            if r is not None:
                default_log = pathlib.Path(r) / "tools" / "stream-instruments" / "session-costs.jsonl"
                if default_log.is_file():
                    clog = str(default_log)
            if tpath is None and clog is None:
                print(
                    "zeo --session-cost: pass --transcript PATH or --cost-log PATH "
                    "(or run inside a corpus with tools/stream-instruments/session-costs.jsonl)",
                    file=sys.stderr,
                )
                return 2
        try:
            if model_tag is not None:
                get_model_rates(model_tag)  # fail closed early
            report = session_cost_report(transcript=tpath, cost_log=clog, model=model_tag)
        except UnknownModelError as e:
            print(f"zeo --session-cost: {e}", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"zeo --session-cost: {e}", file=sys.stderr)
            return 2
        if append_cost_log_path:
            try:
                append_session_cost_log(append_cost_log_path, report)
            except Exception as e:
                print(f"zeo --session-cost: append-cost-log failed: {e}", file=sys.stderr)
                return 2
        if want_json:
            import json as _json

            print(_json.dumps(report, indent=2, default=str))
            return 0
        print("  SESSION-COST (usage from {} × DERIVED USD)".format(report["usage_source"]))
        print(f"  path: {report['path']}")
        print(
            "  in={} out={} cache_r={} cache_w={}  events={}".format(
                report["input_tokens"],
                report["output_tokens"],
                report["cache_read_tokens"],
                report["cache_write_tokens"],
                report["events"],
            )
        )
        print(
            "  DERIVED {}  model={} as_of={}".format(
                format_usd(report["usd"]),
                report["model"],
                report["as_of"],
            )
        )
        if report.get("logged_usd"):
            print(f"  (cost-log also carried logged_usd sum={format_usd(float(report['logged_usd']))})")
        print(f"  ({report['honesty']})")
        return 0

    if want_sollist is not None:
        r = _discover_root(positional[0] if positional else None)
        if r is None:
            print("cadence --soll-ist: run from inside the corpus", file=sys.stderr)
            return 2
        rows = soll_ist(r, want_sollist or None)
        if not rows:
            print("  no rev PAIR carries next_three_acts - SOLL is undeclared, so no")
            print("  variance is computable. That absence IS the finding.")
            return 0
        var = [x for x in rows if x["verdict"] != "AS-PLANNED"]
        unstated = [x for x in var if x["unstated"]]
        print(
            "  SOLL/IST-VERGLEICH: {} comparison(s), {} variance(s), {} UNSTATED".format(
                len(rows), len(var), len(unstated)
            )
        )
        for x in rows:
            tag = x["abweichung"] or ("UNSTATED" if x["unstated"] else "-")
            print(
                "  {}/{}  n{}->n{}  {}/{} planned acts done  {}  [{}]".format(
                    x["project"],
                    x["stream"],
                    x["from_n"],
                    x["to_n"],
                    x["done"],
                    x["of"],
                    x["verdict"],
                    tag,
                )
            )
            for act, hit in zip(x["soll"], x["matched"]):
                print("      {} {}".format("DONE " if hit else "NOT  ", act[:88]))
        if unstated:
            print("  An UNSTATED variance is invisible drift. Name an abweichung: from")
            print("  SCOPE-CHANGED | ESTIMATE-WRONG | BLOCKED-EXTERNAL | DISCOVERED-WORK")
        return 0

    if want_progress is not None:
        r = _discover_root(positional[0] if positional else None)
        if r is None:
            print("zeo --progress: run from inside the corpus", file=sys.stderr)
            return 2
        rows = stream_progress(r, want_progress or None)
        rows.sort(key=lambda x: (x["resting"], -x["idle"]))
        live = [x for x in rows if not x["resting"]]
        stale = [x for x in live if x["idle"] > 7]
        nodw = [x for x in rows if not x["done_when"]]
        print("  {} stream(s), {} not at rest, {} of those IDLE >7d".format(len(rows), len(live), len(stale)))
        print("  {:<24}{:>6}{:>5}{:>9}{:>7}  {}".format("stream", "files", "n", "rate/d", "idle", "status"))
        for x in rows:
            flag = "  <-- IDLE, not resting" if (not x["resting"] and x["idle"] > 7) else ""
            print(
                "  {:<24}{:>6}{:>5}{:>9}{:>7}  {}{}".format(
                    x["stream"],
                    x["files"],
                    x["n"],
                    x["rate"],
                    x["idle"],
                    x["status"],
                    flag,
                )
            )
            if x["done_when"]:
                print("      done_when: {}".format(x["done_when"]))
        print(
            "  {} of {} declare NO done_when - distance to done is UNMEASURABLE for those".format(len(nodw), len(rows))
        )
        return 0

    if locate_stream_name:
        r = _discover_root(positional[0] if positional else None)
        if r is None:
            print(
                "zeo --locate: run from inside the corpus, or pass its path",
                file=sys.stderr,
            )
            return 2
        # doctrine: locate_stream is zero-git pathlib (correct - see its own
        # docstring), but "disk" is a CHECKOUT and a booting seat's question about
        # "what's my next n:" is usually a question about the TRUNK. Name which one
        # this answer came from, before the answer itself, every invocation.
        print(f"  {format_ref_disclosure(git_ref_state(r))}")
        L = locate_stream(r, locate_stream_name)
        if L["ambiguous"]:
            print(
                f"  AMBIGUOUS: {len(L['candidates'])} dirs named "
                f"{locate_stream_name!r} - a human rules this, not the tool:"
            )
            for c in L["candidates"]:
                print(f"    {c}")
            return 1
        if not L["chain_dir"]:
            print(
                f"  NO CHAIN DIR named {locate_stream_name!r} under any "
                f"<project>/sow/. A new stream files its first SOW to create one."
            )
            return 1
        print(f"  stream      {L['stream']}")
        print(f"  project     {L['project']}")
        print(f"  chain dir   {L['chain_dir']}")
        print(f"  files       {L['files']}")
        if L["latest"]:
            x = L["latest"]
            print(f"  latest      {x['file']}")
            print(
                f"              n:{x['n']} rev:{x['rev']} "
                f"status:{x['status']}" + (f" seat:{x['seat']}" if x["seat"] else "")
            )
            print(f"  YOUR NEXT   n: {L['next_n']}   supersedes: {x['n']}")
        else:
            print("  latest      none carry an integer n: - walk the chain by hand")
        print(f"  sow: field  {', '.join(L['declared_sow']) or '(none declared)'}")
        print(f"  diary       {L['diary'] or '(absent - create on first paid lesson)'}")
        print("  NOTE: derived from disk. A spawn message that disagrees with this is WRONG.")
        return 0

    if repair_project:
        r = corpus_root(repair_project) or pathlib.Path(repair_project)
        P = project_repair_plan(r)
        print(f"  known projects: {', '.join(P['known_projects'])}")
        print(f"  REPAIRABLE ({len(P['repair'])}) - declared value is not a project:")
        for x in P["repair"]:
            print(f"    {x['file']}")
            print(f"      project: {x['declared']} -> {x['derived']}  ({x['why']})")
        print(f"  ESCALATE ({len(P['escalate'])}) - NOT rewritten:")
        for x in P["escalate"]:
            print(f"    {x['file']}")
            print(f"      declared:{x['declared']} derived:{x['derived']} - {x['why']}")
        print(f"  MISSING ({len(P['missing'])}) - with reasons:")
        for x in P["missing"][:12]:
            print(f"    {x['file']}  ({x['why']})")
        if apply_flag and P["repair"]:
            done = 0
            for x in P["repair"]:
                f = pathlib.Path(r) / x["file"]
                txt = f.read_text(encoding="utf-8", errors="replace")
                L = txt.splitlines(keepends=True)
                idx = [j for j, l in enumerate(L) if l.startswith("project:")]
                if len(idx) != 1:
                    print(f"    REFUSED {x['file']}: {len(idx)} project: lines")
                    continue
                L[idx[0]] = f"project: {x['derived']}\n"
                cand = "".join(L)
                fm2 = extract_frontmatter(cand)
                if not (isinstance(fm2, dict) and fm2.get("project") == x["derived"]):
                    print(f"    REFUSED {x['file']}: parse-verify failed")
                    continue
                if cand.split("---", 2)[-1] != txt.split("---", 2)[-1]:
                    print(f"    REFUSED {x['file']}: BODY CHANGED")
                    continue
                f.write_text(cand, encoding="utf-8")
                done += 1
            print(f"APPLIED: {done} repaired. ESCALATE untouched. NOT COMMITTED.")
            return 0
        print("REPAIR-PLAN: DRY-RUN ONLY - nothing written. Add --apply for the REPAIRABLE class only.")
        return 0

    if backfill_project:
        r = corpus_root(backfill_project) or pathlib.Path(backfill_project)
        print(f"  corpus root: {r}")
        plan = project_backfill_plan(r)
        by = {}
        for row in plan["rows"]:
            by.setdefault(row["project"], []).append(row)
        for proj in sorted(by):
            print(f"  {proj}: {len(by[proj])} file(s) would gain project: {proj}")
            for row in by[proj][:5]:
                print(f"    {row['file']}")
            if len(by[proj]) > 5:
                print(f"    ... and {len(by[proj]) - 5} more")
        if plan["unresolved"]:
            print(f"  UNRESOLVED ({len(plan['unresolved'])}) - path yields no project, NOT guessed:")
            for u in plan["unresolved"][:5]:
                print(f"    {u['file']}")
        if apply_flag:
            res = project_backfill_apply(r, plan["rows"], limit=limit_n)
            for fl in res["failed"]:
                print(f"    FAILED {fl['file']}: {fl['why']}")
            print(
                f"APPLIED: {len(res['written'])} written, {len(res['skipped'])} "
                f"already had it, {len(res['failed'])} refused. "
                f"NOT COMMITTED - read `git diff` before committing."
            )
            return 1 if res["failed"] else 0
        print(
            f"BACKFILL-PLAN: {len(plan['rows'])} file(s) repairable, "
            f"{len(plan['unresolved'])} unresolved. DRY-RUN ONLY - nothing written."
        )
        return 0

    if resync_apply_upstream:
        tgt = positional[0] if positional else "."
        try:
            results = resync_apply(tgt, resync_apply_upstream)
        except Exception as e:
            print(f"zeo --resync-apply: {e}", file=sys.stderr)
            return 2
        written = [r for r in results if r["action"] == "WRITTEN"]
        skipped = [r for r in results if r["action"] == "SKIP"]
        missing = [r for r in results if r["action"] == "MISSING-UPSTREAM"]
        for r in results:
            sha = (r.get("sha") or "")[:8]
            extra = f" sha={sha}" if sha else ""
            why = f"  ({r['why']})" if r.get("why") else ""
            print(f"  {r['path']:<44} {r['action']}{extra}{why}")
        print(
            f"RESYNC-APPLY: {len(written)} written, {len(skipped)} skipped (local), "
            f"{len(missing)} missing-upstream. NOT COMMITTED."
        )
        if skipped:
            print("  REPORTED, not re-derived: " + ", ".join(r["path"] for r in skipped))
        return 0

    if resync_upstream:
        tgt = positional[0] if positional else "."
        rows = resync_check(tgt, resync_upstream)
        stale = [r for r in rows if r[1] in ("STALE", "MISSING-TARGET")]
        for relp, verdict, rec, cur in rows:
            extra = ""
            if verdict == "STALE" and rec and cur:
                extra = f"  recorded={rec[:8]} upstream={cur[:8]}"
            elif verdict == "MISSING-TARGET" and cur:
                extra = f"  upstream={cur[:8]}"
            elif verdict == "MISSING-UPSTREAM" and rec:
                extra = f"  recorded={rec[:8]}"
            print(f"  {relp:<44} {verdict}{extra}")
        print(f"RESYNC-CHECK: {len(rows)} doctrine files, {len(stale)} STALE")
        # example-stream-CHARTER-03 item 6: a directory upstream not covered by this walk is named,
        # not silently absent - so a clean run cannot be mistaken for "everything upstream
        # is covered." Advisory only: NOT graded, NOT counted toward the exit code, because
        # a genuine content genre (projects/, ruling/, learnings/) belongs here too and
        # that is correct, not a defect (see unwatched_genres' own docstring).
        unwatched = unwatched_genres(resync_upstream)
        if unwatched:
            print(
                f"UNWATCHED (upstream has .md content here; this check does not walk it - "
                f"human judgement, not auto-graded): {', '.join(unwatched)}"
            )
        return 1 if stale else 0

    if promote_dir:
        root = _discover_root(positional[0] if positional else promote_dir)
        if root is None:
            print("zeo --promote: couldn't find the repo root", file=sys.stderr)
            return 2
        root = corpus_root(promote_dir) or root
        plan = promote_plan(root, promote_dir)
        for row in plan["rows"]:
            print(f"  n={row['n']:<4} {pathlib.Path(row['src']).name}")
            print(f"         -> {row['target']}   predecessor={row['predecessor']}")
        if plan.get("excluded"):
            print(f"  EXCLUDED ({len(plan['excluded'])}) - not SOWs, so not renamed:")
            for e in plan["excluded"]:
                print(f"    {e['file']}  ({e['why']})")
        if plan.get("assigned"):
            print(
                f"  n ASSIGNED to {len(plan['assigned'])} file(s) with no declared n; "
                f"{len(plan.get('preserved', []))} kept their existing n"
            )
        if plan["untracked"]:
            print(f"  UNTRACKED ({len(plan['untracked'])}) - git has no birth for these:")
            for u in plan["untracked"]:
                print(f"    {u}")
        renames = [r for r in plan["rows"] if r.get("rename")]
        keeps = [r for r in plan["rows"] if not r.get("rename")]
        print(
            f"  KEEPING their names ({len(keeps)}): already grade - "
            f"a rename would touch landed records for cosmetic conformance"
        )
        rmap = {pathlib.Path(r["src"]).name: r["target"] for r in renames}
        scan_root = corpus_root(promote_dir) or root
        chits = citation_scan(scan_root, rmap)
        nfiles, nrefs = citation_totals(chits)
        print(f"  citation scan root: {scan_root}")
        print(f"  CITATION IMPACT: {nrefs} reference(s) in {nfiles} file(s) would need rewriting")
        for cf, entries in list(chits.items())[:10]:
            tot = sum(e["with_ext"] + e["stem_only"] for e in entries)
            print(f"    {cf}  ({tot})")
        if len(chits) > 10:
            print(f"    ... and {len(chits) - 10} more file(s)")
        if plan["collisions"]:
            print(f"REFUSED: {len(plan['collisions'])} collision(s) - --promote never resolves one,")
            print("         because a naive rename would OVERWRITE LANDED HISTORY (doctrine):")
            for tgt, srcs in plan["collisions"].items():
                print(f"    {tgt}  <-  {', '.join(srcs)}")
            return 1
        if apply_flag:
            res = promote_apply(root, plan["rows"], limit=limit_n)
            for d in res["renamed"]:
                print(f"    RENAMED n={d['n']}  {d['from'].split(chr(47))[-1]} -> {d['to']}")
            for fl in res["failed"]:
                print(f"    FAILED {fl['file']}: {fl['why']}")
            print(
                f"APPLIED: {len(res['renamed'])} renamed, {len(res['skipped'])} kept, "
                f"{len(res['failed'])} refused. Citations NOT rewritten - legacy_name is "
                f"the bridge (doctrine). NOT COMMITTED."
            )
            return 1 if res["failed"] else 0
        print(f"PROMOTE-PLAN: {len(plan['rows'])} file(s), 0 collisions. DRY-RUN ONLY - nothing was written.")
        return 0

    if want_incarnation:
        # doctrine: the session marker a SOW records in its FIRST filing.
        # PAID (example-stream doctrine): the skill has instructed every stream
        # to run this since the stand-down ruling and the verb did not exist -
        # the seat correctly OMITTED the field rather than invent a value.
        import secrets

        print(secrets.token_hex(4))
        return 0

    if migrate_check_path:
        return migrate_check_render(migrate_check_path)
    # --migrate takes a FILE like --migrate-check; dispatch before the root guard
    # (the diag fall-through that made a flag unreachable).
    if migrate_path:
        from .migrate import migrate_render

        return migrate_render(migrate_path, model_tag)
    if (
        board
        or inbox_stream
        or triage
        or priority
        or commit_check_corpus
        or ruling_index
        or mint_requested
        or stream_index
        or want_digest
    ):
        root = _discover_root(positional[0] if positional else None)
        if root is None:
            print(
                "zeo: couldn't find a corpus. Run from inside one, pass its path, or set ZEO_SOWS_ROOT.\n"
                "  marker: claude-md/CLAUDE.md at the corpus root.\n"
                "  example: zeo --board /path/to/corpus\n"
                "  example: ZEO_SOWS_ROOT=/path/to/corpus zeo --board",
                file=sys.stderr,
            )
            return 2
    else:
        # lint mode still needs an explicit target (a file or dir to lint)
        if len(positional) != 1:
            print(
                "zeo: pass a file/dir to lint, or run `zeo` for orientation / `zeo help` for commands.",
                file=sys.stderr,
            )
            return 2
        target = pathlib.Path(positional[0])
        if not target.exists():
            print(f"zeo: path does not exist: {target}", file=sys.stderr)
            return 2
        # THE BUG (diag/346): a single-FILE target set root=the file, so
        # project_of(path, root) returned None and every project_of-gated ERROR
        # (check_status, check_n canonical path) silently DOWNGRADED to WARN — bad SOWs
        # graded "passed". _discover_root returns its arg verbatim (never walks up), so it
        # could not fix this. find_canonical_claude_md DOES walk up to claude-md/CLAUDE.md;
        # the repo root is that marker's grandparent. TARGET = what to lint; ROOT = repo.
        _canon = find_canonical_claude_md(target)
        root = _canon.parent.parent if _canon is not None else (target if target.is_dir() else target.parent)

    if triage:
        return _triage(root)
    if priority:
        return _priority(root, top_n=priority_top_n, near_m=priority_near_m, json_out=want_json)
    if board:
        return _board(root, repair=board_repair)
    if commit_check_corpus:
        return _commit_check_corpus(root)
    if ruling_index:
        return _ruling_index(root)
    if mint_requested:
        return _mint(root, mint_kind or "<none>", mint_stream, words=mint_words)
    if stream_index:
        return _stream_index_cmd(root)
    if want_digest:
        return _digest(root, digest_since)
    if inbox_stream:
        return _inbox(root, inbox_stream)

    canon = pathlib.Path(claude_md_override) if claude_md_override else find_canonical_claude_md(root)
    current_rev = None
    if canon and canon.is_file():
        current_rev = parse_current_rev(read_doctrine(canon))

    rev_note = f"canonical Rev {current_rev}" if current_rev is not None else "canonical Rev UNKNOWN"
    print(f"=== zeo {_version()} · {rev_note} ===")

    # Fold 1: governance-docs-first — grade the currency-enforcer (the skill) BEFORE the corpus.
    gov_errs = 0
    skills = [pathlib.Path(skill_path)] if skill_path else find_authoring_skills(root)
    if skills:
        print("\nGOVERNANCE (graded first — the currency-enforcer):")
    for sp in skills:
        if not sp.is_file():
            print(f"    {_SYM[ERROR]} [skill-missing] skill not found: {sp}")
            gov_errs += 1
        else:
            sfindings = check_skill_staleness(sp.read_text(encoding="utf-8", errors="replace"), current_rev)
            if not sfindings:
                print(f"    ✓ {sp.name} current at Rev {current_rev}")
            for f in sfindings:
                print(f"    {_SYM.get(f.severity, '?')} [{f.code}] {f.message}")
                if f.severity == ERROR:
                    gov_errs += 1

    files = list(iter_sow_files(target))  # WHAT to lint (file or dir)
    per_file: dict = {}
    has_fm: dict = {}
    status_of: dict = {}
    fm_of: dict = {}
    files_fm = []
    # Built ONCE corpus-wide (root, not target — a single-file lint still needs the whole
    # corpus to resolve a requested_by citation against). doctrine's replacement for
    # the `"known_stems" in dir()` dead code that recomputed this per ruling file.
    _known_stems = {pathlib.Path(f).stem for f in iter_sow_files(pathlib.Path(root))}
    _sow_index = build_sow_n_index(root)
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = extract_frontmatter(text)
        status, findings = lint_file(
            path,
            current_rev=current_rev,
            root=root,
            commit_mode=commit_check,
            known_stems=_known_stems,
            sow_index=_sow_index,
        )
        per_file[path] = list(findings)
        status_of[path] = status
        has_fm[path] = status != "SKIP"
        fm_of[path] = fm
        if isinstance(fm, dict):
            files_fm.append((path, fm))
    for path, extra in check_corpus(files_fm, root=root).items():
        per_file.setdefault(path, []).extend(extra)
    # doctrine: check_ruling_corpus (ruling-collision) was DEFINED, TESTED, and
    # NEVER CALLED from anywhere in this file - not from --commit-check (expected, a
    # per-file target's files_fm has one entry and a collision needs two), but not from
    # an ordinary FULL CORPUS run either. MEASURED before this line existed: a synthetic
    # two-file same-NNN fixture linted with the plain `zeo <dir>` (no --commit-check)
    # reported "2 passed - 0 failed", the collision completely invisible, which is a
    # stronger defect than doctrine's own diagnosis named (it attributed the miss only
    # to the per-file commit gate). Wiring it in here fixes reachability for any run that
    # sees the whole ruling namespace at once; the commit-path blindness for a SINGLE
    # staged file is separate and is what --commit-check-corpus below exists to close.
    for path, extra in check_ruling_corpus(files_fm).items():
        per_file.setdefault(path, []).extend(extra)
    # doctrine (binds resolve through stream-index.md) and doctrine (a ruling
    # naming an asking SOW whose resolved_by does not cite it back) - both corpus-level,
    # both built on the SAME index/known_stems computed above, never rebuilt per file.
    _index = build_stream_index(root)
    _stem_index = build_stem_index(root)
    for path, extra in check_binds_corpus(files_fm, root, commit_mode=commit_check, index=_index).items():
        per_file.setdefault(path, []).extend(extra)
    for path, extra in check_ruling_receipts(
        files_fm,
        root,
        commit_mode=commit_check,
        sow_index=_sow_index,
        stem_index=_stem_index,
    ).items():
        per_file.setdefault(path, []).extend(extra)
    # RULING-268 s1 item 2: resolves: <stream>#<n>#<question-id> — the fine-grained
    # sibling of check_ruling_receipts immediately above, same corpus-wide _sow_index.
    for path, extra in check_resolves(
        files_fm,
        root,
        commit_mode=commit_check,
        sow_index=_sow_index,
    ).items():
        per_file.setdefault(path, []).extend(extra)

    # doctrine item 1: `n_skip` used to aggregate three causally different
    # outcomes under ONE hardcoded label ("no frontmatter"), which was simply false
    # for two of the three — a file with eight frontmatter fields reported as having
    # none. Each SKIP branch in lint_file() is distinguished here by the same signal
    # lint_file itself used to choose it (fm is None / a genre-unknown finding / a
    # preschema-block finding / neither, i.e. a deliberate _SKIP_GENRES match) — never
    # re-guessed. Conformance rule (binding): a summary line NAMES THE CAUSE of every
    # count it prints, or prints no cause at all; a zero-valued cause prints nothing.
    n_pass = n_fail = n_cannot = 0
    n_skip_nofm = n_skip_genre = n_skip_preschema = n_skip_deliberate = 0
    fails, warns, hints, cannot, skip_warns = [], [], [], [], []
    for path in files:
        if not has_fm.get(path, False):
            findings = per_file.get(path, [])
            codes = {f.code for f in findings}
            if "genre-unknown" in codes:
                # doctrine item 2: this WARN is manufactured by lint_file (the
                # open-world genre default, core.py:466-479) and was previously
                # discarded here — computed and never shown. Surface it.
                n_skip_genre += 1
                skip_warns.append((path, findings))
            elif "preschema-block" in codes:
                n_skip_preschema += 1
                skip_warns.append((path, findings))
            elif fm_of.get(path) is None:
                n_skip_nofm += 1
            else:
                # fm parsed to a schema-shaped dict but genre is a deliberate
                # _SKIP_GENRES match (relay) — lint_file returns SKIP with no
                # findings. Learnings are graded now (no longer deliberate skip).
                n_skip_deliberate += 1
            continue
        findings = per_file.get(path, [])
        errs = [f for f in findings if f.severity == ERROR]
        wrn = [f for f in findings if f.severity == WARN]
        hnt = [f for f in findings if f.severity == HINT]
        # bucket on lint_file's AUTHORITATIVE verdict, never a re-derived 2-way one
        # (the CLI/lint_file disagreement class — diag). check_corpus may have
        # ADDED an ERROR post-hoc, so a corpus-error still escalates to FAIL.
        st = status_of.get(path, "PASS")
        if errs:
            n_fail += 1
            fails.append((path, errs + wrn + hnt))
        elif st == "CANNOT-GRADE":
            n_cannot += 1
            cannot.append((path, wrn + hnt))  # instrument blind, NOT file-bad
        else:
            n_pass += 1
            if wrn:
                warns.append((path, wrn + hnt))
            elif hnt:
                hints.append((path, hnt))

    for path, fs in cannot:
        print(f"\nCANNOT-GRADE (instrument could not resolve this file — NOT a pass): {path}")
        for f in fs:
            print(f"    {_SYM.get(f.severity, '?')} [{f.code}] {f.message}")
    for path, fs in fails:
        print(f"\nFAIL: {path}")
        for f in fs:
            print(f"    {_SYM.get(f.severity, '?')} [{f.code}] {f.message}")
    for path, fs in warns:
        print(f"\nWARN: {path}")
        for f in fs:
            print(f"    {_SYM.get(f.severity, '?')} [{f.code}] {f.message}")
    for path, fs in hints:
        print(f"\nHINT: {path}")
        for f in fs:
            print(f"    {_SYM.get(f.severity, '?')} [{f.code}] {f.message}")
    # doctrine item 2: the SKIP-with-a-WARN cases (genre-unknown, preschema-block)
    # carry a diagnosis lint_file already computed — render it, same as any other WARN,
    # unless --quiet asked for the count without the noise (a corpus-wide run can be many
    # lines; example-stream makes that a stated flag, not a silent decision to keep discarding it).
    if not quiet:
        for path, fs in skip_warns:
            print(f"\nSKIP (not graded — cause below): {path}")
            for f in fs:
                print(f"    {_SYM.get(f.severity, '?')} [{f.code}] {f.message}")
    skip_parts = []
    if n_skip_nofm:
        skip_parts.append(f"{n_skip_nofm} skipped (no frontmatter)")
    if n_skip_preschema:
        skip_parts.append(f"{n_skip_preschema} skipped (pre-schema block)")
    if n_skip_deliberate:
        skip_parts.append(f"{n_skip_deliberate} skipped (deliberate)")
    if n_skip_genre:
        skip_parts.append(f"{n_skip_genre} skipped (genre not graded)")
    skip_str = (" · " + " · ".join(skip_parts)) if skip_parts else ""
    print(
        f"\n{n_pass} passed · {n_fail} failed · {n_cannot} cannot-grade{skip_str}"
        + (f" · governance errors: {gov_errs}" if skill_path else "")
    )
    return 1 if (n_fail or n_cannot or gov_errs) else 0


# ── Typer front door (Rev migration: hand-rolled argv parser → Typer) ──────────
#
# `main(argv)` above is UNTOUCHED and remains the single source of truth for every
# verb's behavior, every legacy bare flag (--board, --triage, --digest, --mint, ...),
# every exit code, and every --json payload — it is what all 809 existing tests call
# directly, and what every one of the `_cmd_*` handlers still is. This section adds a
# SEPARATE, ADDITIONAL front door: a Typer `app` that becomes the `zeo` console-script
# entry point, so that `zeo --help` / `zeo <verb> --help` (at the process level) get
# Typer's rich-formatted listing of the 20 top-level verbs — the actual point of this
# migration — while every verb's own runtime behavior is a plain passthrough into the
# SAME handler `main()` already dispatches to. Nothing here re-implements business
# logic; `ctx.args` is handed to `main()` verbatim.
#
# Legacy bare flags (`--board`, `--kosten`, ...) and lint positionals (`zeo some.md`)
# are NOT modeled as Typer options on the root command: Click's own command-resolution
# treats an unrecognized first token as "no such command" before any callback logic
# can run, so a flat mix of "verb OR arbitrary legacy flag OR arbitrary lint path" is
# not expressible as one Typer command group without reimplementing (and risking
# behavioral drift in) the legacy parser's own disambiguation rules (e.g. "does this
# positional look like a path, a duration, or a stream name" — see --digest/--restaufwand
# above). Instead, `cli_entry()` (the actual console-script target) peeks at argv[0]:
# a known verb name routes into the Typer `app`; --version is handled directly;
# everything else — every legacy flag, every bare invocation, every lint target —
# routes to `main()` exactly as it always has. This is the "thin compatibility shim
# that detects the legacy invocation and forwards" option named in this migration's
# own constraints, chosen because it holds the legacy surface byte-identical by
# construction (same function, same code path) rather than by re-derivation.
_VERB_NAMES = (
    "help",
    "orient",
    "new",
    "work",
    "next",
    "board",
    "triage",
    "digest",
    "index",
    "mint",
    "hooks",
    "init",
    "scaffold",
    "bridges",
    "equip",
    "cold-start",
    "sow",
    "intake",
    "doctor",
    "artifact",
    "seat",
    "execution",
    "dispatch",
)

app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    help="zeo (zero-employee) — portable SOW governance tooling.",
)

_PASSTHROUGH = {
    "context_settings": {"allow_extra_args": True, "ignore_unknown_options": True},
    "add_help_option": False,
}


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Print the installed zeo version and exit."),
):
    """zeo (zero-employee) — portable SOW governance tooling.

    Bare `zeo`, every legacy `--flag` (--board, --triage, --digest, --mint, ...),
    and lint targets (`zeo path/to/file.md`) are handled before Typer's own command
    resolution runs (see `cli_entry`) and never reach this callback in practice;
    it exists for `--version` and so `zeo --help` / `zeo` under Typer's own argv
    handling degrade sensibly if invoked directly against `app()`.
    """
    if version:
        print(_version())
        raise typer.Exit(0)
    if ctx.invoked_subcommand is None:
        raise typer.Exit(main([]))


@app.command("help", **_PASSTHROUGH)
def _typer_help(ctx: typer.Context):
    """Progressive help (zeo help --all for the full legacy reference)."""
    raise typer.Exit(main(["help", *ctx.args]))


@app.command("orient", **_PASSTHROUGH)
def _typer_orient(ctx: typer.Context):
    """Human/agent orientation briefing (--json for agents)."""
    raise typer.Exit(main(["orient", *ctx.args]))


@app.command("new", **_PASSTHROUGH)
def _typer_new(ctx: typer.Context):
    """Start intake / SOW / project (interactive menu, or --json)."""
    raise typer.Exit(main(["new", *ctx.args]))


@app.command("work", **_PASSTHROUGH)
def _typer_work(ctx: typer.Context):
    """Continue governed work: listing, or detail for one stream."""
    raise typer.Exit(main(["work", *ctx.args]))


@app.command("next", **_PASSTHROUGH)
def _typer_next(ctx: typer.Context):
    """Highest-priority next action (--json for agents)."""
    raise typer.Exit(main(["next", *ctx.args]))


@app.command("board", **_PASSTHROUGH)
def _typer_board(ctx: typer.Context):
    """Write local STATE.md (gitignored). Legacy alias: zeo --board."""
    raise typer.Exit(main(["board", *ctx.args]))


@app.command("branches", **_PASSTHROUGH)
def _typer_branches(ctx: typer.Context):
    """Classify every branch as LIVE/STALE-BASE/ORPHANED/MERGED/RESCUE (RULING-324). Report-only."""
    raise typer.Exit(main(["branches", *ctx.args]))


@app.command("check-base-fresh", **_PASSTHROUGH)
def _typer_check_base_fresh(ctx: typer.Context):
    """Exit non-zero when HEAD's merge-base with origin/main is behind main's tip."""
    raise typer.Exit(main(["check-base-fresh", *ctx.args]))


@app.command("triage", **_PASSTHROUGH)
def _typer_triage(ctx: typer.Context):
    """The operator worklist. Legacy alias: zeo --triage."""
    raise typer.Exit(main(["triage", *ctx.args]))


@app.command("digest", **_PASSTHROUGH)
def _typer_digest(ctx: typer.Context):
    """What happened in a session. Legacy alias: zeo --digest."""
    raise typer.Exit(main(["digest", *ctx.args]))


@app.command("index", **_PASSTHROUGH)
def _typer_index(ctx: typer.Context):
    """zeo index streams|rulings — canonical form of --stream-index / --ruling-index."""
    raise typer.Exit(main(["index", *ctx.args]))


@app.command("mint", **_PASSTHROUGH)
def _typer_mint(ctx: typer.Context):
    """zeo mint ruling|sow ... — canonical subcommand form of --mint."""
    raise typer.Exit(main(["mint", *ctx.args]))


@app.command("hooks", **_PASSTHROUGH)
def _typer_hooks(ctx: typer.Context):
    """install | pre-commit | session-start | stop | pretooluse-git."""
    raise typer.Exit(main(["hooks", *ctx.args]))


@app.command("init", **_PASSTHROUGH)
def _typer_init(ctx: typer.Context):
    """Scaffold a corpus: claude-md/CLAUDE.md marker + root CLAUDE.md."""
    raise typer.Exit(main(["init", *ctx.args]))


@app.command("scaffold", **_PASSTHROUGH)
def _typer_scaffold(ctx: typer.Context):
    """Create projects/<project>/CLAUDE.md + Rev-17 SOW under sow/<stream>/."""
    raise typer.Exit(main(["scaffold", *ctx.args]))


@app.command("bridges", **_PASSTHROUGH)
def _typer_bridges(ctx: typer.Context):
    """Install/refresh selected IDE/agent bridges only."""
    raise typer.Exit(main(["bridges", *ctx.args]))


@app.command("equip", **_PASSTHROUGH)
def _typer_equip(ctx: typer.Context):
    """Install .claude/ + CLAUDE.md ALWAYS-tier files into a work repo."""
    raise typer.Exit(main(["equip", *ctx.args]))


@app.command("cold-start", **_PASSTHROUGH)
def _typer_cold_start(ctx: typer.Context):
    """RULING-278 s3 Ist-Aufnahme (partial) against a target repo, read-only."""
    raise typer.Exit(main(["cold-start", *ctx.args]))


@app.command("sow", **_PASSTHROUGH)
def _typer_sow(ctx: typer.Context):
    """new|set|add|remove|draft|from-intake|doctor — SOW authoring."""
    raise typer.Exit(main(["sow", *ctx.args]))


@app.command("intake", **_PASSTHROUGH)
def _typer_intake(ctx: typer.Context):
    """new|open|edit|doctor|context|mission|propose|promote — intent capture."""
    raise typer.Exit(main(["intake", *ctx.args]))


@app.command("doctor", **_PASSTHROUGH)
def _typer_doctor(ctx: typer.Context):
    """zeo doctor PATH | zeo doctor --changed — actionable readiness check."""
    raise typer.Exit(main(["doctor", *ctx.args]))


@app.command("artifact", **_PASSTHROUGH)
def _typer_artifact(ctx: typer.Context):
    """zeo artifact set FILE KEY VALUE (thin alias onto zeo sow set)."""
    raise typer.Exit(main(["artifact", *ctx.args]))


@app.command("seat", **_PASSTHROUGH)
def _typer_seat(ctx: typer.Context):
    """zeo seat [init|use NAME] — named GitHub-identity switching for a
    two-account review split (see docs/seats.md)."""
    raise typer.Exit(main(["seat", *ctx.args]))


@app.command("execution", **_PASSTHROUGH)
def _typer_execution(ctx: typer.Context):
    """zeo execution validate|import PATH — JSON execution receipts."""
    raise typer.Exit(main(["execution", *ctx.args]))


@app.command("dispatch", **_PASSTHROUGH)
def _typer_dispatch(ctx: typer.Context):
    """zeo dispatch acquire|check-remote|cleanup — exclusive unattended ownership."""
    raise typer.Exit(main(["dispatch", *ctx.args]))


def cli_entry() -> None:
    """The actual `zeo` console-script target (see [project.scripts] in pyproject.toml).

    Routes a known verb as argv[0] into the Typer `app` (rich --help, real
    subcommands); routes --version directly; routes everything else — every
    legacy bare flag, a bare invocation, a lint target — into `main()`,
    completely unchanged from the pre-Typer entry point. See the module-level
    comment above `_VERB_NAMES` for why this split exists instead of a single
    Typer command group.
    """
    argv = sys.argv[1:]
    if argv and argv[0] in _VERB_NAMES:
        app()
        return
    if argv and argv[0] == "--version":
        print(_version())
        raise SystemExit(0)
    # Only --help routes to the Typer app (its root callback binds --help but
    # not -h). -h falls through to main(argv), which has always treated -h as
    # a first-class --help alias in its own dispatch (7 call sites) — routing
    # it into Typer here silently broke that alias (Typer: "No such option: -h").
    if not argv or argv[0] == "--help":
        app()
        return
    raise SystemExit(main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
