# R1 — Do not embed Sandcastle or reimplement an execution harness

**Rejected capability:** Docker/Podman/Daytona/Vercel lifecycle, session
directory copying, prompt expansion, terminal display, or a Sandcastle-shaped
worktree/sandbox engine inside `zero_employee` core.

**Still rejected:** a silent resident daemon that originates work after the
operator leaves (RULING-351). `zeo relay start` is a foreground operator
process; when the human stops it, delivery stops.

**Narrow reopen (2026-08-22):** core may include (1) an operator-started
relay supervisor that attaches to provider threads by **opaque**
`runtime_address` and delivers follow-up input, (2) `git worktree`
add/list/remove wrappers recorded on the instance registry. These are
coordination and git isolation, not a second execution product.

**Why the original reject stands:** copying Sandcastle would create two
owners for execution correctness. Zero Employee owns durable intent,
evidence, and **addressing**; the provider owns invocation inside a thread.

**Seam:** `ExecutorCapabilities`, `ExecutionReceipt`, `zeo relay`,
`zeo workspace`, optional `zero_employee.adapters.sandcastle` (JSON fixtures
only), `zero_employee.runtimes.codex` (capability probe + follow-up adapter).

**Reopen further if:** a dedicated ruling authorizes a companion package that
is not core, with its own threat model and release surface, for containers or
prompt expansion.

**Prior:** SPARRING-RULING-SANDCASTLE-ADOPTION-2026-08-22 §R1;
SPARRING-RULING-CODEX-RELAY-SUPERVISOR-2026-08-22.
