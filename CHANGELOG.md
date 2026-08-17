# Changelog

## [0.3.2] - 2026-08-17

### Fixed
- **`--inbox <stream>` could not deliver a proactive, fleet-binding ruling.** It was
  built entirely from `awaiting_ruling()` — a question-answer channel keyed on a
  stream's own `status: RULING-REQUESTED` and a ruling's `requested_by` citing that
  SOW back. A ruling that binds via `binds: [all-streams]` (or a direct stream id)
  with no `requested_by:` naming the stream at all — Master ruling something
  fleet-wide, nobody having asked — was real, in force, and binding, and was
  invisible to that stream's inbox by construction. MEASURED live: a Master boot in
  a real corpus (ducktyper-ai/org) read `--inbox`'s own doctrine literally and
  correctly reported the tool's relay duty as structurally unmet, not merely quiet;
  reproducing the report against the real corpus surfaced two real, previously
  undelivered rulings. Added `binding_rulings_for_stream()` (reuses the existing
  `binds:` resolution machinery `check_binds`/`build_stream_index` already provided)
  and a new BINDING RULINGS section in `--inbox`'s output: every ACTIVE/AMENDED
  ruling binding this stream, asked or not, with ACKNOWLEDGED/NOT-YET-CITED per the
  corpus's own existing "citation is the receipt" doctrine — no new ack field
  invented. `--triage` is intentionally unchanged (a different question: what does
  Master owe, not what binds a stream); whether it should also surface unacknowledged
  fleet rulings is a separate, open question.
- **The shipped `zeo-stream.md` agent template referenced a file that has never
  existed: `roles/BOOT-LITTLE-CLAUDE.md`.** The real file is `roles/BOOT-SUBAGENT.md`
  — `zeroemployeeorg/org`'s own canonical `CLAUDE.md` already corrected this exact
  ghost-precedent in prose on 2026-08-16, but the package template `zeo equip`
  actually writes into every work repo was never updated to match, so every
  `zeo equip` since v0.1.7 carried the stale reference forward. A missing `@import`
  degrades to a silent HTML comment rather than an error, so a booting stream seat
  got a quietly doctrine-less boot instead of a loud failure. Fixed; added a
  regression test (falsified first — confirmed it fails against the old content).

## [0.3.1] - 2026-08-17

### Fixed
- **`pyproject.toml` claimed `"Typing :: Typed"` in its PyPI classifiers, but
  `src/zero_employee/py.typed` genuinely did not exist** — confirmed by `find` and by
  building the wheel and checking its contents. Any downstream `mypy`/`pyright` user
  silently got untyped stubs regardless of what the classifier claimed. Added the
  marker file, verified it ships in a real build, added a regression test that fails
  without the file and passes with it.

### Added
- **`SECURITY.md`, `CODE_OF_CONDUCT.md`:** standard OSS community-health files
  (Contributor Covenant 2.1 for the latter) — previously absent.

### Changed
- **`README.md`:** real above-the-fold pitch, a live CI status badge, a table of
  contents (every anchor checked against GitHub's actual heading-slug algorithm — three
  were silently broken), and a corrected command table. Dropped a stale claim that
  `sow-lint` is a "permanent alias" for `zeo` — it is not a registered script entry
  point (`[project.scripts]` only declares `zeo`), confirmed by attempting to run it.
- **`CONTRIBUTING.md`:** rewritten with a real local-setup walkthrough, the actual
  tracked-hooks mechanism, test conventions, and a PR checklist, replacing an 11-line
  stub.

## [0.3.0] - 2026-08-17

### Added
- **Fifth genre: `design` (RULING-286):** A real, graded document shape for weighing 2+
  approaches with stated evidence and tradeoffs before committing to a direction — sitting
  between `intake` (operator-only, no evidence required) and `charter` (already-decided,
  binds work). Wired into the real `discriminate()`/`lint_file()` dispatch alongside
  `charter`/`intake`/`learnings`, never falling through to the genre-unknown SKIP path or
  silently inheriting SOW grading rules. Requires an id, `status:` in
  `OPEN|DECIDED|SUPERSEDED`, a `QUESTION:` section, **2 or more `APPROACHES:` entries**
  (fewer than two fails — that is a decision already made, not a comparison), and a
  mandatory `NOT DECIDING HERE:` section (present even when empty, mirroring `intake`'s own
  `NOT THIS:` scope-fence discipline). `DECIDED`/`SUPERSEDED` status requires
  `decided_into:` naming the charter or ruling it became. Closes the same way `intake`
  closes: a Master's `requested_by:` citation on the successor charter/ruling is the
  receipt, no separate acknowledgment field.
- New authoring skill: `authoring/design-authoring-SKILL.md` — when to use the genre (and,
  as importantly, when not to: an obvious call still just becomes a charter directly), the
  form, and its closure mechanic.

