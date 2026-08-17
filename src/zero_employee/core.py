"""Core linting logic.

v0 (§14 keystone): every SHIPPED ledger entry carries a `commit` AND a non-empty
`check`. UNCHANGED in this revision — `extract_frontmatter` and `check_keystone`
are byte-identical to v0; the 6 keystone tests still pass.

v0.2 (Impl-B, Rev 11 §14/§15 identity): additive `n:` and `schema_rev:` checks.
Era-aware by construction — strict identity rules fire ONLY on files that declare
`n:` (Rev-11-era SOWs). Legacy files get a backfill WARN, never an ERROR, so the
existing corpus (uppercase prefixes, -RevN suffixes, pre-11 n-dups) is not broken.

BOUNDARY unchanged: this is a FORM validator. It does not RUN ledger checks
against repo bytes — that is C (the verifier), a separate tool.
"""

from __future__ import annotations
import hashlib
import os
import subprocess
import pathlib
import re
import tomllib
import datetime
from collections import namedtuple, defaultdict
import yaml

# V1-C: B2 grandfather manifest — packaged default is empty/unarmed. Private corpora may
# override via ZEO_GRANDFATHER_MANIFEST or <corpus>/tools/doctrine/grandfather_manifest.toml.
_MANIFEST_PATH = pathlib.Path(__file__).parent / "grandfather_manifest.toml"
_CORPUS_MANIFEST_REL = pathlib.Path("tools") / "doctrine" / "grandfather_manifest.toml"

# ── finding model ───────────────────────────────────────────────────
Finding = namedtuple("Finding", ["severity", "code", "message"])
ERROR = "ERROR"
WARN = "WARN"
HINT = "HINT"  # agent guidance; never fails the exit code


# ── v0 keystone: UNCHANGED ──────────────────────────────────────────
def extract_frontmatter(text: str):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            try:
                return yaml.safe_load("\n".join(lines[1:i]))
            except yaml.YAMLError:
                return "MALFORMED"
    return None


def check_keystone(fm: dict) -> list[str]:
    """v0 keystone — delegated to schemas.keystone_messages (same message contract)."""
    from .schemas import keystone_messages

    return keystone_messages(fm)


# ── NEW: canonical-rev source (for schema_rev) ──────────────────────
_REV_RE = re.compile(r"\(Rev\s+(\d+)\b")
_SKILL_REV_RE = re.compile(r"Teaches CLAUDE\.md Rev\s+(\d+)")


def parse_current_rev(text: str) -> int | None:
    """Extract N from the DOC-DATE '(Rev N, ...)' marker in canonical CLAUDE.md."""
    for line in text.splitlines():
        if "DOC-DATE" in line:
            m = _REV_RE.search(line)
            if m:
                return int(m.group(1))
    m = _REV_RE.search(text)  # fallback: first (Rev N) anywhere
    return int(m.group(1)) if m else None


def find_canonical_claude_md(start) -> pathlib.Path | None:
    """Walk up from `start` to the sows-repo root holding claude-md/CLAUDE.md."""
    start = pathlib.Path(start).resolve()
    bases = [start] + list(start.parents) if start.is_dir() else [start.parent] + list(start.parents)
    for base in bases:
        cand = base / "claude-md" / "CLAUDE.md"
        if cand.is_file():
            return cand
    return None


# ── NEW: n: (identity, filename-grounded, era-aware) ────────────────
# Case-insensitive prefix (F-1): corpus uses UPPERCASE example-stream, sow: is lowercase.
_SOW_FILE_RE = re.compile(r"^(?P<stream>.+)-SOW-(?P<n>\d+)-(?P<slug>.+)\.md$", re.IGNORECASE)
_STREAM_BEFORE_SOW = re.compile(r"^(?P<stream>.+?)-SOW-\d+", re.IGNORECASE)


def _stream_prefix(name: str) -> str:
    """Stream-prefix of a flat-legacy filename, used as the project PROXY when
    project_of is None (V1-D per-project arming, 3rd dimension: n-collision).
    Master ruling (doctrine): within an n: collision group, files sharing a prefix
    are a REAL same-stream duplicate (ERROR); distinct prefixes are a cross-stream
    namespace artifact migration resolves (WARN). Prefer the -SOW- infix; fall back
    to the leading UPPER/digit run for varied legacy names (SEAM-2-Conversion2...
    has no -SOW- infix). Proven against the real colliding corpus, DS5-SCRATCH-25."""
    stem = name[:-3] if name.endswith(".md") else name
    m = _STREAM_BEFORE_SOW.match(stem)
    if m:
        return m.group("stream").upper()
    keep = []
    for seg in stem.split("-"):
        if seg and seg.upper() == seg:  # all-caps or digits: still stream territory
            keep.append(seg)
        else:
            break
    return "-".join(keep).upper() if keep else stem.upper()


_REVSUFFIX_RE = re.compile(
    r"-Rev\d+$"
)  # V1-E/F-A: case-SENSITIVE. Capital-R -Rev is the chain-suffix (125 in corpus); lowercase -rev is a descriptive slug word (doctrine-a-skill-rev11, the only case). IGNORECASE wrongly flagged the descriptive slug. Proven DS4-CORPUS-FA-41.


def filename_sow_number(path) -> int | None:
    """The <n> in a *-SOW-<n>-*.md filename, or None if not a SOW filename."""
    m = _SOW_FILE_RE.match(pathlib.Path(path).name)
    return int(m.group("n")) if m else None


def find_authoring_skills(start) -> list:
    # doctrine: the skill check runs by DEFAULT. Walk up to the sows root and
    # grade every authoring/*SKILL.md - the friction-fix for a check that existed,
    # was wired, and sat behind a flag nobody passed (DS-63 sD).
    p = pathlib.Path(start).resolve()
    bases = [p] + list(p.parents) if p.is_dir() else [p.parent] + list(p.parents)
    # Governance docs live in TWO fleet-wide tiers: authoring/ (per-genre skills)
    # and roles/ (per-role boot docs). roles/BOOT-MASTER.md is the one document a
    # Master reads first, and a STALE boot doc manufactures GHOST PRECEDENT — its
    # ancestor's doctrine summary was cited as settled precedent for a ruling
    # whose file never existed (doctrine). It must be graded WITHOUT a flag:
    # a check behind a flag nobody passes is the friction failure doctrine
    # was chartered to fix, and a new directory silently reintroduced it.
    found = []
    for base in bases:
        for sub, pat in (("authoring", "*SKILL.md"), ("roles", "BOOT-*.md")):
            d = base / sub
            if d.is_dir():
                found.extend(sorted(d.glob(pat)))
        if found:
            return found
    return []


def check_n(path, fm, root=None) -> list[Finding]:
    """Per-file identity. Strict only when frontmatter declares n: (Rev-11 era)."""
    out: list[Finding] = []
    name = pathlib.Path(path).name
    declared = fm.get("n")
    sow = str(fm.get("sow", "")).strip()
    m = _SOW_FILE_RE.match(name)

    if declared is None:
        # legacy / pre-Rev-11: nudge to backfill, NEVER fail (grandfathering F-2/F-3)
        if m:
            out.append(
                Finding(
                    WARN,
                    "n-missing",
                    f"'{name}' looks like a SOW but has no `n:` — backfill n:/schema_rev: (pre-Rev-11)",
                )
            )
        return out

    # Rev-11-era: strict
    if not m:
        # Master ruling (doctrine/47): arm per-project on migration-completion. A file
        # in canonical shape (project_of non-None) is supposed to conform -> ERROR;
        # an unmigrated project (project_of None) WARNs-to-backfill until it migrates.
        # doctrine: key the era-gate on the FILENAME property it grades. The DIRECTORY
        # migration and the FILENAME migration are independent facts, and keying the first on
        # the second disarmed this grandfathering the moment the restructure moved never-renamed
        # files under <project>/sow/. MEASURED: it blocked a 190-file project: backfill that
        # removed 135 failures, on files whose only defect is a legacy name.
        # A rename is --promote's transactional job (doctrine) and it is NOT free:
        # the citation scan showed the references live in landed rulings' requested_by (an
        # IMMUTABLE field, doctrine) and in append-only SOWs. So: WARN-pending-promote.
        out.append(
            Finding(
                WARN,
                "n-pattern-premigration",
                f"'{name}' declares n:{declared} with a legacy filename; --promote assigns the "
                f"canonical <sow>-SOW-<n>-<slug> name in git birth order (doctrine). "
                f"WARN-pending-promote.",
            )
        )
        return out

    file_n = int(m.group("n"))
    stream = m.group("stream")
    slug = m.group("slug")

    try:
        if int(declared) != file_n:
            out.append(
                Finding(
                    ERROR,
                    "n-mismatch",
                    f"frontmatter n:{declared} != filename number {file_n} in '{name}'",
                )
            )
    except (TypeError, ValueError):
        out.append(Finding(ERROR, "n-nonint", f"n: '{declared}' is not an integer in '{name}'"))

    if _REVSUFFIX_RE.search(slug):
        out.append(
            Finding(
                ERROR,
                "n-revsuffix",
                f"'{name}' carries a -RevN suffix — rev lives in frontmatter rev:/supersedes: (Rev 11)",
            )
        )

    # F-1: corpus uses UPPERCASE prefix, sow: is lowercase. Match case-INSENSITIVELY
    # and silently; a mere case difference is not an error (and warning on it would
    # fire across the whole corpus = noise). Canonical-case normalization is a Master
    # ruling raised in the SOW, not enforced here.
    if sow and stream.lower() != sow.lower():
        out.append(
            Finding(
                ERROR,
                "n-stream",
                f"filename stream '{stream}' != frontmatter sow:'{sow}' in '{name}'",
            )
        )
    return out


# ── NEW: schema_rev: (era-awareness + staleness) ────────────────────
def check_schema_rev(fm, current_rev) -> list[Finding]:
    out: list[Finding] = []
    sr = fm.get("schema_rev")
    if sr is None:
        if fm.get("n") is not None:  # a Rev-11 SOW MUST carry schema_rev
            out.append(
                Finding(
                    WARN,
                    "schema-missing",
                    "no `schema_rev:` — required from Rev 11 on; backfill",
                )
            )
        return out
    try:
        sr = int(sr)
    except (TypeError, ValueError):
        out.append(Finding(ERROR, "schema-nonint", f"schema_rev: '{sr}' is not an integer"))
        return out
    if current_rev is None:
        out.append(
            Finding(
                WARN,
                "schema-nocanon",
                f"schema_rev:{sr} present but canonical CLAUDE.md rev not locatable to compare",
            )
        )
        return out
    if sr < current_rev:
        out.append(
            Finding(
                WARN,
                "schema-stale",
                f"STALE-SCHEMA: schema_rev:{sr} < canonical Rev {current_rev} — re-review "
                f"(graded against Rev {sr}'s rules, not failed)",
            )
        )
    elif sr > current_rev:
        out.append(
            Finding(
                ERROR,
                "schema-ahead",
                f"schema_rev:{sr} is AHEAD of canonical Rev {current_rev} — unmerged doctrine or typo",
            )
        )
    return out


# ── NEW: corpus-level (collision / gap), Rev-11 files only ──────────
def parse_skill_rev(text: str) -> "int | None":
    """Extract N from the skill's 'Teaches CLAUDE.md Rev N' dated header line."""
    m = _SKILL_REV_RE.search(text)
    return int(m.group(1)) if m else None


def check_skill_staleness(skill_text: str, current_rev) -> list:
    """Fold 1: the governance skill declares its era in prose ('Teaches CLAUDE.md
    Rev N'), not schema_rev frontmatter. Grade the currency-enforcer first."""
    out = []
    declared = parse_skill_rev(skill_text)
    if declared is None:
        out.append(
            Finding(
                WARN,
                "skill-rev-missing",
                "skill has no 'Teaches CLAUDE.md Rev N' header - cannot determine its era",
            )
        )
        return out
    if current_rev is None:
        out.append(
            Finding(
                WARN,
                "skill-nocanon",
                f"skill declares Rev {declared} but canonical rev not locatable to compare",
            )
        )
        return out
    if declared < current_rev:
        out.append(
            Finding(
                WARN,
                "skill-stale",
                f"STALE: this skill declares Rev {declared} < canonical Rev "
                f"{current_rev} - re-sync the skill to Rev {current_rev} "
                f"(the currency-enforcer is out of date)",
            )
        )
    elif declared > current_rev:
        out.append(
            Finding(
                ERROR,
                "skill-ahead",
                f"skill declares Rev {declared} AHEAD of canonical Rev {current_rev} - unmerged or typo",
            )
        )
    return out


def _stream_of(path, root=None):
    """The STREAM a SOW belongs to - the directory under <project>/sow/.

    The schema (sow-authoring, Rev 11) says n: is "a fresh increment for THE STREAM'S DIR".
    check_corpus keyed collisions on (project, n) only, so ACTING-doctrine
    GUIDE-SWEEP-doctrine - both legitimately n:1 rev:a - were reported as duplicates of each
    other: 78 ERRORs across 19 streams, every one of them correct as filed.

    doctrine _stream_prefix to GUESS the stream from the filename because files
    were flat. They are in stream directories now, so the stream is a PATH FACT; the prefix
    remains the fallback for flat-legacy files exactly as that ruling intended.
    """
    parts = pathlib.Path(path).parts
    if "sow" in parts:
        i = len(parts) - 1 - parts[::-1].index("sow")
        if i + 2 <= len(parts) - 1:  # a directory exists between sow/ and the file
            return parts[i + 1].upper()
    return _stream_prefix(pathlib.Path(path).name)


# TOMBSTONE-AWARE (same class as check_ruling_corpus's _NOT_LIVE, core.py:2116 - paid live
# at profrodai/org 2026-08-16, one turn after the ruling fix): a VOIDED, SUPERSEDED, or
# STALE SOW sharing an n/rev with a live file is the normal, expected shape of a
# caught-and-corrected duplicate-numbering mistake - not a live, unresolved collision. A
# distinct constant from _NOT_LIVE: SOWs carry a third genuinely-dead status, STALE, that
# rulings do not. Deliberately NOT the broader STATUS_RESTING set - CLOSEOUT/SHIPPED/
# HANDOVER/HELD/BLOCKED/FINDING are terminal-but-still-THE-record states; a second file
# claiming their n/rev is still a live collision, and must keep erroring.
_NOT_LIVE_SOW = {"VOIDED", "SUPERSEDED", "STALE"}


def check_corpus(files_fm, root=None) -> dict:
    """files_fm: iterable of (path, fm). Per-project (V1-D): n-collision and n-gap
    scope to each PROJECT (project_of), so the same n in two projects is not a
    collision and gaps do not bleed across projects. Pre-migration all-None files
    group as one flat-legacy set = the prior behavior, preserved."""
    out = defaultdict(list)
    numbered = []  # (project, n, path, rev, status)
    files_fm = list(files_fm)
    # RECONCILED-BY-SUCCESSOR (doctrine: SOWs are append-only, a colliding file is
    # NEVER edited or status-flipped after the fact to silence a real n-collision -
    # see coverage-90 SOW-10/SOW-10, reconciled forward by SOW-11's own supersedes:10
    # + prose naming both filenames, rather than by touching either SOW-10 file).
    # A later, LIVE SOW in the same project whose own `supersedes:` names a colliding
    # `n` is exactly that reconciliation, already on record in the corpus - the
    # checker should recognize it as resolved (WARN, visible, non-blocking) instead
    # of demanding a status edit doctrine forbids. Keyed on (project, n) only: the
    # successor's OWN n/rev is irrelevant, only which n it claims to supersede.
    reconciled_ns = set()
    for path, fm in files_fm:
        succ_status = str(fm.get("status", "")).strip().upper()
        if succ_status in _NOT_LIVE_SOW:
            continue
        supersedes = fm.get("supersedes")
        if supersedes is None:
            continue
        try:
            proj = project_of(path, root)
            reconciled_ns.add((proj, int(supersedes)))
        except (TypeError, ValueError):
            continue
    for path, fm in files_fm:
        n = fm.get("n")
        if n is None:
            continue
        rev = fm.get("rev")
        rev = str(rev).strip() if rev is not None else None
        status = str(fm.get("status", "")).strip().upper()
        try:
            numbered.append((project_of(path, root), _stream_of(path, root), int(n), path, rev, status))
        except (TypeError, ValueError):
            continue
    by_pn = defaultdict(list)
    for proj, stream, n, path, rev, status in numbered:
        # STREAM enters the key ONLY for MIGRATED files. For those the stream is a path fact
        # and cross-stream n reuse is PERMANENTLY CORRECT (the schema: n is fresh per stream
        # dir). For FLAT-LEGACY files the group must stay whole so doctrine's prefix partition
        # still runs and still emits its cross-stream WARN - keying flat files by stream made
        # every group single-stream and deleted that ruled behaviour outright.
        by_pn[(proj, stream if proj is not None else None, n)].append((path, rev, status))
    for (proj, stream, n), entries in by_pn.items():
        if len(entries) <= 1:
            continue
        names = ", ".join(sorted(pathlib.Path(x).name for x, _, _ in entries))
        if proj is not None:
            # migrated project: same-project n reuse collides ONLY when rev also repeats
            # (doctrine B). Distinct revs = one identity's rev-chain, not a collision.
            by_rev = defaultdict(list)
            for path, rev, status in entries:
                by_rev[rev].append((path, status))
            for rev, rentries in by_rev.items():
                # TOMBSTONE-AWARE: only LIVE claimants count toward "real" duplicate.
                rpaths = [p for p, st in rentries if st not in _NOT_LIVE_SOW]
                if len(rpaths) > 1:
                    dup = ", ".join(sorted(pathlib.Path(x).name for x in rpaths))
                    if (proj, n) in reconciled_ns:
                        # RECONCILED BY A SUCCESSOR (see reconciled_ns above): a later
                        # live SOW's own `supersedes:` already names this n - the
                        # collision is a recorded, resolved fact, not an unaddressed
                        # one. WARN (visible, non-blocking) instead of ERROR
                        # (commit-blocking) - append-only doctrine forbids editing
                        # either colliding file's own status to silence this.
                        for p in rpaths:
                            out[p].append(
                                Finding(
                                    WARN,
                                    "n-collision-reconciled",
                                    f"n:{n} rev:{rev} used by {len(rpaths)} SOWs in stream "
                                    f"'{stream}' of project '{proj}' (duplicate): {dup} - "
                                    f"reconciled by a later SOW's own supersedes:{n} "
                                    f"(append-only doctrine: neither file is edited to "
                                    f"silence this, see the successor SOW for the ruling)",
                                )
                            )
                        continue
                    for p in rpaths:
                        out[p].append(
                            Finding(
                                ERROR,
                                "n-collision",
                                f"n:{n} rev:{rev} used by {len(rpaths)} SOWs in stream "
                                f"'{stream}' of project '{proj}' (duplicate): {dup}",
                            )
                        )
            continue
        # flat-legacy set: stream-prefix is the project PROXY (doctrine). Within a prefix,
        # collide ONLY when rev also repeats (doctrine B): distinct revs are one
        # identity's rev-chain (pass); a repeated rev is a real duplicate (ERROR).
        by_prefix = defaultdict(list)
        for path, rev, status in entries:
            by_prefix[_stream_prefix(pathlib.Path(path).name)].append((path, rev, status))
        for pfx, pentries in by_prefix.items():
            if len(pentries) > 1:
                # same stream, same n, multiple files: partition by rev
                by_rev = defaultdict(list)
                for path, rev, status in pentries:
                    by_rev[rev].append((path, status))
                # TOMBSTONE-AWARE: same filter as the migrated-project branch above - a
                # VOIDED/SUPERSEDED/STALE claimant does not count toward "real" duplicate.
                real_dups = {r: [p for p, st in v if st not in _NOT_LIVE_SOW] for r, v in by_rev.items()}
                real_dups = {r: v for r, v in real_dups.items() if len(v) > 1}
                if real_dups:
                    for rev, rpaths in real_dups.items():
                        dup = ", ".join(sorted(pathlib.Path(x).name for x in rpaths))
                        for p in rpaths:
                            out[p].append(
                                Finding(
                                    ERROR,
                                    "n-collision",
                                    f"n:{n} rev:{rev} used by {len(rpaths)} SOWs in stream '{pfx}' (same-stream duplicate): {dup}",
                                )
                            )
                # distinct-rev files in one prefix = a legitimate rev-chain -> NO finding
            else:
                out[pentries[0][0]].append(
                    Finding(
                        WARN,
                        "n-collision-premigration",
                        f"n:{n} shared across flat-legacy streams (namespace artifact, resolves on migration): {names}",
                    )
                )
    by_proj = defaultdict(list)
    for proj, _stream, n, path, rev, _status in numbered:  # gaps stay per-PROJECT
        by_proj[proj].append((n, path))
    for proj, seq in by_proj.items():
        ns = sorted({n for n, _ in seq})
        if len(ns) >= 2:
            missing = sorted(set(range(ns[0], ns[-1] + 1)) - set(ns))
            if missing:
                top = max(seq, key=lambda t: t[0])[1]
                where = str(missing) if len(missing) <= 8 else f"{len(missing)} numbers between {ns[0]} and {ns[-1]}"
                scope = f"project '{proj}'" if proj else "flat-legacy set"
                out[top].append(
                    Finding(
                        WARN,
                        "n-gap",
                        f"n-sequence in {scope} has gaps at {where} (ok if VOIDED/retired)",
                    )
                )
    return dict(out)


# ── lint_file: additive aggregation (2-tuple contract preserved) ────
def check_status(path, fm, root):
    """Status enum — delegated to schemas.grade_sow (era-aware)."""
    from .schemas import grade_sow

    project_known = project_of(path, root) is not None
    return [
        f for f in grade_sow(fm, project_known=project_known) if f.code in ("status-enum", "status-enum-premigration")
    ]


