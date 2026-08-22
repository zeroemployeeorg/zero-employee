"""zeo seat — named GitHub-identity switching for a two-account review split.

No real account names anywhere in this module or these tests — every fixture
uses placeholder names (example-master, example-sparring) to prove the
mechanism works generically, matching the module's own design contract: zero-
employee ships no hardcoded identity, every org configures its own.
"""

from __future__ import annotations

import os

import pytest

from zero_employee import cli
from zero_employee.seats import (
    SeatAccount,
    SeatsConfigError,
    current_seat_name,
    load_seats,
    render_seat_use_script,
    resolve_seat,
    seats_file_path,
    write_seats_template,
)


def _corpus(tmp_path):
    root = tmp_path / "org"
    (root / "claude-md").mkdir(parents=True)
    (root / "claude-md" / "CLAUDE.md").write_text("# CLAUDE\n", encoding="utf-8")
    return root


# ── seats_file_path ──────────────────────────────────────────────────────


def test_seats_file_path_default_is_dot_zeo_under_corpus_root(tmp_path, monkeypatch):
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    root = _corpus(tmp_path)
    assert seats_file_path(root) == root / ".zeo" / "seats.toml"


def test_seats_file_path_env_override_wins(tmp_path, monkeypatch):
    override = tmp_path / "elsewhere" / "my-seats.toml"
    monkeypatch.setenv("ZEO_SEATS_FILE", str(override))
    root = _corpus(tmp_path)
    assert seats_file_path(root) == override


# ── load_seats ───────────────────────────────────────────────────────────


def test_load_seats_missing_file_returns_empty_dict_not_an_error(tmp_path, monkeypatch):
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    root = _corpus(tmp_path)
    assert load_seats(root) == {}


def test_load_seats_real_config_parses_correctly(tmp_path, monkeypatch):
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    root = _corpus(tmp_path)
    seats_dir = root / ".zeo"
    seats_dir.mkdir()
    (seats_dir / "seats.toml").write_text(
        """
[seats.example-master]
gh_config_dir = "~/.config/gh-example-master"

[seats.example-sparring]
gh_config_dir = "~/.config/gh-example-sparring"
ssh_key = "~/.ssh/id_ed25519_example_sparring"
account_login = "example-sparring-bot"
""",
        encoding="utf-8",
    )
    seats = load_seats(root)
    assert set(seats) == {"example-master", "example-sparring"}
    master = seats["example-master"]
    assert master.gh_config_dir.endswith("/.config/gh-example-master")
    assert master.ssh_key is None
    sparring = seats["example-sparring"]
    assert sparring.ssh_key.endswith("/.ssh/id_ed25519_example_sparring")
    assert sparring.account_login == "example-sparring-bot"


def test_load_seats_invalid_toml_raises_seatsconfigerror_not_silently_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    root = _corpus(tmp_path)
    seats_dir = root / ".zeo"
    seats_dir.mkdir()
    (seats_dir / "seats.toml").write_text("this is not [ valid toml", encoding="utf-8")
    with pytest.raises(SeatsConfigError, match="invalid TOML"):
        load_seats(root)


def test_load_seats_file_with_no_seats_key_is_zero_seats_not_an_error(tmp_path, monkeypatch):
    """A file with no `seats` table at all (e.g. `zeo seat init`'s own
    fully-commented-out template) is the SAME "nothing configured" state as
    no file existing -- not a parse error. Only a present-but-wrong-shaped
    `seats` key should raise (see the next test)."""
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    root = _corpus(tmp_path)
    seats_dir = root / ".zeo"
    seats_dir.mkdir()
    (seats_dir / "seats.toml").write_text('other_key = "value"\n', encoding="utf-8")
    assert load_seats(root) == {}


def test_load_seats_seats_key_present_but_wrong_type_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    root = _corpus(tmp_path)
    seats_dir = root / ".zeo"
    seats_dir.mkdir()
    (seats_dir / "seats.toml").write_text('seats = "not a table"\n', encoding="utf-8")
    with pytest.raises(SeatsConfigError, match="must be a table"):
        load_seats(root)


def test_load_seats_entry_missing_gh_config_dir_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    root = _corpus(tmp_path)
    seats_dir = root / ".zeo"
    seats_dir.mkdir()
    (seats_dir / "seats.toml").write_text('[seats.broken]\nssh_key = "~/.ssh/id_whatever"\n', encoding="utf-8")
    with pytest.raises(SeatsConfigError, match="missing required key 'gh_config_dir'"):
        load_seats(root)


# ── resolve_seat ─────────────────────────────────────────────────────────


