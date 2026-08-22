"""Seat identity switching: which real GitHub account a shell operates as.

WHY THIS EXISTS: a two-account review split (one identity per seat -- e.g.
Master and Sparring, or Master and any independent reviewer role) is the only
way a required-approving-review branch-protection rule is a REAL second check
rather than the same account approving its own PR. GitHub will not let an
account approve its own PR, so a single-identity org either can't use required
reviews at all, or has to toggle the requirement off and on around every merge
(which is not a review -- nobody reads anything, the number just moves).

This module owns NO real account names. Every org configures its own seat ->
account mapping in a local, gitignored `.zeo/seats.toml` (or `ZEO_SEATS_FILE`)
-- zero-employee ships the mechanism, never a hardcoded identity. See
`docs/seats.md` for the full config schema and setup walkthrough.
"""

from __future__ import annotations

import dataclasses
import os
import pathlib
import shlex
import tomllib


_ENV_SEATS_FILE = "ZEO_SEATS_FILE"
_DEFAULT_SEATS_RELPATH = pathlib.Path(".zeo") / "seats.toml"


@dataclasses.dataclass(frozen=True)
class SeatAccount:
    """One seat's real-identity configuration, as declared in seats.toml."""

    name: str
    gh_config_dir: str
    ssh_key: str | None = None
    account_login: str | None = None  # informational only, for `zeo seat` display

    def env_exports(self) -> dict[str, str]:
        """The env vars a shell must set to operate as this seat's account."""
        env: dict[str, str] = {"GH_CONFIG_DIR": self.gh_config_dir}
        if self.ssh_key:
            env["GIT_SSH_COMMAND"] = f"ssh -i {shlex.quote(self.ssh_key)} -o IdentitiesOnly=yes"
        return env


class SeatsConfigError(ValueError):
    """A seats.toml file exists but is malformed or names an unknown seat."""


def seats_file_path(corpus_root: pathlib.Path | str | None = None) -> pathlib.Path:
    """Where seats.toml lives: $ZEO_SEATS_FILE, else <corpus_root>/.zeo/seats.toml.

    `corpus_root` may be None (e.g. called before corpus discovery) -- in that
    case only the env var override is consulted; a caller with a real corpus
    root should pass it so the default per-corpus location resolves.
    """
    override = os.environ.get(_ENV_SEATS_FILE)
    if override:
        return pathlib.Path(override).expanduser()
    base = pathlib.Path(corpus_root) if corpus_root else pathlib.Path.cwd()
    return base / _DEFAULT_SEATS_RELPATH


def load_seats(corpus_root: pathlib.Path | str | None = None) -> dict[str, SeatAccount]:
    """Parse seats.toml into {seat_name: SeatAccount}. Empty dict if no file.

    A missing file is NOT an error (most `zeo` usage has no multi-seat review
    split configured at all) -- this returns {} and callers decide what that
    means. A PRESENT but malformed file raises SeatsConfigError -- a real
    config the user wrote that zeo can't parse should fail loudly, not
    silently behave as if unconfigured.
    """
    path = seats_file_path(corpus_root)
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise SeatsConfigError(f"{path}: invalid TOML -- {exc}") from exc

    # A file with no `seats` key at all (e.g. a freshly-`zeo seat init`'d
    # template, entirely commented out) is NOT malformed -- it's the same
    # "zero seats configured" state as a missing file, and callers (`zeo
    # seat` bare, `zeo doctor`) need to tell that apart from a real parse
    # error. Only a PRESENT-but-wrong-shaped `seats` key raises.
    seats_raw = raw.get("seats", {})
    if not isinstance(seats_raw, dict):
        raise SeatsConfigError(f"{path}: 'seats' must be a table of [seats.<name>] entries")

    out: dict[str, SeatAccount] = {}
    for name, entry in seats_raw.items():
        if not isinstance(entry, dict):
            raise SeatsConfigError(f"{path}: [seats.{name}] must be a table, got {type(entry).__name__}")
        gh_config_dir = entry.get("gh_config_dir")
        if not gh_config_dir or not isinstance(gh_config_dir, str):
            raise SeatsConfigError(f"{path}: [seats.{name}] is missing required key 'gh_config_dir' (a string path)")
        ssh_key = entry.get("ssh_key")
        if ssh_key is not None and not isinstance(ssh_key, str):
            raise SeatsConfigError(f"{path}: [seats.{name}].ssh_key must be a string path if present")
        account_login = entry.get("account_login")
        if account_login is not None and not isinstance(account_login, str):
            raise SeatsConfigError(f"{path}: [seats.{name}].account_login must be a string if present")
        out[name] = SeatAccount(
            name=name,
            gh_config_dir=str(pathlib.Path(gh_config_dir).expanduser()),
            ssh_key=str(pathlib.Path(ssh_key).expanduser()) if ssh_key else None,
            account_login=account_login,
        )
    return out


