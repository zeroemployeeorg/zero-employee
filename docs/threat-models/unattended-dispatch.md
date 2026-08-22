# Threat model — unattended GitHub dispatch (A5)

Prerequisite for any scheduled Master/Stream/Sparring mutation. This is not
authorization to add an agent workflow to this repository.

## Assets

- Protected trunk (`main`) and the requirement that changes land through a PR
- Governed corpus artifacts (SOWs, rulings) and execution receipts
- Live exclusive ownership of a mutable branch or governed stream
- Credentials (GitHub tokens, model API keys) — never in the corpus

## Adversaries / failure classes

- Two unattended jobs claiming the same branch or stream (lost updates)
- A remote branch advancing during work (silent overwrite)
- A GitHub `concurrency:` group treated as a seat or lock
- A label, prompt, or seat *type* used as exclusive ownership
- Unconditional `git push --force` racing a human or another job
- A bot merging its own PR on a protected trunk
- Reporting "delivered" from a local SHA without remote containment

## Controls in this package

- Ownership key = `repository + branch` or `repository + stream` (`dispatch.ownership_key`)
- Duplicate live lock → refusal **receipt**, not only a workflow log
- Pin `head_sha` / `base_sha` at acquire
- `check_remote_advancement` before push
- Rewrite only via `--force-with-lease=<branch>:<expected>`
- Failed/aborted locks remain inspectable until authorized cleanup

## Explicitly out of scope here (R7)

Installing agent CLIs, Anthropic/OpenAI credentials in Actions, label machines,
or copying Sandcastle's workflows. Unattended mutation of *this* product repo
still requires a later SOW after this threat model is accepted.

## Residual risk

Filesystem locks in `executions/dispatch/locks/` are not a distributed lock
across machines until they are pushed and fetched. Callers must acquire against
a shared ref and re-check `ls-remote` before mutation. A GitHub concurrency
group may serialize jobs in one workflow; it does not prove organizational
ownership.
