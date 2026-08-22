# Swapping a session from Claude Code to OpenAI Codex

A practical, operator-facing guide for the moment you actually need it: Claude
Code has hit a limit and you need to keep working under Codex instead, right
now. This doc assembles already-ruled, already-verified knowledge into one
place — it does not decide anything new. The design decision (which
approaches to use, and why not a literal daemon port) was made in
[`RULING-351`](../../org/ruling/RULING-351-codex-full-parity-b-and-c-not-a-daemon-port.md)
and behaviorally confirmed in
[`RULING-353`](../../org/ruling/RULING-353-codex-daemon-does-not-reopen-351-bc-artifacts-accepted-with-two-named-gaps.md).
Read those two for the full reasoning; this doc summarizes the parts you need
to actually run the swap.

> Every command and finding below is cited from real SOW text or live
> `--help` output, re-verified on 2026-08-21 against `codex-cli 0.149.0`
> (standalone install). Nothing here is guessed or paraphrased from memory.

## The short version

Custom-agent names (`zeo-master`, `zeo-sparring`, `zeo-stream`) are **seat
types** (constructors). They are not addresses of already-running instances.
Master ↔ Sparring communication uses `zeo relay` plus an operator-started
supervisor (`zeo relay start`). That process is **not** a silent daemon:
when the human stops it, delivery stops (RULING-351 preserved).

A custom persona is loaded only when Codex actually spawns a custom-agent
thread. Starting a top-level `codex exec` run does not itself turn that
top-level thread into the named persona. Probe the **installed** binary with
`zeo doctor --codex` rather than freezing doctrine around one older CLI
experiment.

Preferred dual-seat UX:

```bash
zeo relay start --master zeo-master --sparring zeo-sparring
```

Keep both inboxes: relay messages coordinate live instances; `zeo --inbox`
and SOWs/rulings remain organizational truth.

RULING-351 still rejects a literal Codex daemon port. Approach B (`codex
exec`) and approach C (interactive TUI) remain valid trigger classes for
*starting* work; they do not replace the relay addressing layer.

## Trigger-class table

| | Approach B — `codex exec` | Approach C — interactive `codex` TUI |
|---|---|---|
| **Invocation** | Scripted/CI: `codex exec "<prompt>" ...` | A human runs `codex`, then may spawn a named custom agent |
| **When to use** | Scheduled/CI upkeep | Operator-initiated swap |
| **Persona loads?** | Only if this Codex release actually spawns a custom-agent thread for that name. A bare `codex exec` prompt is not automatically `zeo-stream`. Confirm with `zeo doctor --codex` / `zeo test-runtime codex`. | Same rule: the persona file applies to the spawned custom-agent thread, not to “the TUI exists”. |
| **Master ↔ Sparring** | Use `zeo relay`; do not spawn-by-name if `zeo relay resolve` shows an active instance. | Same. Prefer `zeo relay start`. |
| **Unattended daemon?** | No. | No. |

## Exact commands, verified

### Approach B: `codex exec`

The exact invocation SOW-8 ran and confirmed working end-to-end, including
real shell execution and real corpus output
(`codex-multi-tool-adoption-SOW-8-standalone-install-shell-exec-fully-working.md`):

```bash
codex exec "Run the shell command: zeo --triage . -- run it from /Users/rodbot/code/zeroemployeeorg/org" \
  --sandbox read-only --json
```

This produced a real `command_execution` item running `zeo --triage .` and
real board output (173 streams at the time), matching an independently-run
`zeo --triage .` in the same session exactly, `exit_code: 0`.

For a scheduled/scriptable run where you don't want any approval prompts and
want to allow writes, RULING-351 §2 names the general shape:

```bash
codex exec "<prompt with the full zeo verb sequence and seat discipline inline>" \
  --ask-for-approval never --sandbox workspace-write
```

Both flags are real and current — confirmed directly against `codex exec
--help` (`codex-cli 0.149.0`, re-checked 2026-08-21): `-a, --ask-for-approval
<APPROVAL_POLICY>` accepts `on-request` / `never`; `-s, --sandbox
<SANDBOX_MODE>` accepts `read-only` / `workspace-write` /
`danger-full-access`; `--json` prints events as JSONL.

**Because no persona loads under B, the prompt itself must carry seat
discipline** — the FIRST ACT verb, the escalation rule, explicit-pathspec
commit discipline — the same content `roles/agents/zeo-stream.md` or
`AGENTS.md` carries for a Claude Code session, spelled out in the prompt text
rather than assumed from a persona file.

### Approach C: interactive TUI, invoking a persona by name