# WARN codes that signal the INSTRUMENT could not resolve (not that the file is bad).
# In a schema-era file these escalate to CANNOT-GRADE rather than passing (doctrine).
_CANNOT_GRADE_CODES = {"schema-nocanon"}


_SCHEMA_KEYS = {
    "sow",
    "n",
    "status",
    "rev",
    "schema_rev",
    "lifecycle",
    "ledger",
    "genre",
    "ruling",
    "created",
    "supersedes",
}


def is_schema_shaped(fm) -> bool:
    """Does this frontmatter carry ANY schema field, or is it a `---` block that happens to
    be there?

    MEASURED (GM-example-stream-199): ten example-project files open with a block holding ONE key - `note:`,
    a DELIVERY INSTRUCTION to the operator ("Save to the SOW repo as ...") that got saved into
    the file. No sow:, no n:, no status:. They are Class-A content wearing a `---` block.
    Grading them as schema SOWs made them FAIL for missing ONE field when they are missing
    every field, and it invited the wrong write that lints green (doctrine).
    """
    return isinstance(fm, dict) and bool(_SCHEMA_KEYS & set(fm))


def lint_file(
    path,
    current_rev=None,
    root=None,
    commit_mode=False,
    known_stems=None,
    sow_index=None,
) -> tuple[str, list]:
    # `known_stems`/`sow_index` are OPTIONAL corpus-wide caches a caller (cli.py) builds
    # ONCE and passes in. The previous default here (`known_stems if "known_stems" in
    # dir() else None`) tested a name that was NEVER a local variable — always False,
    # always the recompute branch below, on EVERY ruling file in the corpus. Recorded and
    # fixed together rather than separately, since this build already touches this exact
    # branch for doctrine's stream#n form.
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return "FAIL", [Finding(ERROR, "io", f"could not read: {e}")]
    fm = extract_frontmatter(text)
    if fm is None:
        return "SKIP", []
    if fm == "MALFORMED":
        return "FAIL", [Finding(ERROR, "yaml", "frontmatter is not valid YAML")]
    if not isinstance(fm, dict):
        return "FAIL", [Finding(ERROR, "yaml", "frontmatter did not parse to a mapping")]
    if not is_schema_shaped(fm):
        # A `---` block carrying no schema field at all is PRE-SCHEMA content, not a SOW
        # missing one field. Say so and route it to --migrate; do not fail it into a wrong
        # write (doctrine: an unrecognised shape SKIPs with a WARN, never grades as a SOW).
        return "SKIP", [
            Finding(
                WARN,
                "preschema-block",
                f"frontmatter carries no schema field (keys: {sorted(fm) or 'none'}) - PRE-SCHEMA "
                f"content with a stray block; --migrate generates the real frontmatter",
            )
        ]
    genre = discriminate(path, fm)
    if genre == "ruling":
        from .schemas import grade_ruling

        rf = grade_ruling(fm, raw_text=text, commit_mode=commit_mode)
        _stems = known_stems
        if _stems is None and root:
            _stems = {pathlib.Path(f).stem for f in iter_sow_files(pathlib.Path(root))}
        if _stems:
            _rbf = check_requested_by(fm, text, _stems, sow_index=sow_index)
            if commit_mode:
                # doctrine: gate the FUTURE at the commit path; a ghost being committed
                # NOW is an ERROR. Landed ghosts (the corpus audit, commit_mode=False) stay
                # WARN - immutable under doctrine, repaired by amendment not by a failed gate.
                _rbf = [
                    Finding(ERROR, f.code, f.message)
                    if f.code in ("requested_by-ghost", "requested_by-ghost-stream-n")
                    else f
                    for f in _rbf
                ]
            rf = rf + _rbf
        return ("FAIL" if any(f.severity == ERROR for f in rf) else "PASS"), rf
    if genre == "charter":
        from .schemas import grade_charter

        cf = grade_charter(fm, commit_mode=commit_mode)
        return ("FAIL" if any(f.severity == ERROR for f in cf) else "PASS"), cf
    if genre == "learnings":
        from .schemas import grade_learnings

        lf = grade_learnings(fm, text=text)
        return ("FAIL" if any(f.severity == ERROR for f in lf) else "PASS"), lf
    if genre == "intake":
        from .schemas import grade_intake

        lines = text.splitlines(keepends=True)
        body = text
        if lines and lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    body = "".join(lines[i + 1 :])
                    break
        inf = grade_intake(fm, body=body, commit_mode=commit_mode)
        return ("FAIL" if any(f.severity == ERROR for f in inf) else "PASS"), inf
    if genre in _SKIP_GENRES:
        return "SKIP", []
    if genre != "sow":
        # OPEN-WORLD GENRES: Master coins new ones at will — the live corpus already
        # carries tombstone, session-record, escalation-memo, none of which existed
        # when this dispatch was written. A closed set cannot track an open vocabulary,
        # so the DEFAULT must be "I do not grade what I do not know", never "grade it
        # as the strictest thing I do know". doctrine (genre: tombstone) fell through
        # to the SOW grader and collected project-backfill + b2-premigration — SOW rules
        # applied to a ruling. Same shape as the exact-match status enum doctrine
        # broke (diag): fail closed on the ROW, never guess the grader.
        return "SKIP", [
            Finding(
                WARN,
                "genre-unknown",
                f"genre: {genre} has no grader — SKIPPED, not graded as a SOW. "
                "If this genre should be checked, teach the linter (do not let it "
                "inherit SOW rules by accident)",
            )
        ]
    from .schemas import grade_sow

    project_known = project_of(path, root) is not None if root is not None else (project_of(path) is not None)
    path_canonical = bool(_SOW_FILE_RE.match(pathlib.Path(path).name))
    findings = grade_sow(
        fm,
        commit_mode=commit_mode,
        path_canonical=path_canonical,
        project_known=project_known,
    )
    findings += check_n(path, fm, root)
    findings += check_schema_rev(fm, current_rev)
    findings += check_project(path, fm, root)
    findings += check_b2(path, fm, root)
    if any(f.severity == ERROR for f in findings):
        return "FAIL", findings
    # CANNOT-GRADE (Sparring doctrine): the file declares schema-era intent but the linter
    # could not fully resolve it (e.g. schema_rev present yet canonical rev not locatable) —
    # a WARN like schema-nocanon in a file that MEANS to conform. Never PASS on that
    # uncertainty; speak it aloud. Pre-schema files (no schema_rev) are SKIP, not here.
    _blind = [f for f in findings if f.code in _CANNOT_GRADE_CODES]
    if _blind and fm.get("schema_rev") is not None:
        return "CANNOT-GRADE", findings
    return "PASS", findings


# Required schema-14 fields a conformant SOW MUST carry, read as the migration contract.
# NOT a hand-list that drifts (the skill's own stale "Rev 13" is the proof): these mirror the
# fields lint_file already checks (n:165, schema_rev:214, project:449) plus the identity block
# (s15) and status enum. When the schema evolves, this set moves with the grader's checks.
_MIGRATE_REQUIRED = [
    "sow",
    "n",
    "schema_rev",
    "status",
    "created",
    "updated",
    "sow_repo",
    "work_repo",
    "project",
]
# Single source of truth: schemas.common.STATUS_ENUM (shared with migrate).
from .schemas.common import STATUS_ENUM as _STATUS_ENUM_FROZEN  # noqa: E402
from .schemas.common import OPEN_QUESTION_STATUSES  # noqa: E402

_STATUS_ENUM = set(_STATUS_ENUM_FROZEN)


def migrate_check(path):
    """The verifier half of the migration loop: grade a file AS IF it must be a conformant
    schema-14 SOW. Unlike lint_file, a MISSING or unparseable frontmatter is a FAIL with the
    full required-field list (not a SKIP) - that list IS the feedback the LLM loop consumes.
    Returns (status, [feedback-strings]). PASS only when it would pass as a real SOW."""
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return "FAIL", [f"cannot read file: {e}"]
    fm = extract_frontmatter(text)
    if fm is None:
        return "FAIL", ["no frontmatter block at all — add a YAML `---` block with: " + ", ".join(_MIGRATE_REQUIRED)]
    if fm == "MALFORMED" or not isinstance(fm, dict):
        return "FAIL", ["frontmatter is not valid YAML — fix the `---` block so it parses to a mapping"]
    fb = []
    for k in _MIGRATE_REQUIRED:
        if not fm.get(k):
            fb.append(f"missing required field: {k}")
    st = str(fm.get("status", "")).upper().split("-SEE")[0].strip()
    if fm.get("status") and st not in _STATUS_ENUM and not st.startswith("SUPERSEDED"):
        fb.append(f"status '{fm.get('status')}' not in enum: {sorted(_STATUS_ENUM)}")
    # reuse the real grader too — inherits n/schema/project/ledger checks as they evolve
    try:
        _, findings = lint_file(path)
        for f in findings:
            if f.severity == ERROR:
                fb.append(f"{f.code}: {f.message}")
    except Exception:
        pass
    return ("PASS" if not fb else "FAIL"), fb


def migrate_check_render(paths):
    """Grade EVERY path handed in, and say how many.

    PAID (example-stream doctrine): the CLI bound a SCALAR, so --migrate-check p1..p5 graded
    p1 and SILENTLY DROPPED four - one PASS line reading as a green gate over five files.
    A partial grade inside the gate is the count-is-not-a-set error at the one place it must
    never happen. Accepts a str or a list; the summary line names N.
    """
    if isinstance(paths, (str, pathlib.Path)):
        paths = [paths]
    worst = 0
    for path in paths:
        st, fb = migrate_check(path)
        print(f"MIGRATE-CHECK: {st}  {path}")
        for line in fb:
            print(f"  - {line}")
        if st != "PASS":
            worst = 1
    if len(paths) > 1:
        print(f"MIGRATE-CHECK: {len(paths)} path(s) graded")
    return worst


# ── doctrine: the re-sync trigger ────────────────────────────────
# An inherited doctrine file is upstream bytes + a fixed transform, and its banner records
# UPSTREAM-SHA: the sha256 of the upstream file AS DERIVED. Hash upstream now; a mismatch
# means the re-sync duty is DUE (example-org/doctrine). The marker is MACHINE-WRITTEN -
# only the derivation emits it - because a prose phrase could be typed by an author
# (example-org/doctrine A3, paid by a destroyed BOOT-SPARRING).
_UPSTREAM_SHA_RE = re.compile(r"^(?:#|//|/\*|\*|<!--)?\s*UPSTREAM-SHA:\s*([0-9a-f]{64})", re.M)
_DOCTRINE_DIRS = ("claude-md", "roles", "authoring", "intake", "tools")
# "intake" and "tools" ADDED (doctrine / example-stream-CHARTER-03): shared machinery synchronization index.
# doctrine boundary: SHARED MACHINERY (tools/hooks, tools/doctrine, roles, claude-md,
# authoring, intake) vs LOCAL EVIDENCE (tools/stream-instruments, learnings, ruling, projects).


def _is_shared_machinery(rel_path: pathlib.Path) -> bool:
    """True if rel_path belongs to SHARED MACHINERY (cross-repo sync), False for LOCAL EVIDENCE."""
    parts = rel_path.parts
    if not parts or parts[0] not in _DOCTRINE_DIRS:
        return False
    if any(p.startswith(".") for p in parts):
        return False
    if len(parts) >= 2 and parts[0] == "tools" and parts[1] == "stream-instruments":
        return False
    return True


def unwatched_genres(upstream_root, doctrine_dirs=_DOCTRINE_DIRS):
    """example-stream-CHARTER-03 item 6, the part `_DOCTRINE_DIRS` alone cannot solve: a NEW genre
    dir upstream (like `intake/` was, until it got added above) should be VISIBLE to a
    reader even before anyone edits this tuple. This does NOT grade those dirs as
    doctrine (that produced the false-positive flood, see above) - it only NAMES what
    exists upstream and is not currently being checked, so a green resync_check run
    cannot be mistaken for "everything upstream is covered" when it silently is not.
    A GENUINE genre-container (projects/, ruling/, learnings/) will show up here
    too - that is correct and expected, not a defect: this is advisory, read by a human
    deciding whether a name belongs in `_DOCTRINE_DIRS`, not an auto-classifier.
    """
    upstream_root = pathlib.Path(upstream_root)
    out = []
    if upstream_root.is_dir():
        for d in sorted(upstream_root.iterdir()):
            if d.is_dir() and not d.name.startswith(".") and d.name not in doctrine_dirs and any(d.rglob("*.md")):
                out.append(d.name)
    return out


def resync_check(target_root, upstream_root):
    """Compare each inherited file's recorded UPSTREAM-SHA against the upstream file now.

    Returns a list of (relpath, verdict, recorded, current). Verdicts:
      CURRENT          - the recorded hash matches upstream
      STALE            - upstream has moved; re-derive
      SKIP             - a doctrine file with NO marker: locally authored, never re-derived
      MISSING-UPSTREAM - the marker exists but the upstream file does not
      MISSING-TARGET   - file exists upstream in shared machinery but is missing in target
    Pure derivation: every input is a committed byte or a hash of one (doctrine).
    See `unwatched_genres` for the separate, non-grading visibility check on directories
    this function does not walk.
    """
    target_root = pathlib.Path(target_root)
    upstream_root = pathlib.Path(upstream_root)
    rows = []
    seen_rels = set()

    if target_root.is_dir():
        for f in sorted(target_root.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(target_root)
            if not _is_shared_machinery(rel):
                continue
            seen_rels.add(rel)
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            m = _UPSTREAM_SHA_RE.search(text)
            if not m:
                rows.append((str(rel), "SKIP", None, None))
                continue
            recorded = m.group(1)
            up = upstream_root / rel
            if not up.is_file():
                rows.append((str(rel), "MISSING-UPSTREAM", recorded, None))
                continue
            current = hashlib.sha256(up.read_bytes()).hexdigest()
            rows.append(
                (
                    str(rel),
                    "CURRENT" if current == recorded else "STALE",
                    recorded,
                    current,
                )
            )

    if upstream_root.is_dir():
        for f in sorted(upstream_root.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(upstream_root)
            if not _is_shared_machinery(rel):
                continue
            if rel in seen_rels:
                continue
            current = hashlib.sha256(f.read_bytes()).hexdigest()
            rows.append((str(rel), "MISSING-TARGET", None, current))

    rows.sort(key=lambda r: r[0])
    return rows


# Generic layout transforms applied AFTER the absolute-path rewrite when re-deriving.
# Org-specific name remaps (corpus:, sow_repo:, …) live in the target's optional
# tools/doctrine/resync-transforms.toml — never hardcoded to one org.
_LAYOUT_SUBS = [
    ("<project>/sow/", "projects/<project>/sow/"),
    ("<project>/ruling/", "projects/<project>/ruling/"),
    ("<project>/<category>/<task>/", "projects/<project>/<category>/<task>/"),
    ("`sow/<stream>/`", "`projects/<project>/sow/<stream>/`"),
    ("under sow/<stream>/", "under projects/<project>/sow/<stream>/"),
    ("(the sow/<stream>/ dir)", "(the projects/<project>/sow/<stream>/ dir)"),
    ("`<project>/learnings/`", "`learnings/<stream>/`"),
]


def _load_resync_transforms(target_root: pathlib.Path) -> list[tuple[str, str]]:
    """Optional target-local substitutions from tools/doctrine/resync-transforms.toml."""
    path = pathlib.Path(target_root) / "tools" / "doctrine" / "resync-transforms.toml"
    if not path.is_file():
        return []
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return []
    subs = data.get("substitutions") or {}
    if not isinstance(subs, dict):
        return []
    return [(str(k), str(v)) for k, v in subs.items()]


def _inherited_banner(*, upstream_label: str, sha: str, synced: str) -> str:
    return (
        "<!-- ═══ INHERITED DOCTRINE - READ THIS FIRST ═══\n"
        "This document is RE-DERIVED, not authored and not hand-copied, from the UPSTREAM corpus\n"
        f"{upstream_label}: upstream bytes + a fixed transform list (zeo --resync-apply).\n"
        "Re-running the derivation yields the same bytes, so this copy cannot drift by hand.\n"
        "THREE READING RULES, binding on every seat in this repo:\n"
        " 1. A bare RULING-NNN citation inside this inherited text means the UPSTREAM ruling.\n"
        " 2. Named projects/streams in inherited text are UPSTREAM records unless also present here.\n"
        " 3. Local worktree paths and layout references are rewritten by the transform;\n"
        "    everything else is verbatim upstream.\n"
        "RE-SYNC DUTY: when upstream doctrine moves, re-run zeo --resync-apply in ONE commit.\n"
        f"UPSTREAM-SHA below is the check - hash the upstream file; a mismatch means re-sync is due.\n"
        f"UPSTREAM: {upstream_label} · SYNCED: {synced}\n"
        f"UPSTREAM-SHA: {sha}\n"
        "═══ END INHERITED BANNER ═══ -->\n\n"
    )


def _insert_banner(body: str, banner: str) -> str:
    """Place the inherited banner after YAML frontmatter when present, else at the top."""
    if body.startswith("---"):
        try:
            end = body.index("\n---", 3) + 4
            return body[:end] + "\n" + banner + body[end:].lstrip("\n")
        except ValueError:
            pass
    return banner + body


def _git_worktree_dirty(root: pathlib.Path) -> bool:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "status", "--short"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return False
    return out.returncode == 0 and bool(out.stdout.strip())


def resync_apply(
    target_root,
    upstream_root,
    *,
    dry_run: bool = False,
    allow_dirty_upstream: bool = False,
):
    """RE-DERIVE inherited doctrine files from upstream disk.

    For each shared-machinery path present upstream:
      - target exists without UPSTREAM-SHA → SKIP (locally authored; never overwrite)
      - otherwise → upstream bytes + path rewrite + layout/org transforms + banner

    Never commits or pushes. Returns a list of result dicts:
      {path, action: WRITTEN|SKIP|MISSING-UPSTREAM|WOULD-WRITE, sha, subs}.
    """
    target_root = pathlib.Path(target_root).resolve()
    upstream_root = pathlib.Path(upstream_root).resolve()
    if not upstream_root.is_dir():
        raise FileNotFoundError(f"upstream not a directory: {upstream_root}")
    if not allow_dirty_upstream and _git_worktree_dirty(upstream_root):
        raise RuntimeError(
            f"upstream worktree is DIRTY at {upstream_root} — "
            "refuse to re-derive from uncommitted bytes (pass allow_dirty_upstream to override)"
        )

    upstream_label = upstream_root.name
    synced = datetime.date.today().isoformat()
    old_path = str(upstream_root)
    new_path = str(target_root)
    subs: list[tuple[str, str]] = [(old_path, new_path)]
    subs.extend(_LAYOUT_SUBS)
    subs.extend(_load_resync_transforms(target_root))

    # Candidate set: union of upstream shared machinery + target files that already carry
    # a marker (so MISSING-UPSTREAM is still reported if upstream deleted them).
    rels: set[pathlib.Path] = set()
    for root in (upstream_root, target_root):
        if not root.is_dir():
            continue
        for f in root.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(root)
            if _is_shared_machinery(rel):
                rels.add(rel)

    results = []
    for rel in sorted(rels, key=lambda p: str(p)):
        rel_s = str(rel)
        tgt = target_root / rel
        up = upstream_root / rel

        if tgt.is_file():
            try:
                existing = tgt.read_text(encoding="utf-8", errors="replace")
            except OSError:
                existing = ""
            if "UPSTREAM-SHA:" not in existing:
                results.append(
                    {
                        "path": rel_s,
                        "action": "SKIP",
                        "sha": None,
                        "subs": None,
                        "why": "locally authored (no UPSTREAM-SHA)",
                    }
                )
                continue

        if not up.is_file():
            results.append(
                {
                    "path": rel_s,
                    "action": "MISSING-UPSTREAM",
                    "sha": None,
                    "subs": None,
                    "why": "marker or path present in target but missing upstream",
                }
            )
            continue

        src = up.read_text(encoding="utf-8", errors="replace")
        sha = hashlib.sha256(src.encode("utf-8")).hexdigest()
        text = src
        counts = []
        for old, new in subs:
            n = text.count(old)
            if n:
                text = text.replace(old, new)
            counts.append(n)
        # Strip any previous inherited banner block before inserting a fresh one.
        text = re.sub(
            r"<!-- ═══ INHERITED DOCTRINE.*?═══ END INHERITED BANNER ═══ -->\s*",
            "",
            text,
            flags=re.S,
        )
        banner = _inherited_banner(upstream_label=upstream_label, sha=sha, synced=synced)
        text = _insert_banner(text, banner)
        if old_path in text:
            raise RuntimeError(f"{rel_s}: upstream path survived transforms")

        action = "WOULD-WRITE" if dry_run else "WRITTEN"
        if not dry_run:
            tgt.parent.mkdir(parents=True, exist_ok=True)
            tgt.write_text(text, encoding="utf-8")
        results.append({"path": rel_s, "action": action, "sha": sha, "subs": counts, "why": None})

    return results


# ── doctrine: the --promote engine (computation only) ──────
# `n` is a FILENAME property, so it is ASSIGNED by --promote, never derived from a body
# by --migrate. The order is GIT BIRTH ORDER - reproducible, content-addressed, and not a
# judgement call - the same ground --migrate already uses for created:/updated:.


def birth_order(repo_root, paths):
    """Order paths by GIT BIRTH, using COMMIT TOPOLOGY - not timestamps.

    `rev-list --reverse HEAD` gives a total order over commits; each file's birth commit,
    found rename-aware via --follow, maps to a position in it.

    --follow IS LOAD-BEARING and is not optional here: this corpus has been restructured, so
    without it all 313 moved files report the RESTRUCTURE commit as their birth, tie in one
    commit, and collapse to alphabetical - the exact failure this function exists to kill.
    (migrate.py:98 states the same for created:.)

    KNOWN HAZARD, measured at diag: --follow uses rename DETECTION, so two files with
    IDENTICAL content can be mislinked - git reports the elder's birth for both. Real SOWs
    differ, but a test fixture writing the same bytes into every file will manufacture this
    and look like an ordering bug. It is a property of --follow, not of this function.

    Files added in the SAME commit have NO birth order - git records none. Their tie-break
    is the filename, and that is DECLARED here rather than emerging by accident.
    An untracked path scores 0, sorts first, and is visible to the caller: assigning n to a
    file git has never seen would be an identity from no evidence.
    """
    rl = subprocess.run(
        ["git", "-C", str(repo_root), "rev-list", "--reverse", "HEAD"],
        capture_output=True,
        text=True,
    )
    position = {sha: i + 1 for i, sha in enumerate(rl.stdout.split())}
    scored = []
    for p in paths:
        rel = str(p)
        r = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "log",
                "--follow",
                "--diff-filter=A",
                "--format=%H",
                "--",
                rel,
            ],
            capture_output=True,
            text=True,
        )
        shas = [l for l in r.stdout.split() if l]
        scored.append((position.get(shas[-1], 0) if shas else 0, rel))
    scored.sort(key=lambda x: (x[0], x[1]))
    return [rel for _, rel in scored]


