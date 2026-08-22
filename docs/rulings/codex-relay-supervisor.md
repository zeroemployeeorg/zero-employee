# Sparring ruling — Codex relay supervisor (operator copy)

**ID:** SPARRING-RULING-CODEX-RELAY-SUPERVISOR-2026-08-22  
**Verdict:** CO-SIGN WITH BOUNDARY  
**Authority:** this file is explanatory in the *product* repo. Land the ruling in
the org corpus (`ruling/`) for in-force governance. Vocabulary: [CONTEXT.md](../../CONTEXT.md).

`zeo-master`, `zeo-sparring`, and `zeo-stream` name **seat types** (constructors).
They are not addresses of already-running instances. Inter-seat communication
requires a seat-instance registry, a durable relay ledger, and (for live Codex
threads) an operator-started supervisor — not hierarchical spawn-by-name.

| Adopt | Reject |
| --- | --- |
| Seat instance registry + message ledger | Treating persona names as live addresses |
| Operator-started `zeo relay start` (Model B) | Silent Codex daemon / Model A as org authority |
| Opaque `runtime_address` on the registry | Importing provider session directories (R4) |
| `git worktree` wrappers + branch naming | Sandcastle/container/prompt-expansion engine (R1 remainder) |
| Artifact inbox (`zeo --inbox`) kept | Replacing SOWs/rulings with the message bus |

R1 is reopened only for the supervisor and worktree wrappers named above.
R2 and R4 stay closed. See [docs/non-goals/R1-no-embedded-harness.md](../non-goals/R1-no-embedded-harness.md).