## [0.1.7] - 2026-08-10

### Added
- **Orientation OS (`zeo` / `zeo orient [--json]`):** Replaced static usage dumps on bare `zeo` with a contextual dashboard for humans and structured JSON (`protocol_version: 1`) for agents.
- **Progressive Help (`zeo help ` / `zeo help --all`):** Curated progressive documentation topics (`intake`, `sow`, `rulings`, `doctrine`, `corpus`, `hooks`, `cost`).
- **Creation Router (`zeo new`):** Interactive prompt for creating Intakes, SOWs, or Projects without needing hand-written syntax.
- **Active Work Navigator (`zeo work [context]`):** Surfaces active SOWs, waiting items, recently touched files, and open intakes across corpus or stream scopes.
- **Next-Action Determination (`zeo next [--json]`):** Clear prioritization policy that recommends the immediate next step for human operators and autonomous agents.
- **Subcommand Aliases:** Canonical CLI verbs (`zeo board`, `zeo triage`, `zeo digest`, `zeo index streams`, `zeo index rulings`, `zeo mint`) alongside legacy flag forms.


## [0.1.6] - 2026-08-10

### Added
- **Intake Capture (`zeo intake new` / `open` / `edit`):** Frictionless capture of intent before identity is known. Supports positional titles, CLI flags, `$EDITOR` templates, raw stdin, and JSON specs.
- **Grounded Promote (`zeo intake promote`):** High-assurance promotion of intake items into governed SOWs, grounded in validated repository evidence and proposals stored under `.zeo/intake-proposals/`.
- **Mission & Context Protocol (`zeo intake mission` / `context`):** Structured JSON retrieval protocol for coding agents to investigate codebase context before submitting grounded proposals.
- **Intake Schema & Status Normalization:** Lightweight intake grader with canonical write status enum (`OPEN`, `PROMOTED`, `DUPLICATE`, `REJECTED`, `PARKED`) and read normalization for legacy statuses (`CHARTERED`, `DECLINED`, `SUPERSEDED`).
- **Scaffold Doctrine Update:** Embedded core intake doctrine principles in `scaffold_templates/claude-md/CLAUDE.md`.


## [0.1.5] - 2026-08-09

### Added
- **SOW Authoring Ergonomics (`zeo sow new / set / draft`):** ZEO now owns Rev-17 frontmatter serialization, numbering, and transactional writes so agents only supply semantic values without hand-writing YAML.
- **`zeo doctor` CLI Command:** Added structural health checking and automatic repair filters for working trees and SOW drafts.
- **Transactional Frontmatter Validation:** Rejects improper frontmatter in body content prior to file creation or modification, leaving zero partial artifacts on failure.


## [0.2.0] - 2026-08-17

### Added
- **Stream Priority (`zeo --priority [path]`):** Nutzwertanalyse (German
  weighted-utility analysis) ranking of every `OPEN`/`PAUSED`/`BLOCKED`
  stream, so a Master session has a stated, revisable reason for which
  stream gets the next session's tokens instead of `--triage`'s age-only
  order. Four criteria — Dringlichkeit (urgency), Impact (from rulings'
  `binds:`), Restaufwand (remaining cost in tokens, denominator), Risiko —
  scored in tokens throughout, never currency. Prints top-N funded streams
  plus next-M Opportunitätskosten (opportunity-cost) near-misses with a
  stated Nutzwert delta, so funding one stream is a visible decision not
  to fund another this round, not a hidden one.
- **Repo Equip (`zeo equip <repo> [--force|--diff]`):** Installs the
  ALWAYS-tier `.claude/` governance files (`settings.json` with a full
  deny list, a behavior-verified trunk-guard hook, `CLAUDE.md`, seat
  agent definitions) plus `.claude/hooks/check-trunk-guard.sh` into a
  work repo. Never clobbers an existing file by default (reported
  `kept`); `--force` overwrites; `--diff` previews a unified diff and
  writes nothing. Content resolves through a 4-level precedence chain
  (`$ZEO_TEMPLATES_DIR` → `~/.config/zeo/templates/` → packaged
  default), and every written file is stamped `UPSTREAM-SHA: <sha256>`
  of the content actually written, so a deliberate user override reads
  as current rather than perpetually stale.
- **Governance-Path Gate:** `zeo hooks pretooluse-git` now WARNs (never
  blocks) when a pending commit touches a governance-class path
  (`.claude/**`, `CLAUDE.md`, `tools/hooks/**`) with no SOW-shaped
  citation in the commit message — closing the gap where hand-copied
  `.claude/` configs drifted across repos with zero record. Three
  uncited warnings from one author in one session escalate, naming the
  incident explicitly.