def assign_n(ordered_paths, start=1):
    """1-based n in birth order. Rev-pairs get DISTINCT n because they are distinct
    filings under append-don't-revert - which is why doctrine's collisions largely
    dissolve rather than needing resolution."""
    return {p: i for i, p in enumerate(ordered_paths, start=start)}


_SLUG_STRIP = re.compile(r"(?i)[-_]?rev[-_]?[0-9a-z]+$")


def canonical_name(sow, n, slug):
    """<sow>-SOW-<n>-<slug>.md with zero-padded n.

    The rev suffix is STRIPPED: rev lives in frontmatter, never in the name (CLAUDE.md s5).
    """
    slug = _SLUG_STRIP.sub("", str(slug).strip("-_ ")) or "sow"
    return f"{sow}-SOW-{int(n):02d}-{slug}.md"


def collisions(target_map):
    """{source: target} -> {target: [sources]} for every target claimed more than once.

    --promote REFUSES on any collision and never resolves one: a naive rename would
    OVERWRITE LANDED HISTORY, and this corpus is append-don't-revert (doctrine).
    """
    seen = {}
    for src, tgt in target_map.items():
        seen.setdefault(tgt, []).append(src)
    return {t: sorted(s) for t, s in seen.items() if len(s) > 1}


def predecessor_map(ordered_paths):
    """file -> the file immediately BEFORE it in birth order; `none` for the genesis.

    NOT `supersedes`: C's predecessor is B even when C supersedes A. Its value is that a
    named-but-ABSENT predecessor is detectable - git cannot miss a file it never saw, which
    is how doctrine lost (doctrine).
    """
    out = {}
    prev = None
    for p in ordered_paths:
        out[p] = prev if prev is not None else "none"
        prev = p
    return out


_SOW_N_IN_NAME = re.compile(r"(?i)sow[-_]?0*(\d+)")
# Names that MARK a non-SOW genre (doctrine). Evidence to EXCLUDE - never a
# requirement to include: an unmarked file is planned and the operator judges it.
_NON_SOW_NAME = re.compile(r"(?i)^(charter|ruling|learnings|readme|sparring|master-to|boot)[-_.]")
_SLUG_LEAD = re.compile(r"(?i)^(sow[-_]?)?([a-z0-9]+[-_])*?sow[-_]?[0-9]*[-_]?")
_SLUG_CLEAN = re.compile(r"[^a-z0-9]+")


def slug_from(old_name):
    """Propose a canonical slug from a legacy filename. DRY-RUN territory: this is a
    heuristic, and the whole point of a plan is that a bad slug is visible before a rename
    rather than after 313 of them."""
    stem = pathlib.Path(old_name).stem
    stem = _SLUG_STRIP.sub("", stem)  # trailing -RevN / -rev-b
    stem = _SLUG_LEAD.sub("", stem)  # leading SOW- / <STREAM>-SOW-<n>-
    stem = _SLUG_CLEAN.sub("-", stem.lower()).strip("-")
    return stem or "sow"


def promote_plan(repo_root, stream_dir, sow_id=None):
    """Compute the rename plan for one stream dir. COMPUTES ONLY - nothing is written.

    Returns {'rows': [...], 'collisions': {...}, 'untracked': [...]}, where each row is
    {'src','target','n','predecessor','corpus'}. doctrine: n is assigned by --promote in
    git birth order (s3); a collision is REFUSED and never resolved (s4); predecessor and
    corpus ride the same birth-order pass at no extra cost (s6).
    """
    # PAID (GM-example-stream-166): invoked as `--promote example-project/sow/repo-hygiene` - a RELATIVE
    # path, the normal way - stream_dir stayed relative while repo_root became absolute
    # after the corpus-root fix, and relative_to raised. tmp_path fixtures are ALWAYS
    # absolute, so no test could see it. Resolve at the boundary, once.
    repo_root = pathlib.Path(repo_root).resolve()
    stream_dir = pathlib.Path(stream_dir).resolve()
    files = sorted(f for f in stream_dir.glob("*.md") if f.is_file())
    # EXCLUDE non-SOW genres. A charter ASSIGNS and a SOW RECORDS (doctrine); renaming a
    # charter into <sow>-SOW-<n> makes it masquerade as a SOW and consumes an n. The first
    # live plan did exactly that to guide-sweep's charter and shifted every real SOW by one.
    kept, excluded = [], []
    for f in files:
        fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        genre = str(fm.get("genre", "")).strip().lower() if isinstance(fm, dict) else ""
        # EXCLUSION REQUIRES EVIDENCE; inclusion is the default. The first cut demanded
        # positive proof of SOW-ness and silently dropped every unmarked file - and a
        # migration that drops files without printing them is worse than one that includes
        # an ambiguous file, because the dry run exists so a human can judge exactly those.
        if genre and genre != "sow":
            excluded.append({"file": str(f.relative_to(repo_root)), "why": f"genre: {genre}"})
        elif not genre and _NON_SOW_NAME.match(f.name):
            excluded.append(
                {
                    "file": str(f.relative_to(repo_root)),
                    "why": "filename marks a non-SOW genre",
                }
            )
        else:
            kept.append(f)
    rel = [str(f.relative_to(repo_root)) for f in kept]
    ordered = birth_order(repo_root, rel)
    # PRESERVE a declared n. doctrine assigns n because 313 files never carried one -
    # it does NOT license renumbering a file that already has one, and a rename breaks every
    # citation pointing at the old name (doctrine). Assign only into the gaps.
    declared, undeclared = {}, []
    for r in ordered:
        fm = extract_frontmatter((repo_root / r).read_text(encoding="utf-8", errors="replace"))
        n = fm.get("n") if isinstance(fm, dict) else None
        if n is None:
            m = _SOW_N_IN_NAME.search(pathlib.Path(r).name)
            n = m.group(1) if m else None
        try:
            declared[r] = int(n)
        except (TypeError, ValueError):
            undeclared.append(r)
    # A declared n is preserved ONLY IF IT IS UNIQUE in this dir. MEASURED: the legacy
    # -RevN family put the revision in the FILENAME and left n static - 22 repo-hygiene
    # files all declare n:1 - so preserving the declaration would preserve the collision,
    # and n-collision is the corpus's largest failure class (77 findings). A colliding
    # GROUP is reassigned wholesale in birth order; a unique n is still never touched,
    # because renumbering a validly-numbered file breaks citations (doctrine).
    counts = {}
    for r, n in declared.items():
        counts[n] = counts.get(n, 0) + 1
    unique = {r: n for r, n in declared.items() if counts[n] == 1}
    colliding = [r for r, n in declared.items() if counts[n] > 1]
    nxt = max(unique.values(), default=0) + 1
    ns = dict(unique)
    for r in ordered:  # birth order, so the eldest keeps the lowest n
        if r in colliding or r in undeclared:
            ns[r] = nxt
            nxt += 1
    preds = predecessor_map(ordered)
    # PAID (GM-example-stream-165): the first live rename wrote `corpus: repo-hygiene` because the CLI
    # handed promote_plan the STREAM DIR as its root - the same wrong-root defect already
    # fixed for the citation scan. Resolve the corpus explicitly, and fall back only if the
    # marker is absent.
    corpus = (corpus_root(stream_dir) or repo_root).resolve().name
    # PAID (same run): sow_id defaulted to the DIRECTORY NAME, so the plan proposed
    # `repo-hygiene-doctrine-...` for a stream whose frontmatter says
    # `sow: example-project-repo-hygiene` - the rename CLEARED one finding and CREATED another
    # ([n-stream]). The stream id is a FRONTMATTER fact; the directory is not authoritative.
    if not sow_id:
        declared_sows = []
        for f in kept:
            fmx = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
            if isinstance(fmx, dict) and fmx.get("sow"):
                declared_sows.append(str(fmx["sow"]).strip())
        sow_id = max(set(declared_sows), key=declared_sows.count) if declared_sows else None
    sow = sow_id or stream_dir.name
    rows, targets, final_name = [], {}, {}
    for r in ordered:
        name = pathlib.Path(r).name
        tgt = canonical_name(sow, ns[r], slug_from(name))
        if needs_rename(name, ns.get(r))[0]:
            targets[r] = tgt  # only a file being RENAMED can collide
        need, why = needs_rename(name, ns.get(r))
        final_name[r] = tgt if need else name
        rows.append(
            {
                "src": r,
                "target": tgt if need else name,
                "n": ns[r],
                "predecessor": preds[r],
                "corpus": corpus,
                "rename": need,
                "why": why,
            }
        )
    # PAID (GM-example-stream-168): predecessor named the PRE-RENAME PATH. After a full promote every
    # link would point at a file that no longer exists - legacy_name keeps it grep-resolvable,
    # but a chain whose links name vanished files is not a chain. Point at the predecessor's
    # FINAL name (its target if renamed, else its current name), as a BASENAME - the same
    # granularity as legacy_name.
    for row in rows:
        pred = row["predecessor"]
        row["predecessor"] = "none" if pred == "none" else pathlib.Path(final_name.get(pred, pred)).name
    untracked = [
        r
        for r in ordered
        if not subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "--error-unmatch", r],
            capture_output=True,
        ).returncode
        == 0
    ]
    return {
        "rows": rows,
        "collisions": collisions(targets),
        "untracked": untracked,
        "excluded": excluded,
        "assigned": sorted(set(undeclared) | set(colliding)),
        "preserved": sorted(unique),
        "collided": sorted(colliding),
    }


def needs_rename(name, declared_n, sow_id=None):
    """Does the GRADER reject this filename? Only then is a rename earned.

    MEASURED: renaming guide-sweep's six already-numbered SOWs would rewrite 8 references
    in 6 files - STATE.md (generated), two landed rulings' `requested_by` (an IMMUTABLE
    field, doctrine's mutable-field spec), another landed ruling, and a landed SOW
    (append-don't-revert, s5). Those rewrites are FORBIDDEN, not merely expensive, and
    doctrine's `legacy_name:` exists so an old citation stays resolvable without them.
    So a file whose name already satisfies <sow>-SOW-<n>-<slug>.md, with the n agreeing,
    KEEPS ITS NAME - cosmetic conformance does not justify touching a landed record.
    """
    m = _SOW_FILE_RE.match(name)
    if not m:
        return True, "filename does not match <sow>-SOW-<n>-<slug>.md"
    if _REVSUFFIX_RE.search(m.group("slug")):
        return True, "slug carries a -RevN suffix (rev lives in frontmatter)"
    try:
        if declared_n is not None and int(declared_n) != int(m.group("n")):
            return (
                True,
                f"filename n={m.group('n')} disagrees with declared n={declared_n}",
            )
    except (TypeError, ValueError):
        return True, "n is not an integer"
    return False, "already grades - kept"


def project_repair_plan(root):
    """The `project:` CHECKSUM disagreements, classified by whether they are safely mechanical.

    project: is B1's checksum on the PHYSICAL project axis and the PATH IS GROUND (s15). But a
    disagreement has TWO causes and conflating them would paper over a structural error:

      REPAIR   - frontmatter names something that is NOT a project in this corpus (a stream id,
                 typically). The field is wrong, the file is where it belongs. Mechanical.
      ESCALATE - frontmatter names a REAL but DIFFERENT project. Either the file is MISPLACED or
                 the field is wrong, and a tool cannot tell which. Reported, never rewritten.

    Also reports the `project:`-MISSING residue WITH ITS REASON, so a second pass is not a
    blind retry of whatever failed the first.
    """
    root = pathlib.Path(root).resolve()
    known = {r.parent.name for r in find_sow_roots(root)}
    repair, escalate, missing = [], [], []
    for f in sorted(root.rglob("*.md")):
        rel = str(f.relative_to(root))
        if "/sow/" not in "/" + rel or rel.startswith("_legacy"):
            continue
        fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(fm, dict):
            continue
        derived = project_of(str(f), root)
        declared = str(fm.get("project", "")).strip()
        if not fm.get("sow"):
            continue
        if not declared:
            missing.append(
                {
                    "file": rel,
                    "derived": derived,
                    "why": "path yields no project" if not derived else "field absent",
                }
            )
            continue
        if derived and declared != derived:
            row = {"file": rel, "declared": declared, "derived": derived}
            if declared in known:
                row["why"] = (
                    f"'{declared}' IS a real project - the FILE may be misplaced. "
                    f"A tool cannot tell which side is wrong."
                )
                escalate.append(row)
            else:
                row["why"] = f"'{declared}' is not a project in this corpus (a stream id?)"
                repair.append(row)
    return {
        "repair": repair,
        "escalate": escalate,
        "missing": missing,
        "known_projects": sorted(known),
    }


def project_backfill_plan(root):
    """Files declaring `sow:` but missing `project:`, with the value DERIVED FROM THE PATH.

    guide-sweep's doctrine the grader on [project-missing] - not on its filename. So
    the fix is a FIELD, not a rename: no model (the value is computed, not synthesised),
    no rename, and no citation breakage. project_of() already derives it from
    <project>/sow/<stream>/ (its own ground, per s15's path-over-frontmatter rule).

    Returns [{'file','project','sow'}] for files that can be repaired, and a separate
    'unresolved' list for files whose path yields no project - those are NOT guessed.
    """
    root = pathlib.Path(root).resolve()
    rows, unresolved = [], []
    for f in sorted(root.rglob("*.md")):
        rel = str(f.relative_to(root))
        if "/sow/" not in "/" + rel or rel.startswith("_legacy"):
            continue
        fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(fm, dict) or not fm.get("sow"):
            continue  # Class-A / non-SOW: --migrate's job, not this one
        if fm.get("project"):
            continue
        proj = project_of(str(f), root)
        if proj:
            rows.append({"file": rel, "project": proj, "sow": str(fm.get("sow"))})
        else:
            unresolved.append({"file": rel, "why": "path yields no project - not guessed"})
    return {"rows": rows, "unresolved": unresolved}


def project_backfill_apply(root, rows, limit=None):
    """Insert `project: <derived>` into frontmatter. The FIRST mutation of this tool, so:

    - ONE line is added, immediately after the `sow:` line (a stable, present anchor).
    - The BODY is byte-identical afterwards - asserted, not assumed.
    - The result is PARSE-VERIFIED as YAML before the write (doctrine).
    - Idempotent: a file that already has `project:` is skipped, so a double-run is safe
      (s4 refuse-or-idempot - operator double-runs happen).
    - It does NOT commit. The operator reads the diff; a tool that commits its own
      mutation removes the only human check this relay has.
    """
    root = pathlib.Path(root).resolve()
    done, skipped, failed = [], [], []
    for row in rows[:limit] if limit else rows:
        f = root / row["file"]
        text = f.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines(keepends=True)
        if any(l.startswith("project:") for l in lines):
            skipped.append({"file": row["file"], "why": "already has project:"})
            continue
        idx = [k for k, l in enumerate(lines) if l.startswith("sow:")]
        if len(idx) != 1:
            failed.append(
                {
                    "file": row["file"],
                    "why": f"expected 1 `sow:` line, found {len(idx)}",
                }
            )
            continue
        out = lines[: idx[0] + 1] + [f"project: {row['project']}\n"] + lines[idx[0] + 1 :]
        candidate = "".join(out)
        try:
            fm = extract_frontmatter(candidate)
            assert isinstance(fm, dict) and fm.get("project") == row["project"]
        except Exception as e:
            failed.append({"file": row["file"], "why": f"parse-verify failed: {e}"})
            continue
        body_before = text.split("---", 2)[-1]
        body_after = candidate.split("---", 2)[-1]
        if body_before != body_after:
            failed.append({"file": row["file"], "why": "BODY CHANGED - refusing to write"})
            continue
        f.write_text(candidate, encoding="utf-8")
        done.append(row["file"])
    return {"written": done, "skipped": skipped, "failed": failed}


def _set_or_insert(lines, key, value, after_keys):
    """Set `key: value` in a frontmatter line list; insert after the first of after_keys."""
    for k, l in enumerate(lines):
        if l.startswith(f"{key}:"):
            lines[k] = f"{key}: {value}\n"
            return lines
    for anchor in after_keys:
        idx = [k for k, l in enumerate(lines) if l.startswith(f"{anchor}:")]
        if idx:
            lines.insert(idx[0] + 1, f"{key}: {value}\n")
            return lines
    lines.insert(1, f"{key}: {value}\n")
    return lines


def promote_apply(root, rows, limit=None):
    """Rename via GIT MV and write the four computed fields. Mutating, so:

    - `git mv` (not os.rename) so --follow keeps the file's BIRTH - the whole ordering
      ground depends on it (birth_order's docstring). CAVEAT, measured: --follow uses
      rename DETECTION, so a rename plus a large-relative-to-size content edit in ONE
      commit can fail to link. Real SOWs are long enough that four added lines are noise;
      for safety the rename and the field writes can be committed SEPARATELY.
    - `legacy_name:` records the old name, which is why citations are NOT rewritten:
      they live in landed rulings' `requested_by` - IMMUTABLE under doctrine - and in
      append-only SOWs. doctrine made legacy_name the bridge precisely here.
    - body byte-identical, frontmatter parse-verified before the write.
    - idempotent: a row already at its target is skipped.
    - it does NOT commit.
    """
    root = pathlib.Path(root).resolve()
    done, skipped, failed = [], [], []
    for row in rows[:limit] if limit else rows:
        src = root / row["src"]
        tgt = src.parent / row["target"]
        if not row.get("rename"):
            skipped.append({"file": row["src"], "why": "name already grades"})
            continue
        if tgt.exists() and tgt != src:
            failed.append({"file": row["src"], "why": f"target exists: {row['target']}"})
            continue
        text = src.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            failed.append({"file": row["src"], "why": "no frontmatter block to update"})
            continue
        end = text.index("\n---", 3) + 1
        head, body = text[:end], text[end:]
        lines = head.splitlines(keepends=True)
        _set_or_insert(lines, "n", row["n"], ["sow"])
        _set_or_insert(lines, "corpus", row["corpus"], ["project", "sow"])
        _set_or_insert(lines, "predecessor", row["predecessor"], ["n", "sow"])
        _set_or_insert(lines, "legacy_name", src.name, ["predecessor", "n", "sow"])
        candidate = "".join(lines) + body
        try:
            fm = extract_frontmatter(candidate)
            assert isinstance(fm, dict) and str(fm.get("legacy_name")) == src.name
        except Exception as e:
            failed.append({"file": row["src"], "why": f"parse-verify failed: {e}"})
            continue
        if candidate[candidate.index("\n---", 3) :] != text[text.index("\n---", 3) :]:
            failed.append({"file": row["src"], "why": "BODY CHANGED - refusing"})
            continue
        r = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "mv",
                row["src"],
                str(pathlib.Path(row["src"]).parent / row["target"]),
            ],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            failed.append({"file": row["src"], "why": f"git mv failed: {r.stderr.strip()}"})
            continue
        tgt.write_text(candidate, encoding="utf-8")
        done.append({"from": row["src"], "to": row["target"], "n": row["n"]})
    return {"renamed": done, "skipped": skipped, "failed": failed}


def corpus_root(start):
    """Walk UP from any path to the corpus root (the claude-md/CLAUDE.md marker).

    PAID: --promote passed the STREAM DIR as the citation-scan root, so the scan searched
    the six files being renamed and reported "2 references in 1 file" while a ruling in
    example-project/ruling/ cited one of them. The tell was in the output - the hit printed with
    no directory prefix - which is why the scan now prints the root it searched.
    """
    p = pathlib.Path(start).resolve()
    for cand in [p, *p.parents]:
        if (cand / "claude-md" / "CLAUDE.md").is_file():
            return cand
    return None


def citation_scan(root, rename_map, skip=()):
    """Every reference in the corpus to a file a rename would move. READ-ONLY.

    NO MODEL IS INVOLVED, and that boundary is worth stating: --migrate needs a claimant
    because it SYNTHESISES fields from prose (what is this SOW's status? its lifecycle?).
    A rename synthesises nothing - it rewrites strings. doctrine says a rename breaks
    every citation pointing at the old name; this finds them so the cost is a NUMBER before
    it is a decision.

    rename_map: {old_basename: new_basename}. Returns
      {file_rel: [{'old','new','with_ext','stem_only'}]}
    counting the full basename and the extension-less stem separately, because citations
    appear both ways and the stem match is the looser of the two.
    """
    root = pathlib.Path(root).resolve()
    stems = {old: (pathlib.Path(old).stem, pathlib.Path(new).stem) for old, new in rename_map.items()}
    hits = {}
    for f in sorted(root.rglob("*.md")):
        rel = str(f.relative_to(root))
        if any(rel.startswith(s) for s in skip):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        found = []
        for old, new in rename_map.items():
            old_stem, _ = stems[old]
            with_ext = text.count(old)
            stem_only = text.count(old_stem) - with_ext  # stem hits NOT part of a full name
            if with_ext or stem_only:
                found.append(
                    {
                        "old": old,
                        "new": new,
                        "with_ext": with_ext,
                        "stem_only": max(stem_only, 0),
                    }
                )
        if found:
            hits[rel] = found
    return hits


