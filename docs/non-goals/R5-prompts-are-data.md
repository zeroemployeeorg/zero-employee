# R5 — Do not make prompts executable by default

**Rejected capability:** Prompt-file shell expansion (Sandcastle-style expressions)
inside Zero Employee artifacts or core.

**Why:** Artifacts remain data. Expansion enlarges injection and nondeterminism.

**Seam:** If an *executor* supports expansion, it is executor-side, opt-in,
fail-fast, bounded, and named on the capability manifest and receipt.

**Reopen if:** a threat model plus a capability flag that defaults false and a
receipt field proving expansion was bounded.

**Prior:** SPARRING-RULING-SANDCASTLE-ADOPTION-2026-08-22 §R5.
