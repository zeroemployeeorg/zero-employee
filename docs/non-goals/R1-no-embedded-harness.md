# R1 — Do not embed Sandcastle or reimplement it in Python

**Rejected capability:** Docker/Podman/Daytona/Vercel lifecycle, agent subprocess
orchestration, session copying, prompt expansion, terminal display, or a worktree
engine inside `zero_employee` core.

**Why:** That would create a second execution product, a heavy dependency surface,
and two owners for execution correctness. Zero Employee owns durable intent and
evidence; Sandcastle (or another harness) owns invocation.

**Seam:** `ExecutorCapabilities`, `ExecutionReceipt`, optional
`zero_employee.adapters.sandcastle` (JSON fixtures only).

**Reopen if:** a dedicated ruling authorizes a companion package that is not core,
with its own threat model and release surface.

**Prior:** SPARRING-RULING-SANDCASTLE-ADOPTION-2026-08-22 §R1.