def citation_totals(hits):
    """(files_touched, references) - the two numbers a rename-scope decision needs."""
    refs = sum(h["with_ext"] + h["stem_only"] for v in hits.values() for h in v)
    return len(hits), refs


def iter_sow_files(root: pathlib.Path):
    root = pathlib.Path(root)
    if root.is_file():
        yield root
    else:
        yield from sorted(root.rglob("*.md"))


# ── V1-A: project axis derivation (Option 1-via-3, doctrine) ──────────
def project_of(path, root=None) -> "str | None":
    """The project a SOW belongs to, derived from its PATH (ground, not frontmatter).

    Canonical shape (post-migration):  <project>/sow/<task>/<file>.md  -> <project>
    Flat-legacy shape (pre-migration):  sow/<task>/<file>.md           -> None

    `root`, when given (the walk root), is stripped first so classification is
    root-relative — an ABSOLUTE flat-legacy path must not mistake the repo dir for
    a project. None on a flat-legacy file is deliberate: legacy files have no project
    axis yet, and B1 WARNs-to-backfill on them rather than inventing one (consistent
    with check_n's era-gating — legacy is grandfathered, never invented).

    Path-based and space-safe by construction (pathlib parts, no shell).
    """
    # doctrine (example-org) / the example-org restructure: a corpus may nest its
    # projects under a `projects/` container. MEASURED at diag: without this,
    # the board reports `0 projects` and EVERY file falls into the flat-legacy
    # branch - so n-collision silently reverts to filename-prefix grouping and the
    # project-scoped checks change meaning while the failure COUNT stays the same.
    # Strip the container so `projects/<project>/sow/` reads as `<project>/sow/`.
    _p = pathlib.Path(path)
    _parts = _p.parts
    if "projects" in _parts:
        _i = _parts.index("projects")
        if _i + 1 < len(_parts):
            path = str(pathlib.Path(*_parts[_i + 1 :]))
            root = None
    p = pathlib.Path(path)
    if root is not None:
        try:
            p = p.relative_to(root)
        except ValueError:
            pass
    parts = p.parts
    for i, seg in enumerate(parts):
        if seg == "sow":
            return parts[i - 1] if i >= 1 else None
    return None


# ── V1-B: B1 project: checksum on the physical axis (era-aware like check_n) ──
def check_project(path, fm, root=None) -> list[Finding]:
    """B1: `project:` frontmatter is the CHECKSUM on the physical project axis.
    Era-aware, mirroring check_n:
    - canonical shape (project_of non-None):
        project: present & agrees with parent dir -> OK
        present & disagrees -> ERROR project-mismatch (the misfile B1 exists to catch)
        absent -> ERROR project-missing (B1 mandatory in canonical shape)
    - flat-legacy (project_of None, pre-migration):
        absent -> WARN project-backfill (add identity BEFORE bytes move; NEVER ERROR)
        present -> OK (early-backfilled per B1; no dir to verify against, accept)
    """
    out: list[Finding] = []
    dir_project = project_of(path, root)
    declared = fm.get("project")
    declared = str(declared).strip() if declared is not None else None
    if dir_project is not None:
        if declared is None:
            out.append(
                Finding(
                    ERROR,
                    "project-missing",
                    f"canonical-shape SOW under '{dir_project}/sow/' has no `project:` (B1 mandatory)",
                )
            )
        elif declared != dir_project:
            out.append(
                Finding(
                    ERROR,
                    "project-mismatch",
                    f"project:'{declared}' != parent dir '{dir_project}' (B1 checksum disagreement)",
                )
            )
    else:
        if declared is None:
            out.append(
                Finding(
                    WARN,
                    "project-backfill",
                    "flat-legacy SOW has no `project:` — backfill before migration (B1 early identity)",
                )
            )
    return out


# ── V1-C: B2 grandfather-manifest enforcement (dated boundary, per-project armed) ──
import datetime as _dt


def resolve_manifest_path(root=None) -> pathlib.Path:
    """Prefer corpus-local / env override; fall back to the packaged empty default."""
    env = os.environ.get("ZEO_GRANDFATHER_MANIFEST")
    if env:
        p = pathlib.Path(env)
        if p.is_file():
            return p
    if root is not None:
        cand = pathlib.Path(root) / _CORPUS_MANIFEST_REL
        if cand.is_file():
            return cand
    return _MANIFEST_PATH


def load_manifest(manifest_path=None, root=None) -> "dict | None":
    """Read the B2 boundary DATA. Fails SAFE: an unreadable/malformed manifest
    returns None so check_b2 WARN-skips rather than red the corpus. Never raises.

    Packaged default has empty [areas] (public wheel). Private corpora supply a real
    manifest via ZEO_GRANDFATHER_MANIFEST or tools/doctrine/grandfather_manifest.toml.
    """
    path = pathlib.Path(manifest_path) if manifest_path else resolve_manifest_path(root)
    try:
        raw = path.read_text(encoding="utf-8")
        data = tomllib.loads(raw)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    if not isinstance(data, dict) or "freeze_date" not in data:
        return None
    return data


def parse_created(fm) -> "_dt.date | None":
    """Parse frontmatter created: to a date. None if missing/unparseable (-> WARN,
    never crash). yaml may already yield a date; accept both date and ISO string."""
    raw = fm.get("created")
    if raw is None:
        return None
    if isinstance(raw, _dt.date):
        return raw
    try:
        return _dt.date.fromisoformat(str(raw).strip())
    except (ValueError, TypeError):
        return None


def check_b2(path, fm, root=None, manifest=None) -> list[Finding]:
    """B2: after the frozen boundary, a NEW file (created > freeze_date) filed
    OUTSIDE canonical shape is enforced PER-PROJECT. Arms only when the target
    project has migrated (its <target>/sow/ exists on disk — doctrine B,
    ratified doctrine: disk is the ground, not a flag that can lie).
      - canonical-shape file (project_of non-None) -> pass (B2 governs OUTSIDE it)
      - flat-legacy + created <= freeze -> pass (grandfathered existing bytes)
      - flat-legacy + created > freeze + target migrated -> ERROR (file canonical)
      - flat-legacy + created > freeze + target unmigrated/OPEN/'' -> WARN (nudge)
      - missing/unparseable created (new file outside shape) -> WARN (can't grade)
      - manifest unreadable -> [] (load_manifest already failed safe; skip B2)
    """
    out: list[Finding] = []
    man = manifest if manifest is not None else load_manifest(root=root)
    if man is None:
        return out  # boundary unreadable -> skip B2, never red the corpus
    # canonical-shape files are not B2's concern (B2 governs files OUTSIDE canonical)
    if project_of(path, root) is not None:
        return out
    # flat-legacy from here down
    try:
        freeze = _dt.date.fromisoformat(str(man.get("freeze_date")).strip())
    except (ValueError, TypeError):
        return out  # malformed freeze_date -> fail safe, skip
    created = parse_created(fm)
    name = pathlib.Path(path).name
    if created is None:
        out.append(
            Finding(
                WARN,
                "b2-undated",
                f"'{name}' has no parseable created: — cannot grade against B2 freeze "
                f"{freeze.isoformat()}; backfill created:",
            )
        )
        return out
    if created <= freeze:
        return out  # grandfathered existing bytes
    # created > freeze: a NEW flat file. Arm per-project on the target's migration.
    top = pathlib.Path(path)
    if root is not None:
        try:
            top = top.relative_to(root)
        except ValueError:
            pass
    area = top.parts[0] if top.parts else ""
    target = man.get("areas", {}).get(area)
    armed = (
        bool(target)
        and target != "OPEN"
        and (
            (pathlib.Path(root) / target / "sow").is_dir() if root is not None else pathlib.Path(target, "sow").is_dir()
        )
    )
    if armed:
        out.append(
            Finding(
                ERROR,
                "b2-postfreeze",
                f"'{name}' created {created.isoformat()} > freeze {freeze.isoformat()} "
                f"and is outside canonical shape, but project '{target}' has migrated — "
                f"file it under {target}/sow/<task>/ (B2)",
            )
        )
    else:
        out.append(
            Finding(
                WARN,
                "b2-premigration",
                f"'{name}' created {created.isoformat()} > freeze {freeze.isoformat()} "
                f"outside canonical shape; target project unmigrated or unresolved — "
                f"WARN-to-backfill until it migrates (B2 disarmed pre-migration)",
            )
        )
    return out


# -- V2: genre discriminator + ruling keystone (doctrine, example-stream doctrine) --
_RULING_NAME_RE = re.compile(r"^RULING-(\d{3})-")
# "charter" REMOVED (example-stream-CHARTER-03 item 2, doctrine): graded via check_charter.
# "learnings" REMOVED (pydantic lint big bang): graded via schemas.grade_learnings.
# relay remains deliberate SKIP (coordination traffic, not a claim genre).
_SKIP_GENRES = ("relay",)


def discriminate(path, fm) -> str:
    # The genre of an artifact (doctrine): sow | ruling | learnings | relay.
    # Explicit genre: WINS (inference fails on the live corpus - doctrine).
    # Fallback keys on FILENAME shape, never on directory: ruling/ holds 7
    # non-rulings (directives, cosigns, landing-notes, a lexicon) - doctrine
    g = fm.get("genre")
    if g and str(g).strip():
        return str(g).strip().lower()
    p = pathlib.Path(path)
    if _RULING_NAME_RE.match(p.name):
        return "ruling"
    parts = [x.lower() for x in p.parts]
    if "learnings" in parts:
        return "learnings"
    if "ruling" in parts:
        return "relay"
    return "sow"


_OPERATOR_FORMS = (
    "operator directive",
    "operator eye",
    "operator ruling",
    "operator-briefed",
)


def _split_requesters(rb):
    # A PAREN-AWARE comma split: a stated reason legitimately contains a comma
    # ("path.md (pre-schema, no n: yet)"), and a naive rb.split(",") shatters it into
    # two fragments exactly like the diag/228 prose-shatter bug this function's
    # caller already guards against. Split on "," only at paren-depth 0.
    parts, depth, cur = [], 0, []
    for ch in rb:
        if ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


_STREAM_N_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_-]*)#(\d+)$")
_PATH_WITH_REASON_RE = re.compile(r"^([A-Za-z0-9_./-]+\.md)(?:\s*\((.+)\))?$")
# RULING-268 s1: <stream>#<n>#<question-id> extends the already-ruled <stream>#<n> form
# (RULING-214 s3) one level finer, not a new scheme. question-id is "kebab-ish" per the
# ruling's own worked example (q1-seat) — word chars plus hyphens, no further punctuation.
_STREAM_N_QID_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_-]*)#(\d+)#([A-Za-z0-9][A-Za-z0-9_-]*)$")


def check_requested_by(fm, raw_text, known_stems, sow_index=None):
    # doctrine (Master, superseding doctrine A1's FORWARD-BINDING clause only —
    # A1's body, its historic disposal, and A2 stand). `requested_by` names `<stream>#<n>`
    # going forward: the stream id and the SOW's identity number, NEITHER of which moves
    # under a `--promote` slug sharpening or the projects/ restructure. MEASURED: only 7 of
    # 19 sampled ghosts were the restructure the old rule blamed; 11 were slug drift from a
    # stream sharpening its OWN title exactly as it was told to (doctrine/201/205 among
    # them — filed AFTER the restructure, voided by the asking stream's own rename).
    # `operator directive <date>` (doctrine A1) is UNCHANGED and fully legal, silent.
    # A bare path STAYS legal, but ONLY with a stated reason its target has no `n:` yet
    # (607 of 898 corpus files still carry no (sow,n) pair — the pre/Class-A residue); an
    # UNEXPLAINED path is now a WARN, not a silent pass — the explanation is what makes the
    # residue COUNTABLE (the migration's burn-down meter).
    # `sow_index`: {(stream_id, n): (path, fm)}, built ONCE corpus-wide and passed in — see
    # build_sow_n_index. None is accepted (a ghost on every stream#n token) so a caller that
    # hasn't been updated yet still runs, just blind to the new form.
    #
    # THE SHATTER GUARD, PRESERVED FROM A1 (diag/228): a naive `rb.split(",")` on
    # "sow/editorial-recon/ (rev-p, RULING-REQUESTED F1/F2/F3) + operator directive ..."
    # shatters the parenthetical's OWN internal comma into a phantom fragment. The fix is
    # unchanged in shape: classify EVERY split fragment first: only if ALL of them look like
    # a clean stream#n or path(+reason) token do we resolve them individually; the instant
    # ONE fragment doesn't, the WHOLE original string is judged as one legacy/operator blob,
    # never split. Fail closed toward "I cannot parse this", never "this is a ghost".
    rb = str(fm.get("requested_by", "") or "").strip()
    if not rb:
        return []
    entries = _split_requesters(rb)

    def _conformant(e):
        return bool(_STREAM_N_RE.match(e) or _PATH_WITH_REASON_RE.match(e))

    if not all(_conformant(e) for e in entries):
        if any(f in rb.lower() for f in _OPERATOR_FORMS):
            return []  # operator form is fully legal (A1) - silent
        return [
            Finding(
                WARN,
                "requested_by-legacy",
                "requested_by is not in a gradeable form (<stream>#<n>, a path[+stated reason], "
                "comma-separated, or an operator form) - the board closes it by STEM-tolerant "
                "match where the basename resolves, else it needs a closure mapping (doctrine "
                "A1 / doctrine). Not a ghost; a pre-conformant form",
            )
        ]
    out = []
    for e in entries:
        m = _STREAM_N_RE.match(e)
        if m:
            key = (m.group(1), int(m.group(2)))
            if sow_index is not None and key in sow_index:
                continue  # resolves cleanly - silent
            out.append(
                Finding(
                    WARN,
                    "requested_by-ghost-stream-n",
                    f"requested_by names '{e}' - no SOW on disk declares sow: {m.group(1)} at "
                    f"n: {m.group(2)} (doctrine chimera class, stream#n form). Verify the "
                    "stream id and n, or check stream-index.md for the id",
                )
            )
            continue
        m2 = _PATH_WITH_REASON_RE.match(e)
        path_part, reason = m2.group(1), m2.group(2)
        stem = pathlib.Path(path_part).stem
        if stem not in known_stems:
            out.append(
                Finding(
                    WARN,
                    "requested_by-ghost",
                    f"requested_by names '{pathlib.Path(path_part).name}' - a clean path whose "
                    "basename matches NO SOW on disk: a chimera citation (the doctrine class). "
                    "A stream renders OPEN forever or a false ANSWERED fires. Verify the filename",
                )
            )
        elif not reason:
            out.append(
                Finding(
                    WARN,
                    "requested_by-unexplained-path",
                    f"requested_by names '{pathlib.Path(path_part).name}' as a bare path with no "
                    "stated reason its target lacks n: - doctrine supersedes doctrine A1's "
                    "exact-path rule. Use <stream>#<n> if the target has one, else state why it "
                    "doesn't (e.g. 'path.md (pre-schema, no n: yet)')",
                )
            )
        # else: clean path + a stated reason - fully legal, silent.
    return out


def build_sow_n_index(root):
    """doctrine's resolver: {(stream_id, n): (path, fm)}, built ONCE corpus-wide so
    `<stream>#<n>` citations resolve without re-walking the corpus per ruling file (the
    existing per-file `known_stems` recompute this mirrors and does NOT fix - recorded,
    not fixed, out of THIS build's circle of control).

    Collisions are real and RULED CORRECT (doctrine measurement): a rev-chain shares one
    (sow, n) across many files (`editorial-recon` rev-k..rev-x all at n:1) - "asked by
    editorial-recon node 1" is the right citation granularity; WHICH rev posed the question
    is the ruling body's business, not the index's. Keep the file with the latest `updated:`
    per key, mirroring `awaiting_ruling`'s own dedup rule.
    """
    root = pathlib.Path(root).resolve()
    best = {}
    for f in iter_sow_files(root):
        fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(fm, dict):
            continue
        sid = fm.get("sow")
        if not sid:
            continue
        n = sow_identity(str(f), fm)
        if n is None:
            continue
        key = (str(sid).strip(), n)
        upd = str(fm.get("updated", "?"))
        if key not in best or upd > best[key][1]:
            best[key] = (str(f), upd, fm)
    return {k: (v[0], v[2]) for k, v in best.items()}


def build_stem_index(root):
    """{stem: (path, fm)} built ONCE corpus-wide - the fm-carrying sibling of the
    stem-only `known_stems` set. check_ruling_receipts needs the TARGET's frontmatter
    (to read its resolved_by:) when resolving a legacy path-form requested_by, and
    `files_fm` alone cannot supply it: a single-FILE commit-check lints ONE ruling, so
    `files_fm` holds exactly that one file and the asking SOW living elsewhere in the
    corpus is invisible to it - MEASURED live: `--commit-check` on one real ruling file
    silently dropped its resolved-by-missing-citation finding because the asker's fm
    was never in files_fm to begin with. Corpus-wide resolution fixes it at the root.
    """
    root = pathlib.Path(root).resolve()
    out = {}
    for f in iter_sow_files(root):
        fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if isinstance(fm, dict):
            out[pathlib.Path(f).stem] = (str(f), fm)
    return out


def _resolved_by_cites(fm, ruling_nnn):
    rb = str(fm.get("resolved_by", "") or "").strip()
    if not rb or ":" not in rb:
        return False
    kind, _, target = rb.partition(":")
    if kind.strip().lower() != "ruling":
        return False
    t = target.strip()
    if t.upper().startswith("RULING-"):
        t = t[len("RULING-") :]
    try:
        return int(t) == int(ruling_nnn)
    except ValueError:
        return t.lstrip("0") == str(ruling_nnn).lstrip("0")


def check_ruling_receipts(files_fm, root, commit_mode=False, sow_index=None, stem_index=None):
    """doctrine: 'a ruling naming an asking SOW whose resolved_by does not cite it
    back is an ERROR at the commit path, WARN otherwise.' Deliberately narrow: this checks
    ONLY the SOW(s) a ruling literally NAMES in its own `requested_by:` field — never a SOW
    the ruling's PROSE BODY discusses or disposes on terminal-state grounds without naming
    (doctrine disposed four SOWs' questions but names only ONE, track-b Rev6, in
    `requested_by`; the other three are Master's prose-reading duty, not this lint's — an
    inferred closure built from body text would look identical to a real one, which is
    exactly the shape doctrine's fail-closed-on-unverifiable rule forbids).

    `files_fm` supplies WHICH files to check (the lint TARGET - one ruling, a dir, the
    whole corpus); target resolution (finding the ASKER's own frontmatter) is corpus-wide
    via `sow_index`/`stem_index`, built fresh here if the caller has not passed them in -
    files_fm alone would silently blind a single-file `--commit-check` (the asker lives in
    a different file, invisible to a one-file files_fm — MEASURED, see build_stem_index).
    """
    if sow_index is None:
        sow_index = build_sow_n_index(root)
    if stem_index is None:
        stem_index = build_stem_index(root)
    out = defaultdict(list)
    for path, fm in files_fm:
        if not isinstance(fm, dict):
            continue
        if discriminate(path, fm) != "ruling":
            continue
        rb = str(fm.get("requested_by", "") or "").strip()
        if not rb or any(f in rb.lower() for f in _OPERATOR_FORMS):
            continue
        # identity read the same way `rulings_index` already does: filename first
        # (dodges the YAML-octal-leading-zero trap `ruling_id_from_bytes` exists for
        # when raw bytes aren't available here), fm.get("ruling") as fallback.
        m = _RULING_NAME_RE.match(pathlib.Path(path).name)
        nnn = m.group(1) if m else str(fm.get("ruling") or "").strip()
        if not nnn:
            continue
        for e in _split_requesters(rb):
            target_fm = None
            target_name = e
            sm = _STREAM_N_RE.match(e)
            pm = _PATH_WITH_REASON_RE.match(e)
            if sm:
                key = (sm.group(1), int(sm.group(2)))
                hit = sow_index.get(key)
                if hit:
                    target_fm = hit[1]
                    target_name = f"{key[0]}#{key[1]}"
            elif pm:
                stem = pathlib.Path(pm.group(1)).stem
                hit = stem_index.get(stem)
                if hit:
                    target_fm = hit[1]
                    target_name = pathlib.Path(pm.group(1)).name
            if target_fm is None:
                continue  # unresolvable target - check_requested_by's problem, not this one
            if _resolved_by_cites(target_fm, nnn):
                continue
            finding = Finding(
                WARN,
                "resolved-by-missing-citation",
                f"RULING-{nnn} names asking SOW '{target_name}' in requested_by, but that "
                f"SOW's resolved_by does not cite RULING-{nnn} back — the disposition and "
                "its receipt must land together (doctrine)",
            )
            if commit_mode:
                finding = Finding(ERROR, finding.code, finding.message)
            out[path].append(finding)
    return dict(out)


def _find_open_question(target_fm, qid):
    """Look up one row of target_fm['open_questions'] by id. Returns the row dict or
    None (missing field, non-list shape, or no row with that id — all three are ONE
    ghost outcome for the caller; check_resolves.open_questions_messages already
    caught a malformed list on the OWNING file's own lint pass, this is not where
    that gets re-reported)."""
    oq = target_fm.get("open_questions")
    if not isinstance(oq, list):
        return None
    for row in oq:
        if isinstance(row, dict) and str(row.get("id") or "").strip() == qid:
            return row
    return None


