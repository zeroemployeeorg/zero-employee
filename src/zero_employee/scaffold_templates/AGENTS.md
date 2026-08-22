# Codex entrypoint

First command:

```bash
zeo orient --json
```

Then `zeo relay whoami --json` if `ZEO_INSTANCE_ID` is set, and
`zeo relay receive --instance $ZEO_INSTANCE_ID --json`.

## Repository map

- `governance/GOVERNANCE.md` — tool-neutral doctrine
- `claude-md/CLAUDE.md` — corpus marker (imports governance)
- `projects/*/sow/` — SOW chains
- `ruling/` — durable mandates
- `executions/relay/` — seat-instance registry and message ledger

## Seat types are constructors, not addresses

`zeo-master`, `zeo-sparring`, and `zeo-stream` name **seat types**. They are
not addresses of already-running instances. If a destination is registered in
`zeo relay status`, send through `zeo relay`. Do not spawn another agent with
the destination’s seat name.

Prefer `zeo relay start --master zeo-master --sparring zeo-sparring` for the
two durable seats.

## Verify / done

- Gate: `make verify` or `zeo <path>`
- Done: SOW `done_when:` holds, gates pass, relay acks recorded when you
  messaged another instance
- Worktrees: one write-heavy instance per worktree (`zeo workspace create`)

Longer procedure lives in skills under `.codex/skills/` and in GOVERNANCE.md.
