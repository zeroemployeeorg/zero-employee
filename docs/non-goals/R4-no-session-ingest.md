# R4 — Do not import runtime session files into the canonical corpus

**Rejected capability:** Copying Codex/Claude/Sandcastle session directories into
the governed corpus, or crawling provider session storage from `zero_employee`
core.

**Why:** Sessions are mutable, provider-shaped, potentially secret-bearing, and
often large. Resume and fork remain provider-owned.

**Seam:** opaque `runtime_address`, `log_ref` (identity/hash/path), hashes on
receipts.

**Reopen if:** a ruling plus a redaction/size bound and a non-secret session
export format with a probe receipt.

**Prior:** SPARRING-RULING-SANDCASTLE-ADOPTION-2026-08-22 §R4.
