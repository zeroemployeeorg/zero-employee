# R7 — Do not adopt Sandcastle GitHub workflows unchanged

**Rejected capability:** Copying Sandcastle agent workflows (repo-specific labels,
vendor credentials, agent install, branch mutation, unconditional `git push --force`)
into this repository.

**Why:** Protected-trunk and one-PR-per-session doctrine is stricter. A GitHub
concurrency group is not organizational identity. A bot must not self-merge
protected trunk.

**Seam:** `zero_employee.dispatch` (lock, refusal receipt, pin SHA, lease push)
plus [docs/threat-models/unattended-dispatch.md](../threat-models/unattended-dispatch.md).

**Reopen if:** a dedicated threat-model SOW is SHIPPED and a workflow uses lease
semantics, immutable head SHAs, and refusal receipts — still no bare `--force`.

**Prior:** SPARRING-RULING-SANDCASTLE-ADOPTION-2026-08-22 §R7.
