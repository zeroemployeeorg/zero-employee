# Governance & Operating Rules

DOC-DATE: (Rev 17, scaffold)

## 1. Operating Rules & Doctrine

- Single Source of Truth: doctrine under `claude-md/CLAUDE.md` (IDE entrypoints import this file).
- All SOW documents must adhere to `schema_rev: 17`.
- Primary gate: `make verify` or `zeo` / `sow-lint` must pass before every commit.

## 2. Gate Contract

Run `make verify` (or `zeo <path>` / `sow-lint <path>`) to execute format-checks, linting, and tests.

## 3. SOW Frontmatter (Rev 17)

Required fields include: `sow:`, `n:`, `schema_rev:`, `status:`, `created:`, `updated:`,
`sow_repo:`, `work_repo:`, `project:`, plus working-status fields `done_when:` and `restaufwand:`
when status is not at rest.

Do not mutate closed rulings or historical SOW bodies.
