# CONTEXT — Zero Employee product vocabulary

This glossary is **explanatory**. It does not create a new authority layer.
Rulings decide conflicts; SOWs record governed work; boards are regenerated
views. Terms here exist so an adapter, sandbox, session, run, and receipt
cannot silently change meaning across executors.

Sandcastle (and any other harness) **executes**. Zero Employee **governs intent
and verifies evidence**. Neither impersonates the other.

## corpus

The durable, linted set of governance artifacts (SOWs, rulings, charters,
designs, intakes, learnings, and execution receipts) under a corpus root.

**Avoid:** treating a chat transcript, a board file, or a runtime session
directory as the corpus. Those may be *inputs* or *views*; they are not the
source of truth.

## project

A named work container inside a corpus, typically `projects/<project>/`.
A project may have its own rulings and streams.

**Avoid:** equating a GitHub repository with a project. A host repository may
hold code while the governed project lives in a different corpus repo.

## stream

A sequenced chain of SOWs under one stem (one line of work). Identity is the
stem plus `n:`, not a chat thread and not a seat name.

**Avoid:** calling a Codex/Claude conversation a stream. A conversation is a
runtime session.

## SOW

A Statement of Work: a schema-graded markdown artifact that records intent,
status, ledger claims, and stopping predicates. SOWs are data. They are not
executable prompts.

**Avoid:** treating a prompt file, a GitHub issue, or a board row as a SOW.

## ruling

A durable mandate or precedent. An in-force ruling requires a landing receipt
(`landing_commit`). Bindings and conformance are organizational, not runtime.

**Avoid:** treating an executor timeout, a CI job conclusion, or a sandbox
policy as a ruling.

## design

A pre-decision comparison of approaches (`genre: design`). It sits between
intake (operator intent, no evidence) and a charter or ruling (already decided).

**Avoid:** using "design" as a synonym for architecture diagrams, executor
plans, or SOW status `DESIGN`.

## learning

A diary artifact (`genre: learnings`) recording craft, a gotcha, or a
doctrine candidate. Learnings are not in-force mandates.

**Avoid:** promoting a learning to a ruling by citation density alone.

## intake

Operator-captured intent before it is a SOW. Intake is not evidence that work
ran, completed, or was delivered.

**Avoid:** treating an intake as a SOW, a receipt, or an execution.

## seat type

The *kind* of organizational role (Master, Stream, Sparring, and named
personas such as `zeo-sparring`). A seat type is instructions and authority
shape. A custom-agent name (`zeo-sparring`) is a **constructor**: it selects
configuration used when creating an agent.

**Avoid:** treating a seat type (or an agent persona file) as a persistent
seat instance. Loading `zeo-master.toml` does not mean Master is already
running. Do not treat “ask Sparring” as permission to spawn another agent
of that type when an instance is already registered.

## seat instance

A particular live occupation of a seat type in a round of work, identified in
receipts and the instance registry as `seat_instance` (for example
`sparring-20260822-01`). This is the addressable identity for relay.

**Avoid:** using a GitHub actor, a workflow name, a concurrency group, or a
persona filename as the seat instance. `zeo seat` (GitHub-identity switching)
is a different concept.

## runtime address

An opaque identifier the executor understands: a Codex/Claude session ID, a
Sandcastle run id, a log path. Stored as `runtime_address` on an execution
receipt and on a registered seat instance.

**Avoid:** treating a Codex/Claude session ID as an organizational identity
(stream, seat instance, or ruling). Provider-owned session files stay with
the provider. A runtime address is where a message can be delivered; it is
not a seat.

## instance registry

The ZEO-owned map from seat instance → worktree, branch, opaque runtime
address, write authority, and heartbeat. `zeo relay status` / `resolve`
read this map.

**Avoid:** using Codex custom-agent names, chat titles, or SOW stems as the
registry key.

## relay message

A durable, addressable envelope between two **seat instances** (`zeo relay
send` / `receive` / `ack`). Coordinates live agents. Distinct from the
artifact inbox (`zeo --inbox`): SOWs and rulings remain organizational truth.

**Avoid:** treating a SOW open question, a board row, or a chat line as a
relay message; copying large files into the envelope (use `artifact_refs`).

## supervisor

An operator-started foreground process (`zeo relay start`) that attaches to
persistent provider threads and delivers queued relay messages as follow-up
input. It is not a silent daemon and not a second execution harness.

**Avoid:** a background dispatcher that originates work after the operator
leaves; spawning a destination seat type instead of delivering to the
registered instance.