Real syntax, confirmed directly against `codex --help` (`codex-cli 0.149.0`):
running `codex` with no subcommand starts the interactive session (`codex
[OPTIONS] [PROMPT]` — "If no subcommand is specified, options will be
forwarded to the interactive CLI"). Inside that live session, a human
explicitly names the persona to delegate to (e.g. "delegate to the subagent
named `zeo-stream`") — this is Codex's documented subagent model at standard
tiers, per RULING-351 §8's favorable correction: delegation can also fire
when "applicable project or skill instructions request it," not solely on a
per-spawn human request.

The one real, working example of a persona file in this org is
[`org/.codex/agents/zeo-stream.toml`](../../org/.codex/agents/zeo-stream.toml) —
read it directly to see what a working persona actually looks like,
including its own in-file gap-disclosure history (see below). It carries the
same FIRST ACT verb, escalation rule, and write-set discipline as
`roles/agents/zeo-stream.md`, translated into Codex's TOML persona shape
(`name`, `description`, `developer_instructions`, `sandbox_mode`). The
`model`/`model_reasoning_effort` keys are deliberately omitted (see
codex-multi-tool-adoption SOW-10): a shipped template has no reliable way to
pre-validate a pinned model string against a given account's current
entitlements (`codex --help`, `codex exec --help`, and `codex features list`
were all checked; none enumerate valid model strings), so the persona
inherits whatever model the parent session/account is actually configured to
use, from `~/.codex/config.toml`, rather than pinning a string that can go
stale and fail with a real API 400 `invalid_request_error` on accounts where
the pinned model has been retired.

## Known gaps and their fixes

### 1. `code_mode_host` local-service gap (approach B, shell execution) — FIXED, but by a specific install method

SOW-5 and SOW-7 both hit an identical, reproducible failure on a
**brew-installed** Codex: every attempt to run an actual shell command via
`codex exec` (including plain `zeo --triage .`) failed with `timed out
negotiating with the code-mode host`. Root cause (SOW-5): this Codex version
routes all shell execution through a `code_mode_host` feature; the companion
binary shipped with the brew cask
(`/opt/homebrew/Caskroom/codex/0.149.0/bin/codex-code-mode-host`) exists on
disk but isn't wired up as a running service, and no documented mechanism to
launch it correctly was found (SOW-7 tried a corrected symlink, then
launching the binary directly as a background process — neither fixed it).

**The fix** (SOW-8): uninstall the brew cask and use Codex's official
standalone installer instead:

```bash
brew uninstall --cask codex
curl -fsSL https://chatgpt.com/codex/install.sh | sh
```

This installs to `~/.codex/packages/standalone/releases/<version>/`, with
its own `current` symlink — no manual symlink is needed. Auth survives the
reinstall untouched (`~/.codex/auth.json` is per-user config, independent of
the package manager). SOW-8 re-ran the identical shell-exec test that failed
in SOW-5/SOW-7 and got a real `command_execution` item, real output,
`exit_code: 0` — confirmed fixed, not theoretically fixed.

**If `codex doctor` reports `install method: brew`, this gap likely applies
to you.** Switch to the standalone installer before relying on approach B's
shell-exec path.

### 2. Approach C's persona-loading gap under `codex exec` — also fixed by the same reinstall, but read this carefully

This is a separate finding from item 1, and the distinction matters: SOW-5
found that on the brew install, naming `zeo-stream` under `codex exec` did
**not** actually load the TOML's real contents — the parent model fabricated
a plausible-sounding but nonexistent command (`zeo prime`) instead of the
real `zeo --triage .`. This was caught behaviorally, not left as a
documentation gap — the exact "looks equivalent but isn't" failure mode
RULING-351 §1 named when rejecting a literal daemon-port approach.

SOW-8, re-verifying its own build wasn't contaminated by the reinstall,
incidentally re-ran the same class of probe on the fresh standalone install
and found it **fixed**: the subagent answered with the real verb (`zeo
--triage .`), and a harder verbatim-quote canary probe (asking for an exact
sentence from the TOML, including its own ruling citation) came back as an
**exact match** — only possible if the real file content had genuinely
loaded into context.

**Read this precisely, because it is easy to over-claim:** this confirms
persona content genuinely loads correctly under `codex exec` on a standalone
install. But per the trigger-class table above, `codex exec` is **approach
B**, which per RULING-351 §8 Amendment 2 is documented to never load a
persona at all in real use. What SOW-5/SOW-8 actually tested was persona
loading *as a proxy signal*, using `codex exec` as a convenient
non-interactive way to probe whether the file's content is reachable at
all — not a claim that production B-invocations should rely on persona
files. **Approach C's actual, documented trigger class — a human at a real
interactive Codex TUI, invoking a persona by name inside that session — has
never been tested in this org.** SOW-5 tried it directly (`codex` with piped
stdin) and got an honest, structural refusal: `Error: stdin is not a
terminal` — this tool environment has no live terminal to drive a TUI with.
SOW-8 confirmed this remains the case after the reinstall, unrelated to the
shell-exec/persona-loading fixes. **As of 2026-08-21, this gap is still
open.** It was independently re-confirmed at the point this doc was written
(`tty` reports "not a tty" in this environment too). If you are the first
human to actually run `codex` interactively and invoke `zeo-stream` (or any
persona) by name, that is genuinely new verification — please file a SOW
recording what you saw, since nothing before you has done this.

### 3. Credential method: ChatGPT auth, not `OPENAI_API_KEY` — and one sub-question still open

The operator's own decision (RULING-351 §7): use interactive ChatGPT auth,
not an `OPENAI_API_KEY`. Confirmed live: `codex doctor` shows `auth mode:
chatgpt`, `stored ChatGPT tokens: true`.

**RULING-351 §7 also named an open sub-question, not yet closed as of this
writing:** SOW-4's evidence found the documented GitHub Action path
authenticates via an `OPENAI_API_KEY` GitHub secret specifically; SOW-4 did
not find documentation that `codex exec`'s scriptable path (approach B)
works under interactive ChatGPT auth as opposed to requiring an API key.
Checked directly for this doc: no later SOW or ruling in this chain
(SOW-5 through SOW-8, RULING-353) revisits or resolves this specific
sub-question. **What SOW-8 did confirm** is that `codex exec` runs
successfully end-to-end on this machine using the stored ChatGPT auth
tokens (no API key set, `codex doctor` confirms chatgpt auth mode) — so
approach B's local `codex exec` path is confirmed working under ChatGPT
auth on this machine. What remains genuinely unconfirmed is specifically the
**GitHub Action path** (a different execution environment than a local
`codex exec` invocation) — whether it can also run under ChatGPT auth or
requires a separately-provisioned `OPENAI_API_KEY` GitHub secret. Named here
as still open, not assumed either way.

## Setup: `zeo scaffold --codex`

A sibling stream in this same charter (`codex-swap-ux-SOW-1`) is chartered to
extend `zeo scaffold <project> <stream> --codex` (and `--all`) so it installs,
alongside the existing `AGENTS.md` symlink (instructions parity), real
`.codex/agents/{zeo-master,zeo-stream,zeo-sparring}.toml` personas —
generalized from the real, working `org/.codex/agents/zeo-stream.toml` — the
same way `--claude`/`--agents` installs `.claude/agents/*.md` files.

**As of this doc being written (2026-08-21), that build landed as a real
commit in this repo** (`b640480`, "feat(scaffold): --codex installs
.codex/agents/*.toml personas, not just AGENTS.md" — `scaffold.py`'s
`install_bridges()` wiring and `scaffold_templates/codex-agents/{zeo-master,
zeo-stream,zeo-sparring}.toml` templates are on `main`) **but its own SOW
had not yet been filed in the `org` chain at the time this doc was
written** — only `CHARTER-codex-swap-ux.md` and this doc's own SOW-2 filing
existed there, no `codex-swap-ux-SOW-1-*.md` yet. Do not assume either state
(shipped-and-filed vs. still-building) stays true — check directly before
relying on it:

```bash
# Does the flag actually install personas yet on your checkout?
git log --oneline -- src/zero_employee/scaffold_templates/codex-agents/ src/zero_employee/scaffold.py
ls org/projects/org/sow/codex-swap-ux/   # look for a filed codex-swap-ux-SOW-1-*.md
```

Once it ships, `--codex` is the mechanical setup step for approach C (it
installs the persona files this doc describes invoking). Until it's
confirmed shipped on your checkout, a real persona file for a given repo can
still be hand-authored the way `org/.codex/agents/zeo-stream.toml` was, or
copied and adapted from it directly. See
[README.md's scaffolding section](../README.md#modular-ide--agent-scaffolding)
for the current, authoritative flag behavior on your checkout.

## Further reading

- [`RULING-351`](../../org/ruling/RULING-351-codex-full-parity-b-and-c-not-a-daemon-port.md) — the design decision: why a literal daemon port was rejected, why B+C were adopted together, the credential-method decision and its open sub-question (§7), Sparring's 3 amendments (§8).
- [`RULING-353`](../../org/ruling/RULING-353-codex-daemon-does-not-reopen-351-bc-artifacts-accepted-with-two-named-gaps.md) — the behavioral confirmation: the app-server daemon finding, and both B/C artifacts accepted with their gaps named plainly.
- SOW chain at `org/projects/org/sow/codex-multi-tool-adoption/` — SOW-5 (daemon recon + first B/C build, both gaps found), SOW-7 (symlink fix attempt, verified insufficient), SOW-8 (standalone install, both gaps closed) — the exact commands and evidence this doc draws from.
- [`org/.codex/agents/zeo-stream.toml`](../../org/.codex/agents/zeo-stream.toml) — the one real, working persona file in this org, including its own in-file gap-disclosure history.