def test_resolve_seat_unknown_name_lists_configured_seats_in_error(tmp_path, monkeypatch):
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    root = _corpus(tmp_path)
    seats_dir = root / ".zeo"
    seats_dir.mkdir()
    (seats_dir / "seats.toml").write_text(
        '[seats.example-master]\ngh_config_dir = "~/.config/gh-example-master"\n',
        encoding="utf-8",
    )
    with pytest.raises(SeatsConfigError, match="example-master"):
        resolve_seat("nonexistent", root)


def test_resolve_seat_no_file_at_all_names_zeo_seat_init(tmp_path, monkeypatch):
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    root = _corpus(tmp_path)
    with pytest.raises(SeatsConfigError, match="zeo seat init"):
        resolve_seat("anything", root)


def test_resolve_seat_real_hit_returns_the_seataccount(tmp_path, monkeypatch):
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    root = _corpus(tmp_path)
    seats_dir = root / ".zeo"
    seats_dir.mkdir()
    (seats_dir / "seats.toml").write_text(
        '[seats.example-sparring]\ngh_config_dir = "~/.config/gh-example-sparring"\n',
        encoding="utf-8",
    )
    seat = resolve_seat("example-sparring", root)
    assert seat.name == "example-sparring"


# ── current_seat_name ────────────────────────────────────────────────────


def test_current_seat_name_reads_zeo_seat_env_var(monkeypatch):
    monkeypatch.delenv("ZEO_SEAT", raising=False)
    assert current_seat_name() is None
    monkeypatch.setenv("ZEO_SEAT", "example-sparring")
    assert current_seat_name() == "example-sparring"


# ── write_seats_template / zeo seat init ────────────────────────────────


def test_write_seats_template_creates_a_real_file_with_no_real_account_names(tmp_path, monkeypatch):
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    root = _corpus(tmp_path)
    path = write_seats_template(root)
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    # the template is commented-out example config, not a real seats table --
    # load_seats() on a freshly-init'd file must still report "no seats" (all
    # real entries are commented out), proving this ships no hardcoded identity.
    assert load_seats(root) == {}
    assert "matorclawson" not in content
    assert "profrod-ai" not in content