- **Cold Start (`zeo cold-start <repo-path> [--sows-root PATH] [--project NAME]`):**
  A bounded, mechanical Ist-Aufnahme (as-is survey) for a freshly-equipped
  repo with no SOW/ruling history yet — identity, existing-gate presence,
  docs surface, TODO/FIXME/issue scan, and secrets presence-only checks,
  each item's evidence citing the exact command and its literal output.
  Writes one `FINDING`/`RECON` SOW into the SOWS repo only — zero
  commits, zero writes into the surveyed work repo.
- **`open_questions:` schema field** (RULING-268): a stream's own list of
  outstanding questions, each independently resolvable via `resolved_by:`
  without forcing a whole-SOW status flip. `--triage`'s NEEDS MASTER
  count and `--inbox`'s rollup both read this field directly.
- **Intake capture + grounded promote:** `zeo intake new|open|doctor|context|mission|propose|promote`
  (and `zeo intake "title"`). Capture is frictionless; promotion requires evidence-backed
  proposals from a coding agent. ZEO validates receipts, allocates SOW identity, and writes
  Rev-17 frontmatter. Alias: `zeo sow from-intake`.
- **SOW authoring ergonomics:** `zeo sow new|set|add|remove|draft` and `zeo doctor[--changed]`.
  ZEO serializes Rev-17 YAML, allocates `n`/filenames, validates transactionally, and (for draft)
  runs an Ollama body-only peer loop. Agents supply semantic values; ZEO owns governance syntax.
- Shared `sow_authoring` write substrate + `ollama_client`; scaffold/mint reuse the serializer.
- `zeo init` scaffolds `intake/` and gitignores `.zeo/` proposal cache.
- Tracked `.githooks/pre-commit` (format+lint, ~0.15s) and `.githooks/pre-push`
  (full pytest suite) via `core.hooksPath`, plus CI extended beyond bare pytest.

### Changed
- Canonical SOW filenames zero-pad `n` (`SOW-01`); `zeo scaffold` wraps `sow new`.
- Intake status vocabulary: `OPEN|PROMOTED|DUPLICATE|REJECTED|PARKED` (legacy
  `CHARTERED|DECLINED|SUPERSEDED` accepted as aliases on read).
- `nutzwertanalyse()`'s Impact criterion reads rulings' `binds:` field directly
  (a structured list already ~6.7x the coverage of the original `<stream>#<n>`
  citation-graph walk it replaced) and no longer adds a flat `issue_first`
  bonus — measured at 99.7% of the corpus, contributing zero real
  discrimination and diluting the one real, varied signal.
- `model_rates.toml`'s `default_model` follows the current model catalog
  (was pinned to an older generation while the table already carried
  correct newer rates unused underneath it); three current model IDs added.
- The packaged `.claude/settings.json` and trunk-guard hook templates are
  the real, behaviorally-proven bytes (full deny list; hook resolves its
  own repo from script location, not cwd; gates trunk landings rather
  than forbidding them; exempts abort/continue/skip/quit) — no longer the
  `{"permissions": {}}` stub. The wheel's `force-include` template list
  (silently non-updating for new files) is removed; hatchling's own
  default package walk already ships everything, guaranteed by a test.

### Fixed
- **`--spec -|<path>` crashed with a raw traceback on malformed input** across all
  four call sites (`sow new`, `intake new`, `intake propose`, `intake promote`).
  Now fails the same clean way everywhere: bad JSON, missing file, or
  valid-JSON-but-not-an-object.
- **`DoneWhenItem` accepted a `type`/field mismatch silently**, rendering the
  literal string `` `None` → exit 0 `` into a shipped SOW body when a
  `type: "command"` item only set `criterion`. Now rejected at validation time
  with a message naming the likely intended fix.
- **`restaufwand()` crashed on an n-collision** (`revs.sort()` compared tuples
  with a `rest` field that could be `int` or `None`); now sorts by revision
  number only.
- **`_triage`'s `needs_master` count could show a stream with 0 open questions**
  when its `status` field was stale but its actual open question was already
  resolved; now derived from the same already-correct open-question list
  `--triage` prints, not a separate raw status scan.
- **A decorated `resolved_by:` target** (e.g. `"ruling: 272 (backfilled ...)"`)
  **silently reported a real, landed ruling as absent** instead of resolving
  it; the leading ruling number is now extracted before lookup.
- **A `VOIDED`/`SUPERSEDED`/`STALE` SOW permanently blocked its own `n:` slot**
  from ever being reused, and a `VOIDED`/`SUPERSEDED` ruling permanently
  failed the ruling-collision gate; both now correctly exclude tombstoned
  revisions. A later live SOW's own `supersedes:` also now reconciles an
  earlier n-collision instead of leaving it standing.
- SOW n-collision detection is wired into the real tracked pre-commit hook,
  not just the standalone linter.