## execution

One bounded attempt by an external harness to do work against a governed
claim. Evidence of an execution is an **execution receipt**, not a
transcript and not a board row.

**Avoid:** calling the whole agent product, a GitHub Actions job, or a
git commit "an execution" without a receipt.

## iteration

One step inside an execution (a model turn, a tool batch, a retry). Iterations
are executor-internal. Zero Employee does not require them in the corpus.

**Avoid:** equating an iteration with a SOW `n:` increment or a session fork.

## session

A provider-shaped, often mutable conversation or process the harness can
capture, resume, or fork. Sessions are not corpus artifacts.

**Avoid:** importing runtime session files into the canonical corpus; confusing
session fork with branch fork or worktree isolation.

## receipt

Machine-checkable evidence. Distinct kinds:

- **landing** (`landing_commit` on a ruling/charter) — the artifact is in force
- **closure** (`requested_by` / `resolved_by`) — a question was answered
- **execution receipt** (JSON) — what a harness claims happened
- **delivery** — a commit is on a named remote (`remote_contains` verified)

**Avoid:** treating a completion chat line, a CI green check, or a local SHA
as a receipt of delivery.

## board / view versus source artifact

A board (`STATE.md`, `stream-index.md`, `--board`) is a **regenerated view**.
A source artifact is the markdown/JSON file in the corpus chain.

**Avoid:** committing boards as truth; treating a board row as the artifact
it points at. A board row is a derived pointer, not truth.

## binding

A ruling's `binds:` list: which streams or scopes must acknowledge it.

**Avoid:** treating a GitHub label, a workflow `concurrency:` group, or a
sandbox bind-mount as a binding.

## acknowledgement

A stream citing a bound ruling in its own bytes. Acknowledgement is not
conformance and not completion.

**Avoid:** `conformance: acknowledged` as if it were a behavioral predicate.

## conformance

A checkable predicate on behavior (the ruling's `conformance:` field, or an
executable test named by a SOW). Organizational conformance is independent of
sandbox isolation.

**Avoid:** claiming sandboxing as sufficient governance, or a valid SOW as
proof of isolation.

## landing

The act of putting a ruling or charter in force (`landing_commit: self` or a
SHA). Landing is not delivery of product commits.

**Avoid:** calling a local commit "landed on trunk" without a pull request on
a protected trunk.

## delivery

A produced commit that a **named remote contains**, with verification evidence
on the execution receipt. A commit hash alone is production, not delivery.

**Avoid:** reporting delivery from `git log` in a worktree without
`git branch -r --contains <hash>` (or equivalent) against the real remote.

## host repository

The git repository where code is edited (may be a worktree). May or may not
be the governed corpus.

**Avoid:** assuming the host repo is the corpus root.

## governed repository

The repository (or path) whose mutation is under Zero Employee doctrine:
protected trunk, session-branch cadence, one PR per session unless a later
ruling says otherwise.

**Avoid:** treating any clone or sandbox checkout as governed.

## corpus root

The directory containing `claude-md/CLAUDE.md` (or `ZEO_SOWS_ROOT`). Discovery
walks up from cwd. This package repo is **not** a corpus root.

**Avoid:** using this tooling repository's tree as if it were an org corpus.

## worktree

A git working tree (possibly linked). Exclusive ownership of a live execution
is **not** implied by a worktree existing. A branch name is not a concurrency
lock.

**Avoid:** equating worktree isolation with filesystem sandbox isolation, or
with a session fork.

## branch

A git ref. An execution that mutates code should own an explicit branch.
Session-branch cadence (one branch per session, one PR at the end) is
organizational. Executor branch strategy (`head` / `merge-to-head` / `branch`)
is a capability claim, not a seat.

**Avoid:** using a label, prompt, or seat name as the lock; using a GitHub
concurrency group as organizational identity; treating `git push --force` as
lease semantics.

## Cross-project distinctions (Zero Employee vs Sandcastle)

| Term | Zero Employee | Sandcastle (executor) |
| --- | --- | --- |
| seat type / persona | organizational authority | agent provider invocation profile |
| runtime address | opaque evidence on a receipt | session id the provider can resume |
| sandbox | isolation *claim* on a capability manifest | process/filesystem lifecycle |
| receipt | governed JSON / landing / closure | run result + logs |
| fork | not a git or worktree fork | session-only unless proven otherwise |

An `AgentProvider` knows how to invoke and parse an agent CLI. It does not know
whether the caller is Master, Stream, or Sparring.