def check_resolves(files_fm, root, commit_mode=False, sow_index=None):
    """RULING-268 s1/s4 item 2: teach `resolves:` the `<stream>#<n>#<question-id>` form,
    the fine-grained sibling of `check_ruling_receipts`'s whole-file `requested_by`/
    `resolved_by` pair. Same shape, one level finer:
      - a `resolves:` entry that isn't <stream>#<n>#<question-id> or bare <stream>#<n>
        (RULING-268 s1: a bare stream#n citation resolves EVERY open question the file
        carries — backward-compat with the pre-existing whole-file form, not an error)
        is left alone here (check_requested_by's / check_resolved_by's problem, not
        this one — this function only grades entries that use the NEW field).
      - a #<question-id> suffix naming a stream/n that doesn't resolve, or a question
        id that doesn't exist on the resolved target's open_questions: list, is a ghost
        citation — same fail-closed posture as check_requested_by's stream-n ghost.
      - the closure-lands-together rule (RULING-268 s1, mirroring RULING-214 s2 applied
        one grain finer): a `resolves:` entry naming a real question whose OWN row on
        the target file is not `status: RESOLVED` is flagged — the citing document and
        the closed row must land in the same commit, exactly like check_ruling_receipts
        already enforces for whole-SOW ruling receipts.

    `files_fm` supplies the citing documents (a ruling, or a SOW's own resolves: on a
    later rev); resolution against the wider corpus is via `sow_index` (same corpus-wide
    index check_ruling_receipts already builds — reuse it, don't rebuild).
    """
    if sow_index is None:
        sow_index = build_sow_n_index(root)
    out = defaultdict(list)
    for path, fm in files_fm:
        if not isinstance(fm, dict):
            continue
        resolves = fm.get("resolves")
        if not resolves:
            continue
        if not isinstance(resolves, list):
            out[path].append(
                Finding(WARN if not commit_mode else ERROR, "resolves-shape", "resolves: is present but not a list")
            )
            continue
        for entry in resolves:
            e = str(entry or "").strip()
            m = _STREAM_N_QID_RE.match(e)
            if not m:
                continue  # bare stream#n or a legacy form: not this function's grain
            stream, n, qid = m.group(1), int(m.group(2)), m.group(3)
            hit = sow_index.get((stream, n))
            if hit is None:
                out[path].append(
                    Finding(
                        WARN if not commit_mode else ERROR,
                        "resolves-ghost-stream-n",
                        f"resolves: names '{e}' — no SOW on disk declares sow: {stream} at n: {n}",
                    )
                )
                continue
            target_path, target_fm = hit
            row = _find_open_question(target_fm, qid)
            if row is None:
                out[path].append(
                    Finding(
                        WARN if not commit_mode else ERROR,
                        "resolves-ghost-question-id",
                        f"resolves: names '{e}' — {stream}#{n} carries no open_questions: row "
                        f"with id '{qid}' (target: {pathlib.Path(target_path).name})",
                    )
                )
                continue
            row_status = str(row.get("status") or "").strip().upper()
            if row_status != "RESOLVED":
                out[path].append(
                    Finding(
                        WARN,
                        "resolves-missing-landed-closure",
                        f"resolves: names '{e}' but that question's own row on "
                        f"{pathlib.Path(target_path).name} is still status: "
                        f"{row.get('status')!r} — RULING-268 s1's lands-together rule "
                        "(RULING-214 s2 one grain finer) means the citation and the "
                        "target row's status:RESOLVED flip land in the SAME commit",
                    )
                )
    return dict(out)


def check_ruling(fm: dict, raw_text=None, commit_mode=False) -> list:
    """Ruling keystone — delegated to schemas.grade_ruling."""
    from .schemas import grade_ruling

    return grade_ruling(fm, raw_text=raw_text, commit_mode=commit_mode)


_CHARTER_STATUS_ENUM = {"ACTIVE", "SUPERSEDED", "DONE", "VOIDED"}


def check_charter(fm: dict, raw_text=None) -> list:
    """Charter keystone only — working fields stay on lint_file via grade_charter."""
    from .schemas import grade_charter

    _working = {"working-no-done-when", "working-no-restaufwand"}
    return [f for f in grade_charter(fm, commit_mode=False) if f.code not in _working]


def check_ruling_corpus(files_fm) -> dict:
    # ORG-SCOPE freshness only: doctrine (2026-08-02, ALREADY LANDED) SUPERSEDED
    # doctrine's "the repo IS the namespace, one flat counter" for project-scope
    # rulings - "per-project counters are LEGAL... a citation crossing a project boundary
    # is project-qualified." Only ORG-SCOPE rulings draw from ONE flat counter (now 200+).
    #
    # doctrine diagnosed two reasons this never fired anywhere: nothing called it
    # (fixed at the cli.py call site), and its return dict was keyed by BARE FILENAME while
    # every sibling corpus check (check_corpus) keys by FULL PATH, the shape per_file (the
    # merge target) actually reads - a naive wire-in silently dropped every finding into a
    # disconnected key. Both fixed. THIS docstring exists because a THIRD, more serious
    # defect surfaced only by running the fixed function against the REAL corpus rather
    # than a synthetic pair: an unscoped same-NNN-anywhere check found 28 "collisions" -
    # and RE-READING doctrine (which this function's own original comment never cited)
    # showed EVERY ONE was a legitimate cross-namespace reuse doctrine explicitly
    # legalized, including the exact 93/95/96/97 quartet doctrine itself names as the
    # paradigm case it was written to stop treating as a bug. Scoping to org-scope-only
    # reproduces ZERO false positives against that same corpus (MEASURED), and still
    # catches the shape that provoked doctrine in the first place: doctrine/215, both
    # declaring scope: org, the one namespace doctrine kept flat and un-reusable.
    # TOMBSTONE-AWARE (paid live, profrodai/org 2026-08-16): a VOIDED or SUPERSEDED file
    # is not claiming its integer - it is the doctrine-mandated record of a collision
    # ALREADY CAUGHT AND CORRECTED (append-don't-revert: the misfiled ruling's bytes stay,
    # a dated tombstone section names the successor, "do not cite this file"). The prior
    # unscoped check could not tell that apart from a live, unresolved collision, so a
    # tombstone that DOCUMENTS its own resolution failed the gate FOREVER - every session,
    # every Claude, no way to clear it short of deleting doctrine-mandated history. Two
    # ACTIVE (or AMENDED) files sharing an integer is still a real, live collision and
    # still errors; a VOIDED/SUPERSEDED file sharing an integer with a live one is the
    # normal, expected shape of a caught-and-corrected mistake and is silent.
    _NOT_LIVE = {"VOIDED", "SUPERSEDED"}
    seen = defaultdict(list)
    for path, fm in files_fm:
        m = _RULING_NAME_RE.match(pathlib.Path(path).name)
        if m and str(fm.get("scope", "")).strip().lower() == "org":
            status = str(fm.get("status", "")).strip().upper()
            live = status not in _NOT_LIVE
            seen[m.group(1)].append((path, live))
    out = {}
    for nnn, entries in seen.items():
        live_paths = [p for p, live in entries if live]
        if len(live_paths) > 1:
            names = sorted(pathlib.Path(p).name for p in live_paths)
            for p in live_paths:
                out.setdefault(p, []).append(
                    Finding(
                        ERROR,
                        "ruling-collision",
                        f"RULING-{nnn} claimed by {len(names)} LIVE ORG-SCOPE files: {names} - "
                        "org-scope draws from one flat counter (doctrine)",
                    )
                )
    return out


def ruling_homes(root):
    """Every RULING-*.md home in the corpus: the org root, and one per project (both
    layouts, pre- and post- projects/ container). The SAME three-glob shape already
    used at four other call sites in this file (check_resolved_by, requested_by_ghosts,
    check_binds_corpus) - factored here for the THREE new doctrine call sites
    (build_ruling_index, --mint ruling, --commit-check-corpus) so they share one
    definition rather than becoming a fifth independent copy."""
    root = pathlib.Path(root)
    return [root / "ruling", *root.glob("projects/*/ruling"), *root.glob("*/ruling")]


# -- doctrine(2)/s4: SURVIVE (the tombstone index) + s4 (--mint) --
_INDEX_FENCE_OPEN_RULING = "<!-- RULING-INDEX:AUTO — regenerated WHOLE by zeo --ruling-index, do not hand-edit -->"
_INDEX_FENCE_CLOSE_RULING = "<!-- END RULING-INDEX -->"
_RULING_INDEX_NAV_LINE = (
    "**Navigation, not evidence** (doctrine's caveat, applied here per "
    "doctrine: this index is the SAME PATTERN as stream-index.md, one "
    "layer over rulings). No SOW or ruling may cite a row here as proof of "
    "anything — walk the chain. A TOMBSTONE row means the integer was "
    "renumbered; both candidates are named so a stale citation resolves to "
    "something, never to silence and never to the wrong document."
)


def build_ruling_index(root):
    """doctrine(2)/s4: maps a ruling integer to every file that has EVER claimed it -
    its current owner (by filename), and, for any file carrying `minted_as: <old-integer>`,
    a TOMBSTONE entry under that old integer too. This is what makes a renumber SURVIVE: a
    reader following `doctrine` after the 214->215 renumber gets BOTH candidates and a
    date, not a confident wrong answer (doctrine's own measured hazard - a renumbered
    citation resolving to the WRONG LIVE DOCUMENT, which nothing before this could detect).

    `minted_as:` is read from frontmatter directly (not byte-parsed like the ruling's OWN
    identity - doctrine's octal trap is about a SCALAR read as the file's primary
    id; `minted_as` is always written as an explicit string by whoever performs the
    renumber, per doctrine(2), so this is not re-deriving identity from parsed YAML,
    it is reading a field authored as a plain string).

    PAID (2026-08-07, measured against the real corpus the first time a second and third
    renumber landed): `minted_as` is NOT reliably a bare integer. doctrine and doctrine
    both carry a full annotated sentence ("111 - RENUMBERED BEFORE LANDING. The example-project
    Master minted doctrine...") - a peer seat used the field's latitude (doctrine: a
    new field is an append, not a mutation of the four) to record WHY inline. Using the
    whole string as the dict key/table row put a paragraph in the `Integer` column and,
    had it contained a literal `|`, would have corrupted the markdown table outright. Only
    the LEADING integer is the identity; the rest is kept as a separate annotation, never
    embedded raw into a table cell (pipe/newline-stripped) - shown short, not dumped.

    Returns: {integer_str: [{"path": relpath, "scope": scope-or-None, "role": "owner"|
    "tombstone", "minted_as": <int-str-or-None>, "minted_as_note": <str-or-None>}, ...]} -
    a LIST per integer because doctrine legalized same-integer reuse across scopes
    (never collapse this to one entry).
    """
    root = pathlib.Path(root).resolve()
    entries = defaultdict(list)
    for h in ruling_homes(root):
        if not h.is_dir():
            continue
        for f in sorted(h.glob("RULING-*.md")):
            m = _RULING_NAME_RE.match(f.name)
            if not m:
                continue
            fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
            if not isinstance(fm, dict):
                continue
            rel = str(f.relative_to(root))
            scope = fm.get("scope")
            entries[m.group(1)].append(
                {
                    "path": rel,
                    "scope": scope,
                    "role": "owner",
                    "minted_as": None,
                    "minted_as_note": None,
                    "mint_provenance": None,
                }
            )
            old = fm.get("minted_as")
            if old:
                old_s = str(old).strip()
                im = re.match(r"^(\d+)", old_s)
                old_int = im.group(1) if im else old_s
                note = old_s[im.end() :].lstrip(" -:") if im else None
                # PAID (reported by Master, 2026-08-07, PHANTOM TOMBSTONE): minted_as ==
                # the file's OWN current number is not a renumber - doctrine recorded
                # minted_as: "114 - checked free at file time..." to note a NEAR-COLLISION
                # (111 and 113 were taken mid-session by a peer) while keeping 114 outright.
                # A tombstone claiming "renumbered away from 114" on the file that IS 114 is
                # a false claim from the same instrument that just stopped making one -
                # measured: 1 of 3 real minted_as fields in the corpus was this shape.
                # doctrine(2) defined minted_as for renumbers and never forbade this
                # good-faith secondary use (the field name reads as true either way) - the
                # spec gap is the ruling's, not the filer's, so this is a GUARD, not a
                # rejection: the genuine race evidence survives as mint_provenance on the
                # OWNER's own row instead of being silently dropped or falsely tombstoned.
                if old_int == m.group(1):
                    entries[m.group(1)][-1]["mint_provenance"] = note or old_s
                else:
                    entries[old_int].append(
                        {
                            "path": rel,
                            "scope": scope,
                            "role": "tombstone",
                            "minted_as": old_int,
                            "minted_as_note": note,
                        }
                    )
    return dict(entries)


def _safe_annotation(text, limit=100):
    """Table-cell-safe: a peer seat's free-text annotation can carry ANYTHING (measured:
    doctrine/114 wrote full sentences into minted_as) - pipes and newlines would corrupt
    a markdown table row or spill into the next one. Collapse to one line, strip pipes, cap
    length; the full text is always still in the source file, this is navigation only."""
    safe = " ".join(str(text).split()).replace("|", "/")
    if len(safe) > limit:
        safe = safe[: limit - 3] + "..."
    return safe


def render_ruling_index(entries, head, today):
    out = [
        _INDEX_FENCE_OPEN_RULING,
        "",
        f"_Generated {today} from `sows@{head}` — regenerated WHOLE on every run "
        "(doctrine, the same pattern as stream-index.md), never hand-edited._",
        "",
        _RULING_INDEX_NAV_LINE,
        "",
        "| Integer | Path | Scope | Note |",
        "|---|---|---|---|",
    ]
    for nnn in sorted(entries):
        rows = entries[nnn]
        # PAID (reported by Master, 2026-08-07): counting ALL rows (owners AND tombstones)
        # to decide "multiple occupants" mislabeled an owner+tombstone pair as "legal
        # per-scope reuse" - doctrine's own OWNER row read that note while its ONLY
        # co-occupant was doctrine's tombstone, not a second scope's owner. Legal reuse
        # (doctrine) is specifically TWO OWNERS in DIFFERENT scopes; a tombstone is a
        # SURVIVE artifact, an unrelated reason for the same integer to have >1 row. Two
        # owners in the SAME scope would be neither - a real collision this index should
        # never call "legal" - so that shape gets its own honest, un-legal-sounding note.
        owners = [r for r in rows if r["role"] == "owner"]
        owner_scopes = {r.get("scope") for r in owners}
        legal_reuse = len(owners) > 1 and len(owner_scopes) > 1
        same_scope_multi_owner = len(owners) > 1 and len(owner_scopes) <= 1
        for r in rows:
            if r["role"] == "tombstone":
                note = f"TOMBSTONE — renumbered away from {nnn}; current number is in the path"
                extra = r.get("minted_as_note")
                if extra:
                    note += f" ({_safe_annotation(extra)})"
            else:
                parts = []
                if legal_reuse:
                    parts.append("multiple occupants (legal per-scope reuse, doctrine)")
                elif same_scope_multi_owner:
                    parts.append("multiple OWNERS, SAME scope - not the doctrine shape, needs a human look")
                prov = r.get("mint_provenance")
                if prov:
                    # NOT a tombstone: minted_as named THIS file's own current number, a
                    # near-collision recorded in good faith, not a renumber (see the guard
                    # in build_ruling_index). Surfaced here rather than dropped, since it is
                    # real evidence of the exact race doctrine(3) says --mint cannot
                    # prevent - losing it to a validation rule would be a worse trade than
                    # one extra note.
                    parts.append(f"MINT-PROVENANCE (kept this number): {_safe_annotation(prov)}")
                note = "; ".join(parts)
            out.append(f"| `{nnn}` | `{r['path']}` | {r.get('scope') or '-'} | {note} |")
    out.append("")
    out.append(_INDEX_FENCE_CLOSE_RULING)
    return "\n".join(out) + "\n"


def next_ruling_id(root, project=None):
    """doctrine(3) / doctrine's original --next-ruling spec, corrected for
    doctrine AND for doctrine (the airgap defect): a PROJECT mint (project=<name>)
    returns 1 + the highest integer already used in THAT project's own ruling/ home, with
    no floor - doctrine legalized independent per-project counters, so a project mint
    must not be pushed into the 200+ band it does not need and does not share.

    An ORG-SCOPE mint (project=None) does NOT hardcode the 200 floor. doctrine: the
    band is a property of the CORPUS UNDER TEST, discovered from whether doctrine is
    itself a landed file in one of THIS corpus's own ruling/ homes - never compiled into
    the binary and carried into a corpus that never adopted it. PAID: example-org'
    doctrine was returned as the floor for a `--mint` run against example-org, a corpus
    that has never landed a doctrine and whose own 14 org-scope rulings sit correctly
    below 200 - the floor is discovered here (`band_landed`), never assumed.
        - doctrine landed in this corpus -> max(200, 1 + highest existing org-scope)
        - doctrine NOT landed here        -> 1 + highest existing org-scope, full stop
          (or 1, with no prior org-scope rulings at all)

    Returns (next_int, enumerated_homes, hit_count) - the enumeration doctrine already
    specified ("prints the first free integer... every ruling home"), returned rather than
    just printed, so a caller can show its own work. `enumerated_homes` lists only homes
    that actually EXIST on disk (doctrine): an empty list is the caller's signal
    that discovery found nothing to read, distinct from a homes-exist-but-empty corpus.
    """
    root = pathlib.Path(root).resolve()
    homes = [h for h in ruling_homes(root) if h.is_dir()]
    seen_any = []
    seen_org = []
    seen_project = []
    band_landed = False
    for h in homes:
        proj = None
        if h.parent.name != root.name:
            # projects/<x>/ruling or <x>/ruling - the project name is the parent dir
            proj = h.parent.name
        for f in sorted(h.glob("RULING-*.md")):
            m = _RULING_NAME_RE.match(f.name)
            if not m:
                continue
            n = int(m.group(1))
            seen_any.append(n)
            if n == 200:
                band_landed = True
            fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
            scope = fm.get("scope") if isinstance(fm, dict) else None
            if str(scope or "").strip().lower() == "org":
                seen_org.append(n)
            if project and proj == project:
                seen_project.append(n)
    if project:
        nxt = (max(seen_project) + 1) if seen_project else 1
    elif band_landed:
        nxt = max(200, (max(seen_org) + 1) if seen_org else 200)
    else:
        nxt = (max(seen_org) + 1) if seen_org else 1
    return nxt, [str(h) for h in homes], len(seen_any)


_MINT_RACE_NOTE = (
    "NOTE: this is the next free {kind} id AS OF THIS DISK READ ({ts}) - it is "
    "NOT reserved or locked. A peer minting concurrently can claim the same "
    "integer; doctrine detects that collision downstream (at the next "
    "corpus-wide check), it does not prevent it. Re-run the pre-mint check "
    "immediately before landing."
)

_MINT_RESERVED_NOTE = (
    "RESERVED: stub written exclusively at {path} — the id is claimed on disk. "
    "Fill the frontmatter/body and commit; a peer mint will see this file and take the next id."
)


def words_to_slug(words: str, *, max_words: int = 5, max_len: int = 48) -> str:
    """Normalize agent words to a canonical kebab slug."""
    cleaned = _SLUG_CLEAN.sub("-", str(words or "").lower()).strip("-")
    parts = [p for p in cleaned.split("-") if p]
    if not parts:
        return "untitled"
    slug = "-".join(parts[:max_words])
    return slug[:max_len].strip("-") or "untitled"


def _exclusive_create(path: pathlib.Path, content: str) -> bool:
    """Create path only if absent (O_CREAT|O_EXCL). Returns True on success."""
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(path), flags, 0o644)
    except FileExistsError:
        return False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        return True
    except Exception:
        path.unlink(missing_ok=True)
        raise


def reserve_sow_stub(
    root,
    stream: str,
    words: str,
    *,
    n: int | None = None,
    retries: int = 8,
) -> tuple[pathlib.Path | None, str]:
    """Mint+reserve a canonical SOW path by writing an exclusive stub.

    Returns (path, detail). path is None on refusal.
    """
    root = pathlib.Path(root).resolve()
    L = locate_stream(root, stream)
    if L["ambiguous"]:
        return None, f"AMBIGUOUS - {len(L['candidates'])} dirs named {stream!r}"
    if n is None:
        if L["next_n"] is not None:
            n = L["next_n"]
        else:
            # Brand-new stream OR empty chain dir with no integer n: yet → genesis.
            n = 1
    chain = pathlib.Path(L["chain_dir"]) if L["chain_dir"] else None
    if chain is None:
        # Brand-new stream: prefer projects/*/sow/<stream> if projects/ exists, else sow/<stream>
        projects = root / "projects"
        if projects.is_dir():
            # pick first project dir if only one, else create under a synthetic home
            projs = [p for p in projects.iterdir() if p.is_dir()]
            base = projs[0] / "sow" / stream if len(projs) == 1 else root / "sow" / stream
        else:
            base = root / "sow" / stream
        chain = base
    chain.mkdir(parents=True, exist_ok=True)
    slug = words_to_slug(words)
    # Prefer projects/<project> when chain is under projects/
    project = project_of(chain / "x.md", root)
    if project is None and (root / "projects").is_dir():
        projs = [p for p in (root / "projects").iterdir() if p.is_dir()]
        if len(projs) == 1:
            project = projs[0].name
    project = project or "unknown"
    from .sow_authoring import build_frontmatter, render_sow, transactional_create

    for attempt in range(retries):
        candidate_n = n + attempt
        name = canonical_name(stream, candidate_n, slug)
        dest = chain / name
        title = slug.replace("-", " ")
        try:
            fm = build_frontmatter(
                project=project,
                stream=stream,
                n=candidate_n,
                status="DRAFT",
                lifecycle="DESIGN-MEMO",
                done_when="REPLACE — runnable stopping predicate",
                restaufwand=1,
                work_repo="same-as-sow_repo",
                requested_by="unknown - mint stub",
            )
        except Exception as exc:
            return None, str(exc)
        body = f"# {stream} SOW-{candidate_n:02d}: {title}\n\n(stub reserved by `zeo --mint sow` — replace this body)\n"
        content = render_sow(fm, body)
        ok, reason, _ = transactional_create(dest, content, root=root)
        if ok:
            return dest, f"n={candidate_n}"
        if "collision" in reason or "already exists" in reason:
            continue
        # Fall back to exclusive create without lint gate for mint stubs in bare trees
        if _exclusive_create(dest, content.decode("utf-8")):
            return dest, f"n={candidate_n}"
        continue
    return None, f"could not reserve after {retries} attempts starting at n={n}"


