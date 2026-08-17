# Tutorial: from an idea to a ruled, tracked SOW

`docs/getting-started.md` shows the individual commands. This walks through
**why** you'd use them, in order, on one real example — from capturing a raw
idea, through grounding it in real code, to a design fork getting answered by
a ruling, to `zeo --priority` telling you what to work on next. Every command
below was run for real against a scratch corpus while writing this doc; the
output shown is real output, not invented.

If you haven't installed `zeo` yet, see [Installation](../README.md#installation)
and [Getting started](getting-started.md) first.

## The scenario

You're the operator (or an agent working on your behalf) for a small
organization. Someone needs a health-check endpoint added to a service. You
don't yet know the exact implementation — you know the *problem*. That's
what `intake` is for.

## 1. Capture the idea — no YAML, no ceremony

```bash
mkdir my-org && cd my-org
zeo init
zeo intake "add a health-check endpoint to the payments service"
```

```
Created intake/2026-08-17-add-a-health-check-endpoint-to-the-payments.md
```

Open that file. It's four sections, on purpose — this genre exists so
capturing intent costs less than typing it into chat and losing it:

```yaml
---
genre: intake
id: 2026-08-17-add-a-health-check-endpoint-to-the-payments
intake: 2026-08-17-add-a-health-check-endpoint-to-the-payments
created: '2026-08-17'
updated: '2026-08-17'
status: OPEN
---

WHAT:
add a health-check endpoint to the payments service

WHY:


DONE WHEN:


NOT THIS:


CONTEXT:
```

Fill in `WHY`, `DONE WHEN`, `NOT THIS`, `CONTEXT` — as a human would, in
your own words. `NOT THIS` is the load-bearing line: it's the scope fence
that stops later work from quietly growing into something nobody asked for.

```
WHY:
the load balancer has no way to detect a wedged pod today; we've had two
silent outages this quarter where traffic kept routing to a dead instance

DONE WHEN:
GET /healthz returns 200 with {"status":"ok"} when the DB connection pool
is healthy, 503 otherwise; load balancer config updated to use it

NOT THIS:
not a full readiness/liveness split, not metrics/tracing -- just the one
endpoint the load balancer needs right now

CONTEXT:
payments-service repo, FastAPI, already has a /metrics endpoint we can
pattern-match the routing off of
```

## 2. Investigate — `mission` asks the questions, you (or your agent) answer them

An intake is *unconverted* intent — it doesn't become a trackable unit of
work until something grounds it in the actual codebase. `zeo intake mission`
prints the standard investigation checklist for whoever picks this up (a
person, or a coding agent):

```bash
zeo intake mission intake/2026-08-17-add-a-health-check-endpoint-to-the-payments.md
```

```
Mission for intake/2026-08-17-add-a-health-check-endpoint-to-the-payments.md
Goal: Determine the smallest robust implementation needed to satisfy this intake.
repo_head: d08aadc9a4efdbc2670b37c4156622e149f71916
Questions:
  - What existing implementation should be reused rather than duplicated?
  - What current behavior conflicts with the requested invariant?
  - Which public CLI surfaces need to change?
  - Which tests prove the invariant?
  - What existing callers must remain compatible?
  - What is the smallest change that satisfies WHAT: add a health-check endpoint to the payments service
Submit: zeo intake propose intake/2026-08-17-add-a-health-check-endpoint-to-the-payments.md --spec -
Then:   zeo intake promote intake/2026-08-17-add-a-health-check-endpoint-to-the-payments.md
```

`repo_head` is read from the corpus's own git HEAD automatically — you don't
type it.

## 3. Ground it — `propose` takes a JSON spec, not prose

This is the step most people get wrong on their first try, so it's worth
being explicit: **`--spec` takes a JSON object**, not free-text notes. The
mission's own questions read like they want prose answers — they don't.
Build the spec as JSON, citing real file paths and real line ranges from the
actual repository (an evidence claim `zeo` can't verify against a real file
is rejected, on purpose — this is what keeps a proposal *grounded* rather
than aspirational).

