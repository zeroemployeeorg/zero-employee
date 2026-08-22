# Seat identities: a real second GitHub account for review

`zeo seat` lets Master (or any other seat — Sparring, a reviewer role, an
independent bot) operate as its own real, separately-authenticated GitHub
account on a shared machine — so a branch-protection `required_approving_review_count`
rule is a genuine second check, not the same identity approving its own PR.

This doc names **no real accounts**. `matorclawson`/`profrod-ai` are one
org's own private choice, not part of `zero-employee` itself — every org
configures its own seat → account mapping locally, in a file `zeo` never
reads unless you create it.

## Why this exists

GitHub will not let an account approve its own pull request. If every seat
in your org (Master, little-Claude streams, Sparring) authenticates as the
same account, `required_approving_review_count: 1` on a protected branch has
exactly one bad option: an admin repeatedly drops the requirement to `0`,
merges, and restores it — which is not a review, it's a number moving down
and back up. The real fix is a genuinely separate identity for at least one
reviewing seat.

## Setup

### 1. Create/authenticate a second real GitHub account

Outside `zeo` entirely — sign up for (or use an existing) separate GitHub
account for the reviewing seat. Log it in to its own isolated `gh` config
directory so it never collides with your primary account's session:

```bash
GH_CONFIG_DIR=~/.config/gh-sparring gh auth login --hostname github.com --git-protocol ssh --web
```

(Repeat for as many seats as you want distinct identities for — most orgs
need exactly two: the seat that authors work, and the seat that reviews it.)

### 2. Add that account as a collaborator on your repos

From your **primary** admin-level account (the reviewing account cannot add
itself):

```bash
gh api --method PUT repos/<owner>/<repo>/collaborators/<reviewing-account> -f permission=push
```

This sends a real invitation; accept it once from the reviewing account's own
session (`GH_CONFIG_DIR=~/.config/gh-sparring gh api --method PATCH user/repository_invitations/<id>`,
or via the GitHub web UI).

### 3. Configure `zeo seat` for your corpus

```bash
zeo seat init
```

Writes a commented-out example `.zeo/seats.toml` at your corpus root (or
wherever `$ZEO_SEATS_FILE` points). Edit it to name your own seats:

```toml
[seats.master]
gh_config_dir = "~/.config/gh-master"
# ssh_key = "~/.ssh/id_ed25519_master"       # optional, only if you use SSH git remotes
# account_login = "your-master-account"      # optional, shown by `zeo seat` for humans

[seats.sparring]
gh_config_dir = "~/.config/gh-sparring"
ssh_key = "~/.ssh/id_ed25519_sparring"
account_login = "your-sparring-account"
```

`.zeo/` is gitignored automatically by `zeo hooks install` — **this file
names real accounts and should never be committed.** If you didn't run
`zeo hooks install` in this corpus, add `.zeo/` to your own `.gitignore`
by hand before editing `seats.toml`.

### 4. Switch identity in a shell

```bash
eval "$(zeo seat use sparring)"
```

Sets `GH_CONFIG_DIR` (and `GIT_SSH_COMMAND`, if `ssh_key` is configured) in
the **current shell** — `gh` and `git` in that shell now operate as the
`sparring` seat's account. `zeo seat` (no arguments) shows which seat, if
any, the current shell is using, and lists every configured seat.

## Automating the switch per tmux window (optional)

`zeo seat` itself has no tmux dependency — it just prints `export` lines for
you to `eval`. A common integration: name tmux windows by seat and source
the right identity automatically when a shell starts in that window.

Add to `~/.tmux.conf`:

```tmux
set -g update-environment "TMUX_WINDOW_NAME"
set-hook -g after-new-window 'set-environment -g TMUX_WINDOW_NAME "#{window_name}"'
set-hook -g window-renamed 'set-environment -g TMUX_WINDOW_NAME "#{window_name}"'
set-hook -g session-created 'set-environment -g TMUX_WINDOW_NAME "#{window_name}"'
```

Add to your shell profile (`~/.zshrc` / `~/.bashrc`):

```bash
case "${TMUX_WINDOW_NAME:-}" in
  sparring*) eval "$(zeo seat use sparring)" ;;
  *)         eval "$(zeo seat use master)" ;;
esac
```

Now a tmux window named `sparring-review` (or anything starting with
`sparring`) automatically operates as the `sparring` seat's GitHub identity
in every new shell opened there; everything else defaults to `master`. This
only applies at shell start — rename a window, then open a **new** pane in
it to pick up the change.

## Config reference

`.zeo/seats.toml` (or `$ZEO_SEATS_FILE`):

```toml
[seats.<name>]
gh_config_dir = "<path>"    # required — an isolated `gh` config dir (see setup step 1)
ssh_key = "<path>"          # optional — an SSH private key registered on this account
account_login = "<string>"  # optional — display-only, shown by `zeo seat`
```

Any number of `[seats.<name>]` tables. Names are your own convention —
`master`/`sparring` is one shape; a larger org might use per-role names
(`reviewer-1`, `bot-ci`) instead.

## `zeo seat` command reference

| Command | What it does |
|---|---|
| `zeo seat` | Show the current shell's seat (from `$ZEO_SEAT`) and every configured seat |
| `zeo seat init [--force]` | Write a commented-out example `seats.toml`; refuses to overwrite a real config unless `--force` |
| `zeo seat use <name>` | Print `export ...` lines for `eval "$(zeo seat use <name>)"` |

`zeo seat use` never modifies your shell directly — a subprocess cannot set
its parent shell's environment, so `eval` is the standard, portable
mechanism any CLI tool in this position uses.