def reserve_ruling_stub(
    root,
    words: str,
    *,
    nnn: int | None = None,
    retries: int = 8,
) -> tuple[pathlib.Path | None, str]:
    """Mint+reserve a canonical ruling path by writing an exclusive stub."""
    import datetime as _dt

    root = pathlib.Path(root).resolve()
    nxt, homes, total = next_ruling_id(root, project=None)
    if not homes:
        return None, "0 ruling home(s) discoverable"
    ref_claims = scan_ref_ruling_claims(root)
    colliding = {ref: (n, p) for ref, (n, p) in ref_claims.items() if n >= nxt}
    if colliding:
        widest = max(n for n, _p in colliding.values())
        nxt = max(nxt, widest + 1)
    if nnn is not None:
        nxt = nnn
    home = pathlib.Path(homes[0])
    home.mkdir(parents=True, exist_ok=True)
    slug = words_to_slug(words)
    today = _dt.date.today().isoformat()
    for attempt in range(retries):
        candidate = nxt + attempt
        name = f"RULING-{_pad(candidate)}-{slug}.md"
        dest = home / name
        body = (
            f"---\n"
            f"ruling: {candidate}\n"
            f'title: "{slug.replace("-", " ")}"\n'
            f"authority: master\n"
            f"scope: org\n"
            f"status: ACTIVE\n"
            f"landing_commit: self\n"
            f"binds: []\n"
            f"genre: ruling\n"
            f"created: {today}\n"
            f"updated: {today}\n"
            f"requested_by: \n"
            f"---\n\n"
            f"# RULING-{_pad(candidate)} — {slug.replace('-', ' ')}\n\n"
            f"(stub reserved by `zeo --mint ruling` — replace this body)\n"
        )
        if _exclusive_create(dest, body):
            return dest, f"nnn={candidate}; homes={len(homes)}; seen={total}"
    return None, f"could not reserve after {retries} attempts starting at {nxt}"