```bash
HEAD_SHA=$(git rev-parse HEAD)
cat << EOF | zeo intake propose intake/2026-08-17-add-a-health-check-endpoint-to-the-payments.md --spec -
{
  "repo_head": "$HEAD_SHA",
  "observations": [
    {
      "fact": "The /metrics endpoint's router pattern is the closest existing analog to reuse.",
      "evidence": {"path": "app/routes/metrics.py", "line_start": 1, "line_end": 9}
    }
  ],
  "implementation": {
    "problem": "The load balancer cannot detect a wedged pod today; two silent outages this quarter traced to traffic routing to a dead instance.",
    "invariant": "GET /healthz returns 200 with {\"status\":\"ok\"} when the DB connection pool is healthy, 503 otherwise.",
    "approach": [
      "Add app/routes/health.py registering GET /healthz, reusing the DB pool health-check helper the metrics endpoint already calls.",
      "Register the new router in app/main.py beside the existing /metrics router."
    ],
    "done_when": [
      {"type": "command", "command": "pytest test_health_endpoint.py", "expect": "2 passed (200 when pool healthy, 503 when not)"}
    ]
  },
  "destination": {"project": "payments", "stream": "health-check-endpoint", "title": "Add a health-check endpoint to the payments service"}
}
EOF
```

```
✓ proposal saved .zeo/intake-proposals/2026-08-17-add-a-health-check-endpoint-to-the-payments.json
  observations: 1
```

**A `done_when` item's fields must match its `type`.** `type: "command"`
needs a non-empty `command` (the command to run); `type: "inspection"`
needs a non-empty `criterion` (what to check by reading, not running). Mixing
them — `type: "command"` with only `criterion` set — is rejected at this
step with a message naming the mismatch, rather than silently accepting a
half-specified item that would render `` `None` `` into the shipped SOW
later. If you see that error, it means exactly what it says: pick the field
that matches the type.

**What gets rejected, and why** — three things you'll likely hit on a first
attempt, all deliberate:

| You did | `zeo` says | Why |
| --- | --- | --- |
| Cited a file that doesn't exist | `evidence path missing: <path>` | An observation must be grounded in a real file, not an assumption |
| Cited a line range past EOF | `line range N-M out of bounds for <path> (K lines)` | Same principle, at the line level |
| Left `repo_head` stale (from before your last commit) | proposal rejected as stale | The proposal must describe *this* state of the repo, not an earlier one |

## 4. Promote — the proposal becomes a real, lintable SOW

```bash
zeo intake promote intake/2026-08-17-add-a-health-check-endpoint-to-the-payments.md
```

```
✓ allocated n=1
✓ rendered Rev 17 frontmatter
✓ filename canonical
✓ body assembled from proposal
✓ lint passed
✓ written

projects/payments/sow/health-check-endpoint/health-check-endpoint-SOW-01-add-a-health-check-endpoint.md

✓ intake marked PROMOTED
```

Open the result. Everything in it traces back to something you or your agent
actually asserted in step 3 — the `done_when` line is the literal command
and expectation from the spec, the "Grounded observations" section cites the
real file and line range:

```yaml
---
sow: health-check-endpoint
n: 1
schema_rev: 17
project: payments
status: DESIGN
lifecycle: DESIGN-MEMO
created: '2026-08-17'
updated: '2026-08-17'
genre: sow
done_when: '`pytest test_health_endpoint.py` → 2 passed (200 when pool healthy, 503
  when not)'
restaufwand: 1
sow_repo: example-org/org
work_repo: example-org/payments
requested_by: intake:2026-08-17-add-a-health-check-endpoint-to-the-payments
---
```

The original intake file is now marked `status: PROMOTED` — it isn't
deleted, it's the permanent record of where this work started.

## 5. See where things stand

```bash
zeo --triage .
```

```
BOARD TRIAGE - 1 streams across 1 projects

INTAKE - unconverted operator intent, OPEN only (0; doctrine item 3 - a projection, not evidence, doctrine)

NEEDS MASTER - a ruling is owed (0 streams, 0 open questions)

NEEDS A SUCCESSOR - ruled, maybe unread (0; 0 suppressed as already-acted per doctrine)

PAUSED - held/handover, waiting to be picked up (0)

BLOCKED - external obstruction (0)

DARK - invisible to the board; the migration burn-down meter (doctrine): 0

RESTING - done, not your attention: 0 streams (still-working DRAFT/DESIGN/PROGRESS: 1)
```

`zeo --triage` is the fast, unopinionated worklist. `zeo --board` regenerates
`STATE.md`, a local navigation file (gitignored — never commit it, it's
derived and can go stale the moment you look away).

## 6. A design fork — escalate, don't guess

Say the work needs a decision only a human (or a Master session) should
make: should the new endpoint check the *same* DB pool health the existing
`/metrics` endpoint checks, or maintain its own? Set the SOW's status to
signal it's waiting on that answer:

```bash
zeo sow set projects/payments/sow/health-check-endpoint/health-check-endpoint-SOW-01-add-a-health-check-endpoint.md \
  status RULING-REQUESTED
```