def resolve_seat(name: str, corpus_root: pathlib.Path | str | None = None) -> SeatAccount:
    """Look up one named seat. Raises SeatsConfigError with the real seat
    list if `name` isn't configured -- never returns a guessed/default seat."""
    seats = load_seats(corpus_root)
    if name not in seats:
        path = seats_file_path(corpus_root)
        known = ", ".join(sorted(seats)) or "(none configured)"
        if not seats:
            raise SeatsConfigError(
                f"no seats.toml found at {path} (or $ZEO_SEATS_FILE). "
                f"Run `zeo seat init` to create one, or see docs/seats.md."
            )
        raise SeatsConfigError(f"seat '{name}' not found in {path}. Configured seats: {known}")
    return seats[name]


def current_seat_name() -> str | None:
    """The seat this shell is CURRENTLY operating as, per ZEO_SEAT env var --
    set by `eval "$(zeo seat use <name>)"`. None if never set (not an error;
    plenty of zeo usage has no seat concept in play at all)."""
    return os.environ.get("ZEO_SEAT") or None


_SEATS_TOML_TEMPLATE = """\
# zeo seat identities -- maps a seat name (e.g. "master", "sparring") to a
# REAL GitHub account this machine already has separately authenticated
# (its own `gh auth login`, its own isolated $GH_CONFIG_DIR). This file
# names YOUR org's own accounts -- it is gitignored by default (see
# docs/seats.md) and should stay that way; zero-employee itself ships no
# real account names anywhere.
#
# Setup, per seat:
#   1. `gh auth login` as the real account, into its own config dir:
#        GH_CONFIG_DIR=~/.config/gh-<seat> gh auth login
#   2. (optional, only if you use SSH git remotes) give that account its
#      own SSH key, registered on its GitHub account, distinct from any
#      other seat's key.
#   3. Add an entry below.
#
# Then: `eval "$(zeo seat use sparring)"` in a shell makes `gh`/`git` in
# that shell operate as the sparring seat's account. `zeo seat` (no args)
# shows which seat (if any) the CURRENT shell is using.

# [seats.master]
# gh_config_dir = "~/.config/gh-master"
# ssh_key = "~/.ssh/id_ed25519_master"       # optional
# account_login = "your-master-account"      # optional, display only

# [seats.sparring]
# gh_config_dir = "~/.config/gh-sparring"
# ssh_key = "~/.ssh/id_ed25519_sparring"     # optional
# account_login = "your-sparring-account"    # optional, display only
"""


def write_seats_template(corpus_root: pathlib.Path | str | None = None, *, force: bool = False) -> pathlib.Path:
    """Write a commented-out example seats.toml. Never clobbers a real,
    already-populated file unless force=True -- `zeo seat init` run twice
    on a corpus someone already configured must not silently wipe it."""
    path = seats_file_path(corpus_root)
    if path.is_file() and not force:
        raise FileExistsError(f"{path} already exists -- pass force=True (zeo seat init --force) to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_SEATS_TOML_TEMPLATE, encoding="utf-8")
    return path


def render_seat_use_script(seat: SeatAccount) -> str:
    """Shell (POSIX sh/bash/zsh-compatible) export statements for `eval
    "$(zeo seat use <name>)"` to actually apply the seat's identity to the
    CURRENT shell. A subprocess (which is all `zeo` itself ever is) cannot
    set its parent shell's environment directly -- eval-ing printed export
    lines is the standard, portable way any CLI tool achieves this."""
    lines = [f"export ZEO_SEAT={shlex.quote(seat.name)}"]
    for key, value in seat.env_exports().items():
        lines.append(f"export {key}={shlex.quote(value)}")
    return "\n".join(lines) + "\n"