def scan_ref_ruling_claims(root, timeout=30):
    """doctrine: `--mint` reads LANDED FILES off the working tree/disk while a
    colliding claim can live on a REF - a branch pushed to origin (or sitting local,
    unmerged) that `ruling_homes` never walks because it isn't checked out. The
    example-org Sparring measured this as observable, not the "cannot see a peer minting"
    dead end example-seat doctrine it off as: the peer's doctrine claim was sitting
    at a pushed branch, `a263763`.

    RULED (s3): fetch, then scan every `refs/remotes/*` ref's tree for `ruling/RULING-
    NNN-*.md` paths, returning the HIGHEST integer claimed per ref plus the exact path -
    so a collision names the specific claimant ("`origin/example-stream/foo` already carries
    doctrine"), never a generic race caveat ("someone might be minting").

    Best-effort: a fetch failure (offline, no remote, not a git repo at all) degrades to
    scanning whatever refs are already known locally rather than raising - this is an
    ADVISORY widening of the mint's field of view, not a new hard dependency on network
    access. Returns {refname: (highest_int, path_at_that_ref)}.
    """
    root = pathlib.Path(root).resolve()
    try:
        subprocess.run(
            ["git", "-C", str(root), "fetch", "--all", "--quiet"],
            capture_output=True,
            timeout=timeout,
        )
    except Exception:
        pass
    claims = {}
    try:
        refs_out = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "for-each-ref",
                "--format=%(refname)",
                "refs/remotes",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if refs_out.returncode != 0:
            return claims
        refs = [r.strip() for r in refs_out.stdout.splitlines() if r.strip()]
    except Exception:
        return claims
    for ref in refs:
        if ref.endswith("/HEAD"):  # refs/remotes/origin/HEAD - a pointer, not a branch
            continue
        try:
            tree = subprocess.run(
                ["git", "-C", str(root), "ls-tree", "-r", "--name-only", ref],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if tree.returncode != 0:
                continue
        except Exception:
            continue
        best_n, best_path = None, None
        for line in tree.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            p = pathlib.PurePosixPath(line)
            if p.parent.name != "ruling":
                continue
            m = _RULING_NAME_RE.match(p.name)
            if not m:
                continue
            n = int(m.group(1))
            if best_n is None or n > best_n:
                best_n, best_path = n, line
        if best_n is not None:
            claims[ref] = (best_n, best_path)
    return claims


# -- BOARD: derived state zone (doctrine, doctrine's four co-signed bindings) --
STATE_FENCE_OPEN = "<!-- STATE:AUTO — regenerated by zeo --board, do not hand-edit -->"
STATE_FENCE_CLOSE = "<!-- END STATE -->"
_NAV_LINE = (
    "**Navigation, not evidence.** This zone says WHERE to look, never WHAT is true. "
    "No SOW may cite a board row as proof — walk the chain."
)


_REV_LETTER_RE = re.compile(r"^[a-zA-Z]+$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _rev_rank(rev):
    """Orderable (kind, value) rank for a rev: field, or None if unorderable.

    This corpus uses BOTH conventions for rev: -- numeric chains (rev: 1, 2, 3 ...,
    parsed by YAML as int or a digit string) and letter chains (rev: a, b, c ... z,
    then aa, ab, ac ... -- confirmed live on disk, e.g. archaeology streams). Neither
    shape may be hardcoded as the only orderable one; both are handled generically
    here (letters via a base-26 rank so multi-letter revs order past z correctly).
    Anything else (a bare word, a trailing comment, a compound id) is left
    unorderable -- the caller falls back to a date signal rather than guessing.
    """
    if isinstance(rev, bool):
        return None
    if isinstance(rev, int):
        return ("int", rev)
    if isinstance(rev, str):
        s = rev.strip()
        if not s:
            return None
        if s.isdigit():
            return ("int", int(s))
        if _REV_LETTER_RE.match(s):
            rank = 0
            for ch in s.lower():
                rank = rank * 26 + (ord(ch) - ord("a") + 1)
            return ("alpha", rank)
    return None


def _orderable_date(entry):
    for field in ("updated", "created"):
        v = entry.get(field)
        if isinstance(v, str) and _ISO_DATE_RE.match(v.strip()):
            return v.strip()
    return None


def latest_rev_of(entries):
    # Binding 4 (CONSERVATIVE RENDER): a stream whose revs are not all integer-
    # identified cannot be ordered, so it renders UNKNOWN rather than a confident
    # wrong row. Proven necessary: example-project uses letter revs (rev-o..rev-s) and
    # an int sort silently picked an arbitrary file (DS5-SCRATCH-140).
    # Era-gating, as check_n already does: n: exists only from Rev 11 on, so a
    # legacy entry without one is GRANDFATHERED, not disqualifying. UNKNOWN is for
    # a stream with NOTHING orderable (true letter-rev chains: example-project rev-o..s,
    # rebase-coord rev a). Requiring ALL entries to carry n: rendered 11/17 streams
    # UNKNOWN incl. example-stream's 66 clean revs, and HID 2 of 3 awaiting-ruling rows
    # — conservative-render must fail closed on the ROW, never blind the BOARD.
    numbered = [e for e in entries if isinstance(e.get("n"), int)]
    if not numbered:
        return None
    max_n = max(e["n"] for e in numbered)
    tied = [e for e in numbered if e["n"] == max_n]
    if len(tied) == 1:
        return tied[0]
    # Binding 5 (TIE-BREAK BY REV, THEN DATE): a chain can legitimately mint n:
    # once and encode true revision order in rev: a/b/c...z instead -- max()-on-n
    # alone then ties every entry and silently returns whichever one the caller's
    # file-scan happened to build first, which is NOT true rev order. Proven live:
    # editorial-recon (27 files, every one n: 1, rev: a..z) rendered its rev-k
    # snapshot on the board instead of the true tail, rev-z. Prefer rev: (numeric
    # or letter, whichever this chain uses) when ALL tied entries carry a mutually
    # orderable one; else prefer updated:/created: date when ALL tied entries carry
    # one; only if NOTHING orderable distinguishes the tie do we fall back to the
    # prior (file-scan-order) behavior -- same conservative-fail-closed spirit as
    # Binding 4, scoped to the tie rather than the whole stream.
    ranked = [(_rev_rank(e.get("rev")), e) for e in tied]
    kinds = {rank[0] for rank, _ in ranked if rank is not None}
    if len(kinds) == 1 and all(rank is not None for rank, _ in ranked):
        return max(ranked, key=lambda pair: pair[0])[1]
    dated = [(_orderable_date(e), e) for e in tied]
    if all(date is not None for date, _ in dated):
        return max(dated, key=lambda pair: pair[0])[1]
    return tied[0]


_RESTING = {
    "CLOSEOUT",
    "HANDOVER",
    "HELD",
    "BLOCKED",
    "FINDING",
    "SHIPPED",
    "SUPERSEDED",
    "VOIDED",
    "STALE",
}


ABWEICHUNG_CODES = (
    "SCOPE-CHANGED",
    "ESTIMATE-WRONG",
    "BLOCKED-EXTERNAL",
    "DISCOVERED-WORK",
    "AS-PLANNED",
)


# KOSTENRECHNUNG. In an LLM relay, TOKENS ARE THE MONEY - CLAUDE.md s12 has always reasoned
# this way ("its length is a per-turn tax on the entire fleet") without an instrument.
#
# Token estimates live in cost.py (tiktoken cl100k_base proxy, else chars/3.6). CHARS_PER_TOKEN
# is kept here as the public constant CLI banners historically referenced; the estimator itself
# is ESTIMATE and labelled as one everywhere it surfaces. Claude's tokenizer is not public;
# Anthropic documents that third-party tokenizers mis-estimate Claude.
from .cost import estimate_tokens_local  # noqa: E402


def est_tokens(text) -> int:
    """ESTIMATED tokens. Never call this a count. Delegates to cost.estimate_tokens_local."""
    return estimate_tokens_local(text)


def waste_report(root, stream=None, estimate=None):
    """WASTE, in tokens: work the fleet paid for and did not keep.

    THE COST FUNCTION IS NOT min(tokens). This corpus is the proof: SOWs are long BECAUSE s3
    demands recon-before-build, s6 a check per claim, s14 the ledger. Optimise for fewer
    tokens and you get skipped recon and presence-checks - every failure the last 17 revisions
    removed. A cheap wrong answer is the most expensive artifact here.

    Three categories, and only TWO are worth minimising:

      TAX        - CLAUDE.md + boot docs + skills. Fixed, multiplied by every session the
                   fleet will ever run. MINIMISE HARD (s12's shrink loop, now with a number).
      WASTE      - what this function counts. Rework, wrong-direction work, retracted claims.
                   MINIMISE.
      INVESTMENT - recon, checks, reading the source before claiming something about it.
                   DO NOT MINIMISE. Every waste event measured on 2026-08-02 traced to SKIPPED
                   investment: a seat that did not read doctrine, a Master who did not read
                   doctrine, nobody reading migrate.py. Those reads cost hundreds of tokens and
                   would each have saved tens of thousands.

    Counted here, all from the corpus:
      RETRACTED  - a rev whose lifecycle is SELF-CORRECTION, or whose body says RETRACT.
      VARIANCE   - a FULL-VARIANCE soll/ist pair: a rev's plan wholly abandoned.
      CHURN      - consecutive revs where n advances but no ledger claim does.

    NEVER SET A TOKEN TARGET ON A STREAM. A stream optimising its own token count stops
    reading things, and that is the one failure mode this corpus cannot afford.
    """
    estimate = estimate or est_tokens
    root = pathlib.Path(root).resolve()
    out = []
    variance_pairs = {(x["stream"], x["to_n"]) for x in soll_ist(root, stream) if x["verdict"] == "FULL-VARIANCE"}
    for r in find_sow_roots(root):
        for d in sorted(x for x in r.iterdir() if x.is_dir()):
            if stream and d.name != stream:
                continue
            revs = []
            for f in sorted(d.glob("*.md")):
                txt = f.read_text(encoding="utf-8", errors="replace")
                fm = extract_frontmatter(txt)
                if not isinstance(fm, dict):
                    continue
                try:
                    n = int(fm.get("n"))
                except (TypeError, ValueError):
                    continue
                revs.append((n, f, fm, txt))
            revs.sort()
            for n, f, fm, txt in revs:
                tok = estimate(txt)
                kinds = []
                if str(fm.get("lifecycle", "")).upper() == "SELF-CORRECTION":
                    kinds.append("RETRACTED")
                if "RETRACT" in txt.upper()[:4000]:
                    if "RETRACTED" not in kinds:
                        kinds.append("RETRACTION-IN-BODY")
                if (d.name, n) in variance_pairs:
                    kinds.append("PLAN-ABANDONED")
                if kinds:
                    out.append(
                        {
                            "project": r.parent.name,
                            "stream": d.name,
                            "n": n,
                            "file": f.name,
                            "tokens": tok,
                            "kinds": kinds,
                        }
                    )
    return out


def kosten(root, stream=None, estimate=None):
    """What the fleet SPENDS, in the only unit that is money.

    Three numbers, and the first is the one nobody looks at:

    FIXED PER-SESSION TAX - CLAUDE.md + the role's boot doc + the authoring skills are
    prepended to EVERY session of EVERY stream. A line added there is multiplied by every
    session the fleet will ever run. s12's shrink loop exists for this and has never had a
    number attached to it.

    ARTIFACT COST - what a stream's own chain weighs.

    WIRTSCHAFTLICHKEIT - artifact tokens per SHIPPED claim. Not a target: a stream doing hard
    work writes more per claim, and a stream writing 30k tokens per claim is worth ASKING
    about, never automatically wrong.

    NOT MEASURED here, and the honest gap: SESSION tokens - context, tool output, the
    operator's pastes - are not in the corpus. They are the larger cost. Use
    `zeo --session-cost` (transcript / session-costs.jsonl) for that. This function
    reports what the FILES cost, and says so.

    `estimate` is an optional callable(text)->int; default is cost.estimate_tokens_local.
    """
    estimate = estimate or est_tokens
    root = pathlib.Path(root).resolve()
    fixed = {}
    for rel in ("claude-md/CLAUDE.md",):
        f = root / rel
        if f.is_file():
            fixed[rel] = estimate(f.read_text(encoding="utf-8", errors="replace"))
    for d in ("roles", "authoring"):
        for f in sorted((root / d).glob("*.md")) if (root / d).is_dir() else []:
            fixed[f"{d}/{f.name}"] = estimate(f.read_text(encoding="utf-8", errors="replace"))
    streams = []
    for r in find_sow_roots(root):
        for d in sorted(x for x in r.iterdir() if x.is_dir()):
            if stream and d.name != stream:
                continue
            tok, files, shipped = 0, 0, 0
            for f in sorted(d.glob("*.md")):
                txt = f.read_text(encoding="utf-8", errors="replace")
                tok += estimate(txt)
                files += 1
                fm = extract_frontmatter(txt)
                if isinstance(fm, dict):
                    for c in fm.get("ledger") or []:
                        if isinstance(c, dict) and str(c.get("state", "")).upper() in (
                            "SHIPPED",
                            "FINDING",
                        ):
                            shipped += 1
            if files:
                streams.append(
                    {
                        "project": r.parent.name,
                        "stream": d.name,
                        "files": files,
                        "tokens": tok,
                        "claims": shipped,
                        "per_claim": int(tok / shipped) if shipped else None,
                    }
                )
    rulings = 0
    for d in [root / "ruling", *root.glob("projects/*/ruling")]:
        if d.is_dir():
            for f in d.glob("RULING-*.md"):
                rulings += estimate(f.read_text(encoding="utf-8", errors="replace"))
    return {
        "fixed": fixed,
        "fixed_total": sum(fixed.values()),
        "streams": streams,
        "ruling_tokens": rulings,
        "corpus_total": sum(s["tokens"] for s in streams),
    }


def restaufwand(root, stream=None):
    """RESTAUFWAND, not FERTIGSTELLUNGSGRAD: what is LEFT, and whether it is falling.

    doctrine Percent-complete is vanity - it rises while the work grows, so a stream can
    report 80% for a fortnight and be further from done than when it started. Each rev declares
    WHAT IS LEFT (`restaufwand:`, an integer of remaining units in the stream's own unit) and
    THE TREND OF THAT NUMBER IS THE SIGNAL. Meilenstein-Trendanalyse on a SOW chain.

    MEASURED at introduction (doctrine): `done_when` in ZERO files corpus-wide, which is
    why profrod-site sat 10 days at one SOW in DESIGN - a stream with no stopping condition
    never terminates, because every session finds more to do.

    Verdicts, per stream:
      FALLING     - remaining decreased across the last two declarations. Progressing.
      FLAT        - unchanged. Busy is not progressing.
      RISING      - discovery outpacing delivery. Not a fault; a fact that wants a reason.
      UNDECLARED  - no rev declares restaufwand. DISTANCE IS UNMEASURABLE and that is the
                    honest headline, never a silent zero.
    """
    root = pathlib.Path(root).resolve()
    out = []
    for r in find_sow_roots(root):
        for d in sorted(x for x in r.iterdir() if x.is_dir()):
            if stream and d.name != stream:
                continue
            revs = []
            for f in sorted(d.glob("*.md")):
                fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
                if not isinstance(fm, dict):
                    continue
                sid = str(fm.get("sow") or d.name)
                if stream and sid != stream and d.name != stream:
                    continue
                try:
                    n = int(fm.get("n"))
                except (TypeError, ValueError):
                    continue
                try:
                    rest = int(fm.get("restaufwand"))
                except (TypeError, ValueError):
                    rest = None
                revs.append(
                    (
                        n,
                        rest,
                        fm.get("done_when"),
                        sid,
                        str(fm.get("status", "")).upper(),
                    )
                )
            if not revs:
                continue
            revs.sort()
            sid = revs[-1][3]
            series = [(n, x) for n, x, _, _, _ in revs if x is not None]
            latest = revs[-1]
            if len(series) < 2:
                verdict = "UNDECLARED" if not series else "SINGLE-POINT"
                delta = None
            else:
                delta = series[-1][1] - series[-2][1]
                verdict = "FALLING" if delta < 0 else ("RISING" if delta > 0 else "FLAT")
            out.append(
                {
                    "project": r.parent.name,
                    "stream": sid,
                    "declarations": len(series),
                    "series": series[-5:],
                    "remaining": series[-1][1] if series else None,
                    "delta": delta,
                    "verdict": verdict,
                    "done_when": latest[2],
                    "status": latest[4],
                    "working": latest[4] in _WORKING_STATUSES,
                    "needs_done_when": latest[4] in _WORKING_STATUSES and not latest[2],
                }
            )
    return out


_WORKING_STATUSES = {"DRAFT", "DESIGN", "PROGRESS", "RULING-REQUESTED"}

# Genre-keyed WORKING-like sets (example-stream-CHARTER-03 item 2): each gradeable genre with a
# WORKING/RESTING status axis gets its OWN set, rather than assuming the SOW one applies
# everywhere. A charter borrows the ruling vocabulary (ACTIVE/SUPERSEDED) - `ACTIVE` is
# its one "still being worked" state, mirroring a ruling's in-force status.
_WORKING_LIKE = {
    "sow": _WORKING_STATUSES,
    "charter": {"ACTIVE"},
}


def check_working_fields(fm, genre, commit_mode=False):
    """doctrine — delegated to genre graders (kept for direct call sites)."""
    if genre == "sow":
        from .schemas import grade_sow

        return [
            f
            for f in grade_sow(fm, commit_mode=commit_mode)
            if f.code in ("working-no-done-when", "working-no-restaufwand")
        ]
    if genre == "charter":
        from .schemas import grade_charter

        return [
            f
            for f in grade_charter(fm, commit_mode=commit_mode)
            if f.code in ("working-no-done-when", "working-no-restaufwand")
        ]
    return []


def soll_ist(root, stream=None, materiality=0):
    """SOLL/IST-VERGLEICH: what a rev PLANNED against what the next rev DID.

    Rev n declares `next_three_acts` (SOLL). Rev n+1 records what happened (IST). A variance
    is not a fault - plans change - but an UNSTATED variance is invisible drift, and drift is
    what a relay cannot see without asking.

    PAID: a session ran the wrong work for a full sitting with every instrument green. The
    operator could not tell without asking. Nothing compared plan to outcome.

    ABWEICHUNGSANALYSE: a variance alone is noise. A variance with a REASON CODE is management
    data - `abweichung:` from ABWEICHUNG_CODES on the rev that diverged. Compounding
    DISCOVERED-WORK becoming SCOPE-CHANGED is visible in the codes long before the prose.

    WESENTLICHKEIT: `materiality` suppresses variances below a threshold of matched acts, so
    the report stays readable. A report nobody reads is a report that does not exist.
    """

    def _acts(fm):
        v = fm.get("next_three_acts")
        if isinstance(v, str):
            return [v]
        return [str(x) for x in v] if isinstance(v, list) else []

    root = pathlib.Path(root).resolve()
    out = []
    for r in find_sow_roots(root):
        for d in sorted(x for x in r.iterdir() if x.is_dir()):
            if stream and d.name != stream:
                continue
            revs = []
            for f in sorted(d.glob("*.md")):
                fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
                if not isinstance(fm, dict):
                    continue
                try:
                    n = int(fm.get("n"))
                except (TypeError, ValueError):
                    continue
                revs.append((n, f, fm))
            revs.sort()
            for (n0, f0, fm0), (n1, f1, fm1) in zip(revs, revs[1:]):
                soll = _acts(fm0)
                if not soll:
                    continue
                body1 = f1.read_text(encoding="utf-8", errors="replace").lower()
                claims = " ".join(
                    str(c.get("claim", "")) for c in (fm1.get("ledger") or []) if isinstance(c, dict)
                ).lower()
                hay = body1 + " " + claims
                matched = []
                for act in soll:
                    # a planned act counts as DONE if its distinctive words appear in the
                    # successor's body or ledger. Word-level, because an act is restated in
                    # the doing, never quoted.
                    words = [w for w in re.findall(r"[a-z-]{5,}", act.lower())][:6]
                    hits = sum(1 for w in words if w in hay)
                    matched.append(bool(words) and hits >= max(1, len(words) // 3))
                done = sum(matched)
                if done >= max(materiality, 0) and done == len(soll):
                    verdict = "AS-PLANNED"
                elif done == 0:
                    verdict = "FULL-VARIANCE"
                else:
                    verdict = "PARTIAL"
                code = str(fm1.get("abweichung", "")).upper() or None
                out.append(
                    {
                        "project": r.parent.name,
                        "stream": d.name,
                        "from_n": n0,
                        "to_n": n1,
                        "soll": soll,
                        "matched": matched,
                        "done": done,
                        "of": len(soll),
                        "verdict": verdict,
                        "abweichung": code,
                        "unstated": verdict != "AS-PLANNED" and not code,
                    }
                )
    return out


def stream_progress(root, stream=None):
    """DISTANCE TO DONE, not activity.

    PAID: a full session ran the WRONG WORK with every instrument green - files migrating,
    lint clean, SOWs well-formed. Nothing measured distance, so nothing could show the
    distance was not shrinking. MEASURED the same day: 29 streams idle >7 days against 4
    filing today, and nothing distinguished FINISHED from ABANDONED.
    """
    import datetime

    root = pathlib.Path(root).resolve()
    today = datetime.date.today()
    out = []
    for r in find_sow_roots(root):
        for d in sorted(x for x in r.iterdir() if x.is_dir()):
            if stream and d.name != stream:
                continue
            fs = sorted(d.glob("*.md"))
            dates, ns, latest, best = [], [], None, -1
            for f in fs:
                fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
                if not isinstance(fm, dict):
                    continue
                for k in ("created", "updated"):
                    if fm.get(k):
                        dates.append(str(fm[k]))
                try:
                    n = int(fm.get("n"))
                except (TypeError, ValueError):
                    n = -1
                ns.append(n)
                if n > best:
                    best, latest = n, fm
            if not dates or latest is None:
                continue
            first, last = min(dates), max(dates)
            try:
                fd = datetime.date.fromisoformat(first)
                ld = datetime.date.fromisoformat(last)
                span, idle = (ld - fd).days + 1, (today - ld).days
            except ValueError:
                span, idle = 0, -1
            st = str(latest.get("status", "")).upper()
            out.append(
                {
                    "project": r.parent.name,
                    "stream": d.name,
                    "files": len(fs),
                    "n": max(ns) if ns else 0,
                    "first": first,
                    "last": last,
                    "span": span,
                    "rate": round(len(fs) / span, 2) if span else 0,
                    "idle": idle,
                    "status": st,
                    "resting": st in _RESTING,
                    "done_when": latest.get("done_when"),
                    "next_three_acts": latest.get("next_three_acts"),
                }
            )
    return out


def git_ref_state(root):
    """doctrine: an instrument states the boundary of what it read.

    `--inbox`/`--locate` (and every generator that stamps a header line) read pathlib off
    disk with ZERO git - CORRECT, per doctrine: a seat must see its own uncommitted
    work, and switching to trunk-only reads would hide that from the seat that needs it
    most. The defect the ruling names is narrower: "disk" is a CHECKOUT, a seat's question
    is usually about the TRUNK, and nothing in the output said which one was read - MEASURED
    in example-org, `--inbox` from a branch silently reports that branch's own tail, and a
    seat proving "my filing is visible to the fleet" that way has read work the fleet
    cannot see and called it published.

    This does not change what gets read (doctrine rules that out explicitly) - it is
    the disclosure a caller prints alongside its existing output. Returns:

    {"ref": <branch name, or short SHA if HEAD is detached>, "sha": <short HEAD SHA>,
     "dirty": <bool - True if the working tree has uncommitted changes, None if undetectable>,
     "trunk": "main", "contained_in_trunk": <True|False|None>}

    `contained_in_trunk` is None whenever it cannot be determined honestly (not a git repo,
    no `origin/<trunk>` remote-tracking ref reachable) - NEVER guessed as True or False,
    the same fail-closed shape doctrine requires everywhere else in this file. A caller
    prints None as "unknown", not as either answer.
    """
    root = str(root)

    def _run(*args):
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)
        return r.returncode, r.stdout.strip()

    rc, sha = _run("rev-parse", "--short", "HEAD")
    if rc != 0:
        return {
            "ref": None,
            "sha": None,
            "dirty": None,
            "trunk": None,
            "contained_in_trunk": None,
        }
    rc2, branch = _run("rev-parse", "--abbrev-ref", "HEAD")
    ref = branch if (rc2 == 0 and branch and branch != "HEAD") else sha  # detached HEAD
    rc3, status = _run("status", "--porcelain")
    dirty = (len(status) > 0) if rc3 == 0 else None
    trunk = "main"
    rc4, _ = _run("rev-parse", "--verify", "--quiet", f"origin/{trunk}")
    if rc4 != 0:
        contained = None  # no origin/<trunk> to compare against - not a guess either way
    else:
        rc5, _ = _run("merge-base", "--is-ancestor", "HEAD", f"origin/{trunk}")
        contained = rc5 == 0
    return {
        "ref": ref,
        "sha": sha,
        "dirty": dirty,
        "trunk": trunk,
        "contained_in_trunk": contained,
    }


def format_ref_disclosure(state):
    """The one-line form doctrine asks for ("the cheapest form is one line of
    output"). Shared so every caller's disclosure line reads identically."""
    if state.get("sha") is None:
        return "ref: UNKNOWN (not a git repo - disk state cannot be attributed to any ref)"
    bits = [f"ref: {state['ref']} @{state['sha']}"]
    if state["dirty"] is None:
        bits.append("(commit-state unknown)")
    elif state["dirty"]:
        bits.append("(UNCOMMITTED changes present - this read includes work no one else can see)")
    else:
        bits.append("(clean)")
    trunk = state.get("trunk") or "trunk"
    if state["contained_in_trunk"] is None:
        bits.append(f"- containment in origin/{trunk} UNKNOWN (no origin/{trunk} ref found)")
    elif state["contained_in_trunk"]:
        bits.append(f"- contained in origin/{trunk} (this state is visible to the fleet)")
    else:
        bits.append(f"- NOT contained in origin/{trunk} (this state is NOT yet visible to the fleet)")
    return " ".join(bits)


def locate_stream(root, stream):
    """Everything a booting stream needs, DERIVED FROM DISK, given only its own name.

    PAID (2026-08-02): a spawn message named two different chain directories and two
    different chain tails for the same seat. The stream correctly refused to derive an `n:`
    from a message that contradicted itself. A spawn must name the STREAM; the tool resolves
    the rest - org/ holds the whole GitHub org, each project is a repo, and paths move.

    Matches a directory whose NAME is the stream, then confirms against the frontmatter
    `sow:` field. AMBIGUITY IS REPORTED, NEVER RESOLVED: two dirs with one name is a
    condition a human rules on, not one a tool picks a winner for.
    """
    root = pathlib.Path(root).resolve()
    # MEASURED (GM-example-stream-214): this matched the DIRECTORY NAME only, so
    # `--locate example-project-repo-hygiene` found nothing while the board showed 11 rows -
    # its SOWs declare `sow: example-project-repo-hygiene` and sit in a dir named `repo-hygiene`.
    # Every other projection keys on `fm.get("sow") or <dirname>` (four sites, consistent):
    # THE DECLARATION IS THE PROPERTY, THE DIRECTORY IS THE PROXY. A stream is what it says
    # it is; the directory is where it happens to sit - which is why one dir can host a
    # foreign relay SOW (example-stream holds example-project-cto-relay, measured, legitimate).
    hits = []
    for r in find_sow_roots(root):
        for d in r.iterdir():
            if not d.is_dir():
                continue
            declared = set()
            for f in d.glob("*.md"):
                fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
                if isinstance(fm, dict) and fm.get("sow"):
                    declared.add(str(fm["sow"]).strip())
            if stream in declared or (not declared and d.name == stream):
                hits.append(d)
    out = {
        "stream": stream,
        "candidates": [str(d.relative_to(root)) for d in hits],
        "chain_dir": None,
        "project": None,
        "files": 0,
        "latest": None,
        "next_n": None,
        "declared_sow": None,
        "diary": None,
        "ambiguous": len(hits) > 1,
    }
    if not hits:
        return out
    d = hits[0]
    out["chain_dir"] = str(d.resolve())
    out["project"] = project_of(str(d / "x.md"), root)
    mds = sorted(d.glob("*.md"))
    out["files"] = len(mds)
    best, best_n, sows = None, -1, set()
    for f in mds:
        fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(fm, dict):
            continue
        if fm.get("sow"):
            sows.add(str(fm["sow"]).strip())
        try:
            n = int(fm.get("n"))
        except (TypeError, ValueError):
            continue
        if n > best_n:
            best_n, best = (
                n,
                (
                    f.name,
                    n,
                    str(fm.get("rev", "")),
                    str(fm.get("status", "")),
                    str(fm.get("seat", "")),
                ),
            )
    if best:
        out["latest"] = {
            "file": best[0],
            "n": best[1],
            "rev": best[2],
            "status": best[3],
            "seat": best[4],
        }
        out["next_n"] = best[1] + 1
    out["declared_sow"] = sorted(sows)
    diary = root / "learnings" / stream
    out["diary"] = str(diary) if diary.is_dir() else None
    return out


def find_sow_roots(repo_root):
    # <project>/sow/<task>/ — discovered, never assumed. Multi-project as of 869c729.
    r = pathlib.Path(repo_root)
    # MEASURED (GM-example-stream-183): glob('*/sow') is SINGLE-level, so projects/<project>/sow
    # is invisible - example-org reported `0 projects` since its restructure. This is not
    # cosmetic: ungraded_streams() and flat_dark_files() BOTH iterate sow_roots, so an
    # empty list makes the DARK burn-down meter report zero pre-schema streams and zero
    # flat files - green because it cannot see (doctrine's banned silent downgrade).
    # Union both layouts so a MIXED state during a restructure stays fully visible.
    roots = set(r.glob("*/sow")) | set(r.glob("projects/*/sow"))
    return sorted(d for d in roots if d.is_dir())


# ── V3: stream-index + binds (doctrine — the declaration is the property) ──
def build_stream_index(root):
    """doctrine: the mechanism. A stream id resolves to a path via the DECLARED
    `sow:` frontmatter field — NEVER the dirname (s1's namespace fix, `locate_stream`'s
    same rule generalised corpus-wide instead of one stream at a time).

    A directory with NO file declaring ANY `sow:` field is pre-schema legacy; it is
    matched by its OWN DIRNAME (locate_stream's fallback, unchanged) so a live 24-rev
    pre-schema stream like `example-project` still resolves — s5's 15-dir DARK bucket, not
    a naming defect.

    AMBIGUITY IS RECORDED, NEVER RESOLVED (s1): two directories declaring the same id
    get BOTH candidates listed and no single `path` — a human question, never a tool's
    guess. `directional facing` (s6, a space in a dirname) is landed and NOT renamed;
    it is read via `pathlib`, never a shell glob, so the space is not a hazard here.
    """
    root = pathlib.Path(root).resolve()
    by_id = defaultdict(list)  # id -> [(dirpath, project, preschema_hit)]
    for r in find_sow_roots(root):
        project = r.parent.name
        for d in sorted(x for x in r.iterdir() if x.is_dir()):
            declared = set()
            for f in d.glob("*.md"):
                fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
                if isinstance(fm, dict) and fm.get("sow"):
                    declared.add(str(fm["sow"]).strip())
            if declared:
                for sid in declared:
                    by_id[sid].append((d, project, False))
            else:
                by_id[d.name].append((d, project, True))
    entries = {}
    for sid, hits in by_id.items():
        dirs = sorted({str(h[0].relative_to(root)) for h in hits})
        projects = sorted({h[1] for h in hits})
        entries[sid] = {
            "path": dirs[0] if len(dirs) == 1 else None,
            "candidates": dirs,
            "ambiguous": len(dirs) > 1,
            "project": projects[0] if len(projects) == 1 else None,
            "preschema": all(h[2] for h in hits),
        }
    return entries


_INDEX_FENCE_OPEN = "<!-- STREAM-INDEX:AUTO — regenerated WHOLE by zeo --stream-index, do not hand-edit -->"
_INDEX_FENCE_CLOSE = "<!-- END STREAM-INDEX -->"
_INDEX_NAV_LINE = (
    "**Navigation, not evidence** (doctrine). No SOW or ruling may cite a "
    "row here as proof of anything — walk the chain. A stream with no `path` is "
    "NOT-STARTED or AMBIGUOUS (see `candidates`); a `path` with no numbered SOW "
    "yet is CHARTERED-NOT-BEGUN."
)


def render_stream_index(entries, head, today):
    out = [
        _INDEX_FENCE_OPEN,
        "",
        f"_Generated {today} from `sows@{head}` — regenerated WHOLE on every run (doctrine), never hand-edited._",
        "",
        _INDEX_NAV_LINE,
        "",
        "| Stream id | Path | Project | Note |",
        "|---|---|---|---|",
    ]
    for sid in sorted(entries):
        e = entries[sid]
        if e["ambiguous"]:
            note = f"AMBIGUOUS — {len(e['candidates'])} directories declare this id"
            path = "—"
        elif e["preschema"]:
            note = "pre-schema (matched by dirname, no `sow:` field on disk)"
            path = e["path"]
        else:
            note = ""
            path = e["path"]
        out.append(f"| `{sid}` | `{path}` | {e.get('project') or '-'} | {note} |")
    out.append("")
    out.append(_INDEX_FENCE_CLOSE)
    return "\n".join(out) + "\n"


_ROLE_TOKENS = {"master", "sparring", "operator"}


def check_binds(fm, entries, known_projects):
    """doctrine: `binds:` names STREAM IDS resolvable in `stream-index.md`. A
    PROJECT belongs in `scope:`, not `binds:`. A ROSTER (`all-streams`) or a ROLE
    (`sparring` — a seat, not a stream) carries an explicit `binds-class:` so a reader
    and a tool can both tell which is meant; declaring it TRUSTS the declaration and
    skips resolution entirely (s4's own worked example: `binds: [master, sparring,
    example-stream]` under `binds-class: role` is not re-litigated even though `master` and
    `example-stream` also happen to resolve as real streams — the class describes the CITATION'S
    intent, not a fact the index could contradict).

    Landed rulings are NOT rewritten (doctrine); every finding here is a WARN in the
    general lint (a recorded, countable residue) and is promoted to ERROR only at the
    commit path (doctrine's gate-the-future idiom, applied to this field).
    """
    out = []
    binds = fm.get("binds")
    if not binds:
        return out
    if isinstance(binds, str):
        toks = [t.strip() for t in re.split(r"[,\n]", binds) if t.strip()]
    else:
        toks = [str(t).strip() for t in binds]
    bc_raw = fm.get("binds-class")
    bc = str(bc_raw).strip().lower() if bc_raw else ""
    if bc in ("role", "roster"):
        return out
    if bc and bc not in ("role", "roster", "stream"):
        out.append(
            Finding(
                WARN,
                "binds-class-invalid",
                f"binds-class: '{bc_raw}' is not one of stream | roster | role (doctrine)",
            )
        )
    for tok in toks:
        if "|" in tok:
            out.append(
                Finding(
                    WARN,
                    "binds-malformed",
                    f"binds: entry '{tok}' contains a literal '|' — a YAML list item, not a "
                    "pipe-separated string (doctrine)",
                )
            )
            continue
        e = entries.get(tok)
        if e is not None and e["path"] is not None:
            continue
        if e is not None and e["ambiguous"]:
            out.append(
                Finding(
                    WARN,
                    "binds-ambiguous",
                    f"binds: '{tok}' matches {len(e['candidates'])} directories in "
                    f"stream-index.md ({', '.join(e['candidates'])}) — RECORDED, not resolved "
                    "(doctrine)",
                )
            )
            continue
        if tok in known_projects:
            out.append(
                Finding(
                    WARN,
                    "binds-project-not-scope",
                    f"binds: '{tok}' is a PROJECT, not a stream id — doctrine rules a "
                    "project belongs in scope:, not binds:",
                )
            )
            continue
        if tok in _ROLE_TOKENS or tok.endswith("-master") or tok.startswith("all-"):
            out.append(
                Finding(
                    WARN,
                    "binds-needs-class",
                    f"binds: '{tok}' is absent from stream-index.md and looks like a role or "
                    "roster, not a stream — declare binds-class: role|roster (doctrine)",
                )
            )
            continue
        out.append(
            Finding(
                WARN,
                "binds-unresolved",
                f"binds: '{tok}' is absent from stream-index.md — no directory declares this "
                "id and none is named it. Check for a typo, a retired id, or a genuinely "
                "absent stream (doctrine)",
            )
        )
    return out


def check_binds_corpus(files_fm, root, commit_mode=False, index=None):
    """Corpus-level pass (mirrors check_corpus's shape): builds the index ONCE, checks
    every file that carries a `binds:` field — rulings today, but genre-agnostic by
    construction (the CHARTER example in doctrine's own reception carries one too)."""
    if index is None:
        index = build_stream_index(root)
    known_projects = {e["project"] for e in index.values() if e["project"]}
    out = defaultdict(list)
    for path, fm in files_fm:
        if not isinstance(fm, dict) or not fm.get("binds"):
            continue
        findings = check_binds(fm, index, known_projects)
        if commit_mode:
            findings = [Finding(ERROR, f.code, f.message) if f.code.startswith("binds-") else f for f in findings]
        if findings:
            out[path].extend(findings)
    return dict(out)


def ungraded_streams(sow_root):
    # A directory holding .md files of which NONE carry frontmatter is pre-schema
    # legacy: invisible to the projection. It gets a row saying so, never silence.
    out = []
    root = pathlib.Path(sow_root)
    if not root.is_dir():
        return out
    proj = root.parent.name
    for d in sorted(x for x in root.iterdir() if x.is_dir()):
        mds = list(d.glob("*.md"))
        if not mds:
            continue
        # MEASURED (GM-example-stream-199): startswith("---") counted a DELIVERY-NOTE block as graded,
        # so ten such files made a whole stream read GRADED and hid 12 real Class-A files from
        # the DARK meter. "Graded" means SCHEMA-SHAPED.
        graded = [
            m for m in mds if is_schema_shaped(extract_frontmatter(m.read_text(encoding="utf-8", errors="replace")))
        ]
        if not graded:
            out.append({"stream": d.name, "project": proj, "files": len(mds)})
    return out


def flat_dark_files(sow_root):
    """Pre-schema files sitting DIRECTLY in <project>/sow/, with no stream dir.

    ungraded_streams() walks `if x.is_dir()` (l796) and therefore CANNOT SEE these
    by construction. Convicted live: 29 frontmatter-less files across example-project(2),
    example-project(10), example-project(12), example-project(5) are on disk and absent from
    every projection. Found independently by example-stream doctrine (filed INFERRED with
    a falsifier) and by example-stream doctrine (measured as 29 `missing: sow` migrate blockers) -
    one defect, two directions.

    This matters beyond tidiness: doctrine makes the DARK count the migration's
    PUBLIC BURN-DOWN METER, so a projection blind to 29 files reports the meter low.
    An instrument that cannot see a violation must not report health (doctrine).
    """
    out = []
    root = pathlib.Path(sow_root)
    if not root.is_dir():
        return out
    proj = root.parent.name
    for f in sorted(root.glob("*.md")):
        text = f.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            out.append({"project": proj, "file": f.name, "path": str(f)})
    return out


def intake_open_rows(root):
    """doctrine item 3: an `intake/` file with `status: OPEN` renders on
    `--triage` as an OPEN board row, per the ratified intake/README.md ("AN
    UNCONVERTED INTAKE RENDERS AS AN OPEN BOARD ROW").

    Canonical closed statuses: PROMOTED / DUPLICATE / REJECTED / PARKED.
    Legacy aliases still closed for triage: CHARTERED→PROMOTED, DECLINED→REJECTED,
    SUPERSEDED→DUPLICATE. This is a PROJECTION, not evidence (doctrine): no SOW or
    ruling may cite a board row as proof, only the intake file itself.

    `intake/` sits at the repo root, not under any `<project>/sow/`, so
    board_rows()'s `"sow" in path.parts` filter structurally cannot see it
    (core.py:1888) — this is a deliberately separate, narrow walk of one
    directory, not a fix to board_rows' stream-shaped contract.
    """
    from .schemas.intake import normalize_intake_status

    root = pathlib.Path(root)
    d = root / "intake"
    out = []
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.md")):
        fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(fm, dict):
            continue
        if str(fm.get("genre", "")).strip().lower() != "intake":
            continue
        if normalize_intake_status(fm.get("status")) != "OPEN":
            continue
        out.append(
            {
                "intake": str(fm.get("id") or fm.get("intake") or f.stem),
                "project": str(fm.get("project_hint") or fm.get("project") or "-"),
                "created": str(fm.get("created") or "?"),
                "file": f.name,
            }
        )
    return out


def entries_project(entries):
    ps = {e.get("project") for e in entries if e.get("project") and e.get("project") != "-"}
    return sorted(ps)[0] if len(ps) == 1 else ("/".join(sorted(ps)) if ps else "-")


def board_rows(files_fm):
    streams = {}
    for path, fm in files_fm:
        if not isinstance(fm, dict):
            continue
        p = pathlib.Path(path)
        if "sow" not in [x.lower() for x in p.parts]:
            continue
        sid = str(fm.get("sow") or p.parent.name)
        streams.setdefault(sid, []).append(
            {
                "project": project_of(path) or "-",
                "n": fm.get("n"),
                "rev": fm.get("rev"),
                "status": str(fm.get("status", "") or ""),
                "lifecycle": str(fm.get("lifecycle", "") or "-"),
                "updated": str(fm.get("updated", "") or "?"),
                "file": p.name,
            }
        )
    rows = []
    for sid in sorted(streams):
        top = latest_rev_of(streams[sid])
        if top is None:
            rows.append(
                {
                    "stream": sid,
                    "project": entries_project(streams[sid]),
                    "latest": "UNKNOWN",
                    "status": "UNKNOWN",
                    "lifecycle": "-",
                    "updated": "-",
                    "file": "",
                    "note": "revs not integer-identified — walk the chain",
                }
            )
        else:
            rows.append(
                {
                    "stream": sid,
                    "project": top.get("project", "-"),
                    "latest": str(top["n"]),
                    "status": top["status"] or "UNKNOWN",
                    "lifecycle": top["lifecycle"],
                    "updated": top["updated"],
                    "file": top["file"],
                    "note": "",
                }
            )
    return rows


_SOWNUM_RE = re.compile(r"(?i)SOW-(\d+)")


def sow_identity(path, fm):
    # The SOW's identity number. n: when present (Rev 11+); else the filename's
    # SOW-NN. Streams that put the number in the NAME and the revision in rev:
    # (letters) — keying on n: alone found no order and listed every revision of
    # every SOW as separately awaiting.
    n = fm.get("n")
    if isinstance(n, int):
        return n
    m = _SOWNUM_RE.search(pathlib.Path(path).name)
    return int(m.group(1)) if m else None


def rulings_index(files_fm):
    # requested_by: -> the SOWs a ruling ANSWERS. This is the Master->little-Claude
    # half of the loop: a stream may not know its request was ruled.
    out = []
    for path, fm in files_fm:
        if not isinstance(fm, dict):
            continue
        if str(fm.get("genre", "")).strip().lower() != "ruling" and not _RULING_NAME_RE.match(pathlib.Path(path).name):
            continue
        rb = str(fm.get("requested_by", "") or "")
        m = _RULING_NAME_RE.match(pathlib.Path(path).name)
        nnn = m.group(1) if m else str(fm.get("ruling", "?"))
        out.append((nnn, rb, str(fm.get("updated", "?")), path))
    return out


def requested_by_ghosts(root):
    """Every `requested_by:` target that does not resolve to a file on disk.

    MEASURED (diag): 17 ghosts against 106 resolvable - a 14% failure rate on the ONE
    field that closes a Master->stream loop. BOOT-MASTER s5 has named this as "the single
    biggest hole in master-to-stream communication" for weeks; it was documented and never
    GATED, and four of the seventeen were filed by the seat that wrote the warning, on the day
    it wrote it.

    SIXTEEN OF SEVENTEEN ARE NEAR-MISSES - a filename cited AS REMEMBERED rather than AS READ
    OFF DISK: a truncated tail (`-escalation` for `-escalation-handover`), a wrong word
    (`retire-shipped` for `retired-shipped`), a wrong number (doctrine doctrine). The
    seventeenth has no close match and is a genuinely lost artifact (doctrine's family).

    Returns rows with the nearest real basename, so a repair is a POINTER not a guess.
    `requested_by` is immutable on a landed ruling (doctrine), so landed ghosts are WARNs
    and repaired by amendment; the ERROR belongs on the NEXT filing.
    """
    import difflib

    root = pathlib.Path(root).resolve()
    allmd = {}
    for p in root.rglob("*.md"):
        allmd.setdefault(p.name, p)
    out = []
    for d in [root / "ruling", *root.glob("projects/*/ruling"), *root.glob("*/ruling")]:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("RULING-*.md")):
            fm = extract_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
            if not (isinstance(fm, dict) and fm.get("requested_by")):
                continue
            for tok in re.split(r"[,\s]+", str(fm["requested_by"])):
                if not tok.endswith(".md"):
                    continue
                nm = pathlib.Path(tok).name
                if nm in allmd:
                    continue
                near = difflib.get_close_matches(nm, list(allmd), n=1, cutoff=0.6)
                out.append(
                    {
                        "ruling": f.name,
                        "names": nm,
                        "nearest": near[0] if near else None,
                        "lost": not near,
                    }
                )
    return out


def check_resolved_by(fm, root, ruling_stems=None):
    """doctrine: resolved_by records HOW a RULING-REQUESTED SOW closed, gate-verified
    against ground, fail-closed on unverifiable. Five forms:
      ruling: RULING-NNN | commit: <repo>@<sha> | rev: N | superseded-by: SOW-NN | operator: <sow-path>
    Returns (kind, target, ok, detail). kind=None if no resolved_by. This is the mechanism
    that makes the inbox tell the truth: a valid resolver moves a SOW out of OPEN; an
    unverifiable one FAILS (resolved_by-ghost) so it cannot become false-ANSWERED reborn."""
    rb = fm.get("resolved_by")
    if not rb:
        return (None, None, None, None)
    s = str(rb).strip()
    # RESOLVE, not just wrap: `commit:` below does root.parent / <repo> to reach a
    # SIBLING repo. A lexically relative root (Path(".") from `zeo --triage .`,
    # the natural way to invoke it from inside the sows repo) has `.parent == "."` -
    # the sibling repo is never found and a VALID commit-kind resolver silently fails
    # closed. Measured: `--triage .` and `--triage` (auto-discovered, absolute) gave
    # different example-stream open counts (4 vs 1) off the SAME corpus - an instrument
    # whose answer depends on argv spelling rather than the SOW it is reading.
    root = pathlib.Path(root).resolve()
    # form: "kind: target"
    if ":" not in s:
        return ("malformed", s, False, "resolved_by must be 'kind: target'")
    kind, _, target = s.partition(":")
    kind = kind.strip().lower()
    target = target.strip()
    if kind == "ruling":
        # RULING-NNN exists on disk
        # MEASURED (GM-example-stream-203): this globbed root/example-project/ruling - HARDCODED and
        # PRE-RESTRUCTURE. Proven before the fix: `ruling: 046` returned 'no such ruling
        # on disk' while projects/example-project/ruling EXISTED and example-project/ruling did not.
        # So every resolved_by: ruling: NNN closed NOTHING while LOOKING like a
        # fail-closed verdict - the worst shape a gate can take. Org-scope rulings at
        # root ruling/ were never findable at all. Third instance of this family after
        # project_of and find_sow_roots.
        #
        # MEASURED (worldprops-SOW-24, 2026-08-17): a well-formed target with trailing
        # prose - `ruling: RULING-272 (backfilled 2026-08-17 by Master ...)` - globbed for
        # a literal file named "RULING-272 (backfilled..." and found nothing, so a REAL,
        # ON-DISK ruling reported `ok=False, detail="no such ruling on disk"` — a message
        # that is simply false (the ruling exists) and indistinguishable from a genuinely
        # absent one. The author has no way to tell "you typed the wrong number" from
        # "your formatting broke the match" without reading this function's source. Fix:
        # extract the leading integer explicitly and match on THAT, but keep the two
        # failure shapes distinguishable in `detail` rather than silently tolerating
        # decoration — an author writing "ruling: 272 see also 273" should be told their
        # target was ambiguous, not have it quietly resolved to the first number found.
        m = re.match(r"^(?:RULING-)?(\d+)\s*(.*)$", target)
        if m is None:
            return ("ruling", target, False, "resolved_by ruling target has no leading number")
        num, trailing = m.group(1), m.group(2).strip()
        stem = "RULING-" + num
        homes = [
            root / "ruling",
            *root.glob("projects/*/ruling"),
            *root.glob("*/ruling"),
        ]
        hits = [f for h in homes if h.is_dir() for f in h.glob(stem + "-*.md")]
        if not hits:
            detail = "no such ruling on disk"
        elif trailing:
            detail = f"ruling file present (trailing text after the number ignored: {trailing!r})"
        else:
            detail = "ruling file present"
        return (
            "ruling",
            target,
            bool(hits),
            detail,
        )
    if kind == "rev":
        # N <= current canonical Rev
        from .scaffold import read_doctrine as _read_doctrine

        canon = find_canonical_claude_md(root)
        cur = parse_current_rev(_read_doctrine(canon)) if canon and canon.is_file() else None
        try:
            ok = cur is not None and int(target) <= int(cur)
        except ValueError:
            return ("rev", target, False, "rev not an integer")
        return (
            "rev",
            target,
            ok,
            f"Rev {target} <= canonical {cur}" if ok else f"Rev {target} > canonical {cur}",
        )
    if kind == "commit":
        # <repo>@<sha> — verify sha resolves in that sibling repo
        if "@" not in target:
            return ("commit", target, False, "commit must be <repo>@<sha>")
        repo, _, sha = target.partition("@")
        repo_path = root.parent / repo.strip()
        import subprocess

        try:
            r = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "cat-file",
                    "-e",
                    sha.strip() + "^{commit}",
                ],
                capture_output=True,
                timeout=5,
            )
            ok = r.returncode == 0
        except Exception:
            ok = False
        return (
            "commit",
            target,
            ok,
            "sha resolves" if ok else f"sha not found in {repo}",
        )
    if kind == "superseded-by":
        # SOW-NN exists in this stream dir (self-serving resolver — rendered separately)
        # MEASURED (doctrine item 1): this globbed root/example-project/sow/<sid> - HARDCODED
        # and PRE-RESTRUCTURE, the SAME family as the `ruling` kind's GM-example-stream-203 fix above,
        # unfixed here. Proven before the fix: example-stream/doctrine's `superseded-by: doctrine`
        # returned 'no such SOW in stream' while projects/governance-layer/sow/example-stream
        # held doctrine disk and example-project/sow/example-stream did not exist. A stream's own
        # closure record, silently unreadable because a project moved out from under a
        # hardcoded path. Fourth instance of this family after project_of, find_sow_roots,
        # and check_resolved_by's own `ruling` kind.
        sid = str(fm.get("sow") or "")
        dirs = [d for d in (*root.glob(f"projects/*/sow/{sid}"), *root.glob(f"*/sow/{sid}")) if d.is_dir()]
        num = target.replace("SOW-", "")
        hits = [f for d in dirs for f in d.glob(f"*SOW-{num}-*.md")]
        return (
            "superseded-by",
            target,
            bool(hits),
            "later SOW present" if hits else "no such SOW in stream",
        )
    if kind == "operator":
        # the SOW-path that banked the in-session ruling exists (semantic half human)
        hits = (root / target).is_file() or list(root.glob(f"**/{pathlib.Path(target).name}"))
        return (
            "operator",
            target,
            bool(hits),
            "banking SOW present" if hits else "no such SOW",
        )
    return ("unknown", target, False, f"unknown resolver kind '{kind}'")