- A staged **deletion** of a generated board file (`STATE.md`,
  `stream-index.md`) is now let through by pre-commit as the intended
  untracking act, rather than treated the same as an unwanted modification.
- `latest_rev_of` now breaks a tie on shared `n` by revision letter then
  date, rather than an unstable/arbitrary order.
- Flaky `test_digest_matches_the_real_bash_script_on_the_same_commit_range`:
  the bash and Python digest header each stamp their own independent
  timestamp a subprocess apart, occasionally differing by a minute
  (`07:18` vs `07:19`) and failing the byte-identical comparison. Test now
  normalizes the header timestamp out before comparing, the same way it
  already normalizes ruling-citation differences.
- `make setup`'s dev-dependency install was a silent no-op (`--python` +
  unknown-extra fallback never triggered under `uv`); now installs the
  `dev` dependency group explicitly.
- `anthropic_count_tokens` (used by `--kosten`/`--repo-cost --count-via anthropic`)
  now fails loudly with both remediation paths named when no credential is
  found, instead of an opaque error; `--api-key-env <VARNAME>` lets a caller
  whose credential lives under a non-default variable name use it.

## [0.1.4] - 2026-08-09

### Added
- **Zero-Friction Git Flow:** `zeo hooks install` now automatically configures a `zeo-auto` git merge driver to silently bypass `STATE.md` and `stream-index.md` conflicts.
- **Auto-Regeneration:** Pre-commit hooks now automatically rebuild and stage `STATE.md` and `stream-index.md` on every commit, ensuring the board is always accurate without manual intervention.

### Changed
- Refactored `pre-commit` into a thin wrapper pattern that delegates execution entirely to the `zeo` binary, ensuring git hooks update automatically when the Python package is upgraded.


## [0.1.3] - 2026-08-09

### Added

- Thin-wrapper corpus hooks: installed stubs only `exec zeo hooks <subcommand>`; gate and
  orientation logic live in the package so upgrades update students without reinstalling
  script bodies (`pre-commit`, `session-start`, `stop`, `pretooluse-git`).
- `zeo hooks pre-commit|session-start|stop|pretooluse-git` runners.
- Automatic `.gitignore` entries for `STATE.md` and `stream-index.md` from `zeo init` and
  `zeo hooks install` (boards are local views, not shared git artifacts).

### Changed

- Pre-commit unstages generated boards if staged, regenerates them locally (fail-open), and
  never `git add`s them — beginners no longer hit `STATE.md` merge conflicts.
- Docs: getting-started recommends hooks install; boards documented as gitignored local views.

### Migration (existing corpora that still track boards)

```bash
git rm --cached STATE.md stream-index.md
zeo hooks install
```

## [0.1.2] - 2026-08-09

### Added
- Parallel `ThreadPoolExecutor` pre-commit gate checking in `.git/hooks/pre-commit` to prevent timeouts on batch commits.
- Deterministic Rev 17 frontmatter injection support for pre-schema SOWs.
- Automatic `done_when` and `restaufwand` frontmatter enforcement for active working SOWs.

### Changed
- Improved `-RevN` suffix validation and stream identity resolution in `zeo --commit-check`.
- Canonical filename promotion support across active project workstreams.


All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] — 2026-08-09

### Added

- Document `zeo init`, `zeo scaffold`, and `zeo bridges` (corpus/project scaffolding with
  opt-in IDE bridges). These verbs shipped on the 0.1.0 surface but were omitted from the
  prior changelog notes.
- Local `@import "rel/path"` doctrine expansion via `read_doctrine()` (airgap-safe; no HTTP).
- Packaged scaffold templates and personas (`zeo-architect` / `zeo-claimant` / `zeo-verifier`).
- OIDC trusted-publishing workflow (`.github/workflows/publish.yml`) and release docs.

### Changed

- README rebrand with command reference for scaffold verbs.
- Richer PyPI metadata (authors, classifiers, project URLs).
- Release docs point at the `zeroemployeeorg/zero-employee` GitHub org.

## [0.1.0] — 2026-08-08

### Added

- First public release of `zero-employee` (CLI: `zeo`, alias: `sow-lint`).
- Import package renamed to `zero_employee` for a consistent public surface.
- Session/repo cost proxies (`--repo-cost`, `--session-cost`) with dated model rates.
- `--resync-apply` and `zeo hooks install` for doctrine re-derive and hook templates.
- Honest no-corpus failure for `--board` / discovery verbs.
- Packaged empty grandfather manifest; corpora may override via
  `tools/doctrine/grandfather_manifest.toml` or `ZEO_GRANDFATHER_MANIFEST`.

### Changed

- Public wheel sanitized: identity strings redacted; internal ruling/stream citations
  generalized for open-source distribution.

### Notes

- Dependencies: `pyyaml`, `pydantic`, `tiktoken` (intentional; required by shipped features).
