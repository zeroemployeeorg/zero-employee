# Governance & Operating Rules

DOC-DATE: (Rev 17, scaffold)

## 1. Operating Rules & Doctrine

- Single Source of Truth: doctrine under `claude-md/CLAUDE.md` (IDE entrypoints import this file).
- All SOW documents must adhere to `schema_rev: 17`.
- Agents provide semantic values; ZEO owns governance syntax (`zeo sow new` / `zeo sow set` — never hand-author YAML frontmatter).
- Intake captures intent before identity is known; SOW governs work after identity is known.
- An implementation SOW promoted from intake must be grounded in current repository bytes, not inferred from intake prose alone.
- The coding agent owns investigation and engineering judgment; ZEO owns evidence validation, identity, governance syntax, and the write gate.
- Primary gate: `make verify` or `zeo` / `zeo` must pass before every commit.

## 2. Gate Contract

Run `make verify` (or `zeo <path>` / `zeo <path>`) to execute format-checks, linting, and tests.

## 3. SOW Frontmatter (Rev 17)

Required fields include: `sow:`, `n:`, `schema_rev:`, `status:`, `created:`, `updated:`,
`sow_repo:`, `work_repo:`, `project:`, plus working-status fields `done_when:` and `restaufwand:`
when status is not at rest.

Do not mutate closed rulings or historical SOW bodies.

## 4. Intake → grounded promote (coding agents)

Capture intent without YAML:

```bash
zeo intake "idea title"
# or
zeo intake new --spec -
```

When promoting an intake into an implementation SOW:

1. Run `zeo intake mission <path> --json`
2. Read the intake fully; inspect actual repository bytes (search before assuming)
3. Submit an evidence-backed proposal: `zeo intake propose <path> --spec <proposal.json>`
4. Materialize: `zeo intake promote <path>`
5. Never author SOW YAML or choose `n`/filename yourself

`zeo sow draft` remains for prose-oriented body assistance (Ollama peer loop).
`zeo intake promote` is the high-assurance path for engineering changes.
