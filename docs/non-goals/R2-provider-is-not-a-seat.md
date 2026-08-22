# R2 — Do not equate an agent provider with a Zero Employee seat

**Rejected capability:** Treating Sandcastle's `AgentProvider` (CLI construction,
stream parse, usage extraction) as Master, Stream, or Sparring authority.

**Why:** A provider knows how to invoke a CLI. It does not know the seat, the
corpus, or what may be decided.

**Seam:** Receipts carry `seat_type` and `seat_instance` separately from
`agent_provider` and `runtime_address`.

**Reopen if:** a ruling binds a specific provider version to a seat type *and*
a live probe shows the provider enforces that seat's tool allowlist.

**Prior:** SPARRING-RULING-SANDCASTLE-ADOPTION-2026-08-22 §R2.
