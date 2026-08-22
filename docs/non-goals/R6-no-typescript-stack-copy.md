# R6 — Do not copy TypeScript implementation idioms literally

**Rejected capability:** Porting Effect services, Zod, Vitest, tsup, npm Changesets,
or discriminated TypeScript unions as a requirement of this package.

**Why:** Those are Sandcastle implementation choices. Semantics transfer; the
stack does not.

**Seam:** Pydantic models, `Protocol`, pytest, Hatch/uv, `.release/` fragments.

**Reopen if:** never as a stack transplant; individual libraries only with a
dependency-budget ruling.

**Prior:** SPARRING-RULING-SANDCASTLE-ADOPTION-2026-08-22 §R6.