def test_write_seats_template_does_not_clobber_an_existing_real_config(tmp_path, monkeypatch):
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    root = _corpus(tmp_path)
    seats_dir = root / ".zeo"
    seats_dir.mkdir()
    real_content = '[seats.example-master]\ngh_config_dir = "~/.config/gh-example-master"\n'
    (seats_dir / "seats.toml").write_text(real_content, encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_seats_template(root)
    # confirmed byte-identical after the refused overwrite attempt
    assert (seats_dir / "seats.toml").read_text(encoding="utf-8") == real_content


def test_write_seats_template_force_does_overwrite(tmp_path, monkeypatch):
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    root = _corpus(tmp_path)
    seats_dir = root / ".zeo"
    seats_dir.mkdir()
    (seats_dir / "seats.toml").write_text("stale content\n", encoding="utf-8")
    write_seats_template(root, force=True)
    assert "stale content" not in (seats_dir / "seats.toml").read_text(encoding="utf-8")


# ── render_seat_use_script / env_exports ────────────────────────────────


def test_seat_account_env_exports_gh_config_dir_only_when_no_ssh_key():
    seat = SeatAccount(name="example-master", gh_config_dir="/home/x/.config/gh-master")
    env = seat.env_exports()
    assert env == {"GH_CONFIG_DIR": "/home/x/.config/gh-master"}


def test_seat_account_env_exports_includes_git_ssh_command_when_ssh_key_set():
    seat = SeatAccount(
        name="example-sparring",
        gh_config_dir="/home/x/.config/gh-sparring",
        ssh_key="/home/x/.ssh/id_ed25519_sparring",
    )
    env = seat.env_exports()
    assert env["GH_CONFIG_DIR"] == "/home/x/.config/gh-sparring"
    assert "id_ed25519_sparring" in env["GIT_SSH_COMMAND"]
    assert env["GIT_SSH_COMMAND"].startswith("ssh -i ")


def test_render_seat_use_script_is_real_evalable_shell(tmp_path):
    seat = SeatAccount(
        name="example-sparring",
        gh_config_dir=str(tmp_path / "gh-sparring"),
        ssh_key=str(tmp_path / "id_ed25519_sparring"),
    )
    script = render_seat_use_script(seat)
    assert script.startswith("export ZEO_SEAT=")
    assert "example-sparring" in script
    assert "GH_CONFIG_DIR=" in script
    assert "GIT_SSH_COMMAND=" in script
    # real behavioral proof: eval this in a real subshell, confirm the env
    # vars actually land — not just that the string LOOKS like shell syntax.
    import subprocess

    result = subprocess.run(
        ["sh", "-c", f'{script}\necho "$ZEO_SEAT|$GH_CONFIG_DIR|$GIT_SSH_COMMAND"'],
        capture_output=True,
        text=True,
        check=True,
    )
    seat_out, gh_dir_out, ssh_cmd_out = result.stdout.strip().split("|", 2)
    assert seat_out == "example-sparring"
    assert gh_dir_out == str(tmp_path / "gh-sparring")
    assert "id_ed25519_sparring" in ssh_cmd_out


def test_render_seat_use_script_handles_paths_with_spaces_safely(tmp_path):
    weird_dir = tmp_path / "gh config with spaces"
    seat = SeatAccount(name="example-master", gh_config_dir=str(weird_dir))
    script = render_seat_use_script(seat)
    import subprocess

    result = subprocess.run(
        ["sh", "-c", f'{script}\necho "$GH_CONFIG_DIR"'],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == str(weird_dir)


# ── zeo seat CLI (real end-to-end, via cli.main) ────────────────────────


def test_zeo_seat_bare_with_no_config_reports_no_seats_toml(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    monkeypatch.delenv("ZEO_SEAT", raising=False)
    root = _corpus(tmp_path)
    monkeypatch.chdir(root)
    rc = cli.main(["seat"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "no seats.toml found" in out
    assert "zeo seat init" in out


def test_zeo_seat_init_then_bare_shows_configured_seats(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    monkeypatch.delenv("ZEO_SEAT", raising=False)
    root = _corpus(tmp_path)
    monkeypatch.chdir(root)

    rc = cli.main(["seat", "init"])
    assert rc == 0
    capsys.readouterr()  # discard the init message

    # the template is all commented out — confirm bare `zeo seat` still
    # correctly reports zero configured seats, not a parse error.
    rc = cli.main(["seat"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "no seats.toml found" not in out  # the file DOES exist now
    assert "current seat: (none set" in out


def test_zeo_seat_init_twice_without_force_fails_clean(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    root = _corpus(tmp_path)
    monkeypatch.chdir(root)
    assert cli.main(["seat", "init"]) == 0
    capsys.readouterr()
    rc = cli.main(["seat", "init"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "already exists" in err


def test_zeo_seat_use_unconfigured_seat_fails_with_real_message(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    root = _corpus(tmp_path)
    monkeypatch.chdir(root)
    seats_dir = root / ".zeo"
    seats_dir.mkdir()
    (seats_dir / "seats.toml").write_text(
        '[seats.example-master]\ngh_config_dir = "~/.config/gh-example-master"\n',
        encoding="utf-8",
    )
    rc = cli.main(["seat", "use", "example-sparring"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "example-sparring" in err


def test_zeo_seat_use_configured_seat_prints_real_export_script(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    root = _corpus(tmp_path)
    monkeypatch.chdir(root)
    seats_dir = root / ".zeo"
    seats_dir.mkdir()
    (seats_dir / "seats.toml").write_text(
        '[seats.example-sparring]\ngh_config_dir = "~/.config/gh-example-sparring"\n',
        encoding="utf-8",
    )
    rc = cli.main(["seat", "use", "example-sparring"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "export ZEO_SEAT=example-sparring" in out
    assert "GH_CONFIG_DIR=" in out


def test_zeo_seat_use_then_bare_reflects_the_current_seat_via_real_eval(tmp_path, monkeypatch, capsys):
    """End-to-end proof: `eval "$(zeo seat use X)"` genuinely changes what a
    subsequent `zeo seat` (bare) reports as current — not just that the
    printed script LOOKS right in isolation."""
    monkeypatch.delenv("ZEO_SEATS_FILE", raising=False)
    root = _corpus(tmp_path)
    monkeypatch.chdir(root)
    seats_dir = root / ".zeo"
    seats_dir.mkdir()
    (seats_dir / "seats.toml").write_text(
        '[seats.example-master]\ngh_config_dir = "~/.config/gh-example-master"\n\n'
        '[seats.example-sparring]\ngh_config_dir = "~/.config/gh-example-sparring"\n',
        encoding="utf-8",
    )
    rc = cli.main(["seat", "use", "example-sparring"])
    assert rc == 0
    script = capsys.readouterr().out
    # simulate the shell's eval by actually applying the exports to THIS
    # process's own env (monkeypatch, auto-reverted) — real behavioral check
    # of what current_seat_name()/load_seats() see afterward, not a re-parse
    # of the script string.
    for line in script.strip().splitlines():
        assert line.startswith("export ")
        key, _, value = line[len("export ") :].partition("=")
        monkeypatch.setenv(key, value.strip("'\""))
    assert os.environ["ZEO_SEAT"] == "example-sparring"
    assert current_seat_name() == "example-sparring"

    monkeypatch.chdir(root)
    capsys.readouterr()
    rc = cli.main(["seat"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "current seat: example-sparring" in out
    assert "example-sparring *" in out
    assert "example-master" in out and "example-master *" not in out