def answered_by(idx, stream, sownum, filename, on_disk=None):
    # EXACT-MATCH ONLY. A claim that "this was ruled" is a causal claim about bytes:
    # it carries proof or it does not fire. Fuzzy matching (stream name + any SOW-NN
    # in requested_by) produced FALSE ANSWERED rows — doctrine as ruled by
    # doctrine, which names doctrine; and doctrine as ruled by doctrine,
    # WHICH DOES NOT EXIST ON DISK. A false ANSWERED tells a stream to proceed on a
    # ruling nobody made — the ghost-citation class, mechanized. Worse than silence.
    stem = pathlib.Path(filename).stem
    for nnn, rb, upd, path in idx:
        if not rb:
            continue
        if stem in rb or filename in rb:
            return str(nnn), upd
    return None


_RAW_ID_RE = re.compile(r"^ruling:\s*(\S+)\s*$", re.M)


def ruling_id_from_bytes(text):
    # YAML 1.1 parses a LEADING-ZERO scalar as OCTAL: `ruling: 016` -> 14,
    # `012` -> 10, `010` -> 8. (008/009 survive only as invalid octal -> str.)
    # So the parsed value is NOT the identity — check_ruling reported doctrine's
    # file as "doctrine", a real and different ruling: a manufactured ghost
    # citation, the doctrine class made by my own tool. zfill() made it WORSE by
    # rendering the wrong number plausibly (diag). An identity field is
    # read from the BYTES, never from a parser's interpretation of them.
    m = _RAW_ID_RE.search(text or "")
    return m.group(1).strip().strip("\"'") if m else None


def _pad(n):
    return str(n).zfill(3) if isinstance(n, int) else str(n).strip()


_RESOLVE_ROOT = [None]


def open_questions_summary(fm):
    """RULING-268 s1 / charter Phase 1 item 3: per-file rollup of open_questions: rows.

    Returns None when the field is absent or not a list (additive — a file with zero
    open_questions: rows is untouched by this, byte-identical to pre-field behavior).
    Otherwise returns a dict {tag, resolved, total} where tag is one of:
      OPEN       — every row status: OPEN (m resolved out of m is 0)
      RESOLVED   — every row status: RESOLVED
      PARTIAL    — a genuine mix, reported as "PARTIAL (n/m)" by the caller
    A row with a status outside {OPEN, RESOLVED} (the open_questions_messages shape
    lint already ERRORs on this at the owning file's own grade_sow pass) counts toward
    neither bucket here — this function summarizes, it does not re-validate shape.
    """
    oq = fm.get("open_questions")
    if not isinstance(oq, list) or not oq:
        return None
    resolved = 0
    total = 0
    for row in oq:
        if not isinstance(row, dict):
            continue
        st = str(row.get("status") or "").strip().upper()
        if st not in OPEN_QUESTION_STATUSES:
            continue
        total += 1
        if st == "RESOLVED":
            resolved += 1
    if total == 0:
        return None
    if resolved == 0:
        tag = "OPEN"
    elif resolved == total:
        tag = "RESOLVED"
    else:
        tag = "PARTIAL"
    return {"tag": tag, "resolved": resolved, "total": total}


def awaiting_ruling(files_fm, root=None):
    _RESOLVE_ROOT[0] = root
    # Scans EVERY file, independent of rev-ordering: an unorderable stream must not
    # lose its escalation (guide-sweep rendered UNKNOWN and its RULING-REQUESTED
    # silently left the list — DS5-SCRATCH-148).
    # A rev is awaiting a ruling only if NOTHING later exists in its stream: a
    # superseded RULING-REQUESTED was answered by the stream moving on. Scanning
    # every file without this rendered example-project-track-A at rev 18 AND 19 and
    # track-B at 3/4/6/8 — a list that cries wolf is a list nobody reads, which is
    # the failure the board exists to end (DS5-SCRATCH-150).
    idx = rulings_index(files_fm)
    high = {}
    for path, fm in files_fm:
        if not isinstance(fm, dict):
            continue
        pp = pathlib.Path(path)
        if "sow" not in [x.lower() for x in pp.parts]:
            continue
        sid = str(fm.get("sow") or pp.parent.name)
        n = sow_identity(path, fm)
        if n is not None:
            high[sid] = max(high.get(sid, -1), n)
    out = []
    for path, fm in files_fm:
        if not isinstance(fm, dict):
            continue
        pp = pathlib.Path(path)
        if "sow" not in [x.lower() for x in pp.parts]:
            continue
        if not str(fm.get("status", "")).upper().startswith("RULING-REQUESTED"):
            continue
        sid = str(fm.get("sow") or pp.parent.name)
        n = sow_identity(path, fm)
        # CLOSURE RULE: a ruling-request is closed by a RULING, never by the stream
        # filing a later SOW. Excluding on `n < high[sid]` hid example-stream doctrine
        # doctrine doctrine — coding the operator's exact complaint into the
        # detector built for it. Only REVISIONS of the SAME SOW collapse (below).
        ans = answered_by(idx, sid, n, pp.name, on_disk=True)
        # doctrine: a valid resolved_by is a THIRD closure state - the SOW is resolved
        # by implementation/doctrine/supersession, which answered_by (ruling-only) cannot see.
        rkind, rtarget, rok, _rdetail = (
            check_resolved_by(fm, _RESOLVE_ROOT[0]) if _RESOLVE_ROOT else (None, None, None, None)
        )
        resolved = (rkind, rtarget) if rok else None
        out.append(
            {
                "stream": sid,
                "sownum": n if n is not None else -1,
                "rev": str(n if n is not None else fm.get("rev") or "?"),
                "updated": str(fm.get("updated", "?")),
                "file": pp.name,
                "answered": ans,
                "resolved": resolved,
                "supersession": rok and rkind == "superseded-by",
            }
        )
    # dedupe per (stream, SOW identity): keep the latest revision by updated:
    best = {}
    for r in out:
        k = (r["stream"], r["sownum"])
        if k not in best or r["updated"] > best[k]["updated"]:
            best[k] = r
    return sorted(best.values(), key=lambda r: (r["stream"], r["sownum"]))


def needs_successor(awaiting, rows):
    """The NEEDS-SUCCESSOR projection: answered rulings a stream may not have acted on.

    doctrine MANDATES this filter: "a stream past the answered SOW (higher n,
    CLOSEOUT, or valid resolved_by) is never listed." Those THREE conditions, exactly -
    not "any resting status", which would suppress HELD streams the ruling never
    authorised.

    WHY IT LIVES HERE AND NOT IN awaiting_ruling: that function deliberately does NOT
    exclude on `n < high[sid]`, because doing so hid example-stream doctrine/66 behind doctrine -
    the operator's exact complaint, coded into the detector built for it. A
    ruling-request is closed by a RULING, never by the stream filing a later SOW. But
    the SUCCESSOR bucket asks a DIFFERENT question - "has this stream already acted?" -
    and for that, a later SOW IS evidence. Two buckets, two semantics, one data source.

    Measured before the fix: 34 rows listed, 29 of them streams that had moved on
    (example-project at doctrine pending at doctrine/2/3/6 - the named defect, verbatim).
    A list that cries wolf is a list nobody reads.

    Returns (listed, suppressed) - the instrument declares what it hid.
    """
    latest = {}
    for r in rows:
        latest[str(r["stream"])] = r
    listed, suppressed = [], []
    for a in awaiting:
        if not a.get("answered"):
            continue
        if a.get("resolved"):  # valid resolved_by: closed
            suppressed.append((a, "resolved_by"))
            continue
        row = latest.get(str(a["stream"]))
        if row is None:
            listed.append(a)
            continue
        status = str(row.get("status", "")).upper().split("-SEE")[0].strip()
        if status == "CLOSEOUT":
            suppressed.append((a, "stream CLOSEOUT"))
            continue
        try:
            if int(row.get("latest")) > int(a.get("sownum", -1)):
                suppressed.append((a, f"stream at SOW-{row.get('latest')}"))
                continue
        except (TypeError, ValueError):
            pass  # unorderable stream: stay VISIBLE rather than guess closed
        listed.append(a)
    return listed, suppressed


def render_state_zone(rows, head, today, awaiting=(), ungraded=()):
    out = [STATE_FENCE_OPEN, ""]
    out.append(f"_Generated {today} from `sows@{head}` — regenerated whole on every run._")
    out.append("")
    out.append(_NAV_LINE)
    out.append("")
    out.append("| Project | Stream | Latest | Status | Lifecycle | Updated |")
    out.append("|---|---|---|---|---|---|")
    for r in rows:
        s = r["stream"]
        note = f" _({r['note']})_" if r["note"] else ""
        out.append(
            f"| {r.get('project', '-')} | {s} | {r['latest']} | {r['status']}{note} | {r['lifecycle']} | {r['updated']} |"
        )
    aw = awaiting
    out.append("")
    _open = [x for x in aw if not x.get("answered")]
    _ans = [x for x in aw if x.get("answered")]
    out.append(
        f"**Open questions ({len(_open)} awaiting a ruling · {len(_ans)} ruled-but-maybe-unread).** "
        "An open question does NOT halt a stream — it fences ONE direction. "
        "Matching is exact (`requested_by` names the file); a ruling not named here is not claimed."
    )
    if not aw:
        out.append("- none")
    for r in aw:
        if r.get("answered"):
            nnn, upd = r["answered"]
            out.append(
                f"- **ANSWERED** — `{r['stream']}` SOW-{r['rev']} was ruled by **RULING-{nnn}** ({upd}); the stream may not have read it. `{r['file']}`"
            )
        else:
            out.append(
                f"- **OPEN** — `{r['stream']}` SOW-{r['rev']}, asked {r['updated']}. Do not build in this direction until ruled; other work is unaffected. `{r['file']}`"
            )
    out.append("")
    out.append(f"**Pre-schema, ungraded ({len(ungraded)}) — invisible to this projection, NOT absent:**")
    if not ungraded:
        out.append("- none")
    for u in ungraded:
        out.append(f"- `{u.get('project', '?')}/{u['stream']}` — {u['files']} file(s), no frontmatter; snapshot needed")
    out.append("")
    out.append(STATE_FENCE_CLOSE)
    return "\n".join(out)


def splice_state_zone(existing, zone, title="the fleet"):
    # Binding 1: rebuild the fenced zone WHOLE; never append, never patch.
    # A fence that is present-but-broken FAILS LOUD rather than guessing.
    if existing is None:
        return (
            f"# STATE — {title}\n\n"
            "<!-- ROADMAP: authored by Master. zeo never touches anything above the fence. -->\n\n" + zone + "\n"
        )
    o, c = existing.find(STATE_FENCE_OPEN), existing.find(STATE_FENCE_CLOSE)
    if o == -1 and c == -1:
        return existing.rstrip("\n") + "\n\n" + zone + "\n"
    if o == -1 or c == -1 or c < o:
        raise ValueError(
            "STATE fence is malformed (open/close missing or inverted) — refusing to write; fix the fence by hand"
        )
    return existing[:o] + zone + existing[c + len(STATE_FENCE_CLOSE) :]