```bash
zeo --triage .
```

```
NEEDS MASTER - a ruling is owed (1 streams, 1 open questions)
   payments/health-check-endpoint SOW-1  (2026-08-17)
     OPEN  health-check-endpoint SOW-1  asked 2026-08-17
```

The question is now visible, fenced to exactly this stream — nothing else
stops moving because of it.

## 7. Answer it — a ruling, filed and cited back

A ruling is a binding decision, filed as its own document. Mint the next
free number, then write the ruling:

```bash
zeo --mint ruling .
```

```
MINT: next ORG-SCOPE ruling id = 1
  ...
  NOTE: this is the next free ruling id AS OF THIS DISK READ — NOT reserved or
  locked. A peer minting concurrently can claim the same one; detected downstream.
```

```yaml
# ruling/RULING-1-healthz-uses-the-existing-db-pool-helper.md
---
ruling: "1"
title: "The /healthz endpoint reuses the existing DB pool health-check helper..."
authority: master
scope: project:payments
status: ACTIVE
requested_by: "health-check-endpoint#1"
created: '2026-08-17'
updated: '2026-08-17'
landing_commit: self
binds: [health-check-endpoint]
genre: ruling
---

# RULING-1 — reuse the existing DB pool helper

Ruled: /healthz calls the same DB pool health-check helper /metrics already
imports, rather than a second, parallel health-check abstraction.
```

**Filing the ruling is not the same as delivering it.** The asking SOW needs
its own receipt — a `resolved_by` field naming the ruling, in the *bare*
form `"ruling: N"` (a decorated string like `"ruling: 1 (see also...)"` will
fail to resolve — the field is machine-parsed, keep prose in the ruling
itself):

```bash
zeo sow set projects/payments/sow/health-check-endpoint/health-check-endpoint-SOW-01-add-a-health-check-endpoint.md \
  resolved_by "ruling: 1"
```

```bash
zeo --triage .
```

```
NEEDS MASTER - a ruling is owed (0 streams, 0 open questions)
```

Notice the SOW's own `status:` field is *still* `RULING-REQUESTED` — that's
correct, not a bug. It's the historically accurate record of what the status
was when the question was asked. `resolved_by` is what closes the question;
`--triage` reads both together, not `status:` alone.

## 8. What should get the next session's attention?

Once you have more than one stream competing for the next block of work,
`zeo --priority` ranks them — a [Nutzwertanalyse](../README.md#stream-priority-nutzwertanalyse)
(German: utility-value analysis) over urgency, impact, remaining cost, and
risk, in tokens, never currency:

```bash
zeo --priority .
```

```
NUTZWERTANALYSE (RULING-279) - 1 rankable stream(s)
  Nutzwert = (0.30*Dringlichkeit + 0.30*Impact + 0.15*Risiko) / Restaufwand_tokens

FUNDED - top 1 for the next session's tokens:
  1. health-check-endpoint        nutzwert=0.750000  dringlichkeit=0d  impact=0  risiko=0  restaufwand~1tok [ESTIMATE-LOCAL-MEDIAN]

OPPORTUNITÄTSKOSTEN - next 0 near-miss stream(s), NOT funded this round:
  (none - fewer than top_n+near_m rankable streams)
```

With more streams in flight, this is where the near-miss list earns its
keep: it names what you're *choosing not to fund this round*, not just what
you picked.

## What you just did, and why it's shaped this way

- **Intake before identity.** You captured intent before deciding which
  project or stream owns it — the four-line form costs less than losing the
  idea entirely.
- **Grounded, not asserted.** A proposal that cites code has to cite *real*
  code — a wrong path or a stale line range is rejected before it becomes a
  SOW that lies about what it's based on.
- **The SOW is the durable record.** Everything downstream — `--triage`,
  `--priority`, a future agent picking this up — reads the SOW's frontmatter,
  never a chat transcript.
- **A design fork is escalated, not guessed.** `status: RULING-REQUESTED`
  fences one direction without stopping everything else.
- **Delivery is a separate act from filing.** A ruling that exists on disk
  but isn't cited back by the asking SOW is a decision nobody received —
  `resolved_by` is what closes the loop.

## Next

- [Command reference](../README.md#command-reference) — every verb, one line each.
- [Stream Priority](../README.md#stream-priority-nutzwertanalyse) — the full Nutzwertanalyse design.
- [Getting started](getting-started.md) — bridges, hooks, the shorter version of steps 1–5.
