"""Behavioral probes for `zeo cold-start <repo-path>` (COLD-START-SOW-2).

RULING-278 s3 names a fixed 10-item Ist-Aufnahme checklist. This SOW builds ONLY
the 5 items that need no stack detector: 1 (identity), 3 (CI presence), 8 (docs
surface), 9 (TODO/FIXME/XXX + gh issues), 10 (secrets presence-only).

Every probe runs against a REAL throwaway git repo fixture (tmp_path + `git
init`) and a REAL throwaway SOWS repo fixture (tmp_path + `zeo init`-equivalent),
reading files back rather than trusting return values alone -- the same
falsification discipline `test_scaffold_equip.py` already uses for this charter
family.

Three groups, matching COLD-START-SOW-2 s4's own required tests:
  1. Each of the 5 items, evidence cited exactly (not paraphrased).
  2. The zero-commits/zero-writes-in-the-work-repo safety probe (s3's own
     load-bearing property).
  3. The RULING-278 s0 regression: a `.claude/`-only repo with no SOW/ruling at
     all now gets a real, non-placeholder partial survey, contrasted with
     `zeo scaffold`'s own placeholder body.
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest

from zero_employee.cold_start import (
    derive_project_name,
    run_partial_survey,
    write_ist_aufnahme_sow,
)
from zero_employee.scaffold import equip_repo, init_corpus, scaffold_project_stream


def _git(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture()
def target_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A real, throwaway git repo standing in for an arbitrary cold-started work repo."""
    repo = tmp_path / "target-repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text(
        "# target-repo\n\n"
        "A real multi-line README with actual content describing the project.\n\n"
        "## Usage\n\n"
        "Run `make test` to run the test suite.\n",
        encoding="utf-8",
    )
    (repo / "app.py").write_text("# TODO: refactor this\nprint('hi')\n# FIXME: handle errors\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".env\nnode_modules/\n", encoding="utf-8")
    (repo / ".env.example").write_text("API_KEY=\n", encoding="utf-8")
    (repo / ".github").mkdir()
    (repo / ".github" / "workflows").mkdir()
    (repo / ".github" / "workflows" / "ci.yml").write_text("name: CI\non: [push]\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "initial")
    _git(repo, "remote", "add", "origin", "https://github.com/exampleorg/target-repo.git")
    return repo


@pytest.fixture()
def sows_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A real, throwaway SOWS corpus (claude-md/CLAUDE.md marker + projects/)."""
    root = tmp_path / "sows-repo"
    init_corpus(root)
    return root


# ---------------------------------------------------------------------------
# 1. Each of the 5 items, evidence cited exactly.
# ---------------------------------------------------------------------------


def test_item_1_identity_records_exact_git_evidence(target_repo):
    survey = run_partial_survey(target_repo)
    item1 = next(r for r in survey["results"] if r["item"] == 1)
    assert item1["cannot_complete"] is None

    branch_ev = next(e for e in item1["evidence"] if e["command"] == "git symbolic-ref --short HEAD")
    assert branch_ev["exit_code"] == 0
    assert branch_ev["stdout"] == "main"

    count_ev = next(e for e in item1["evidence"] if e["command"] == "git rev-list --count HEAD")
    assert count_ev["stdout"] == "1"

    assert item1["summary"]["default_branch"] == "main"
    assert item1["summary"]["commit_count"] == "1"
    assert "target-repo" in item1["summary"]["remote"]


def test_item_3_ci_presence_finds_github_workflows(target_repo):
    survey = run_partial_survey(target_repo)
    item3 = next(r for r in survey["results"] if r["item"] == 3)
    assert item3["summary"]["ci_config_found"] is True
    assert ".github/workflows" in item3["summary"]["paths"]
    assert "ci.yml" in item3["summary"]["github_workflow_files"]
    # cited evidence includes the literal test-e command for the exact path found
    assert any(e["command"] == "test -e .github/workflows" and e["exit_code"] == 0 for e in item3["evidence"])


def test_item_3_ci_presence_absent_when_no_ci_config(tmp_path):
    repo = tmp_path / "no-ci-repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")

    survey = run_partial_survey(repo)
    item3 = next(r for r in survey["results"] if r["item"] == 3)
    assert item3["summary"]["ci_config_found"] is False
    assert item3["summary"]["paths"] == []


def test_item_8_docs_surface_non_trivial_readme(target_repo):
    survey = run_partial_survey(target_repo)
    item8 = next(r for r in survey["results"] if r["item"] == 8)
    assert item8["summary"]["readme_found"] is True
    assert item8["summary"]["non_trivial"] is True
    assert item8["summary"]["readme_path"] == "README.md"
    # the exact `wc` command and its literal output must be cited
    assert any(e["command"].startswith("wc -l -w") for e in item8["evidence"])


def test_item_8_docs_surface_trivial_readme_is_not_non_trivial(tmp_path):
    repo = tmp_path / "trivial-readme-repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("# just a title\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")

    survey = run_partial_survey(repo)
    item8 = next(r for r in survey["results"] if r["item"] == 8)
    assert item8["summary"]["readme_found"] is True
    assert item8["summary"]["non_trivial"] is False


def test_item_8_docs_surface_no_readme(tmp_path):
    repo = tmp_path / "no-readme-repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "x.txt").write_text("hi\n", encoding="utf-8")
    _git(repo, "add", "x.txt")
    _git(repo, "commit", "-m", "initial")

    survey = run_partial_survey(repo)
    item8 = next(r for r in survey["results"] if r["item"] == 8)
    assert item8["summary"]["readme_found"] is False
    assert item8["summary"]["non_trivial"] is False


def test_item_9_markers_found_via_git_grep(target_repo):
    survey = run_partial_survey(target_repo)
    item9 = next(r for r in survey["results"] if r["item"] == 9)
    assert item9["cannot_complete"] is None
    assert item9["summary"]["marker_count"] == 2  # TODO + FIXME in app.py
    joined = "\n".join(item9["summary"]["marker_sample"])
    assert "TODO" in joined
    assert "FIXME" in joined


def test_item_9_gh_unavailable_skips_cleanly_without_erroring(target_repo, monkeypatch):
    monkeypatch.setattr("zero_employee.cold_start.shutil.which", lambda name: None)
    survey = run_partial_survey(target_repo)
    item9 = next(r for r in survey["results"] if r["item"] == 9)
    assert item9["summary"]["gh_available"] is False
    assert item9["summary"]["gh_authenticated"] is False
    assert item9["summary"]["open_issue_count"] is None
    assert "gh CLI not found" in item9["summary"]["gh_skip_reason"]
    # marker scan must be unaffected by gh's absence
    assert item9["summary"]["marker_count"] == 2


def test_item_9_gh_auth_status_stdout_never_leaks_into_evidence(target_repo, monkeypatch):
    """MEASURED live (manual CLI run against this seat's own gh credential): a
    naive `gh auth status` capture put the operator's real GitHub username and
    local hosts.yml path into a filed SOW. `gh auth status`'s exit code is real
    evidence (authenticated y/n); its stdout is operator PII that must never
    land in a corpus artifact meant to be shared/comparable across repos."""

    def fake_run(args, cwd, timeout=30):
        if args[:2] == ["gh", "auth"]:
            return {
                "command": " ".join(args),
                "exit_code": 0,
                "stdout": "github.com\n  Logged in to github.com account realuser123 (/Users/realuser/.config/gh/hosts.yml)",
                "stderr": "",
            }
        if args[:2] == ["gh", "issue"]:
            return {"command": " ".join(args), "exit_code": 0, "stdout": "[]", "stderr": ""}
        return real_run(args, cwd=cwd, timeout=timeout)

    import zero_employee.cold_start as cs

    real_run = cs._run
    monkeypatch.setattr(cs, "shutil", cs.shutil)  # gh stays "available"
    monkeypatch.setattr(cs, "_run", fake_run)

    survey = run_partial_survey(target_repo)
    item9 = next(r for r in survey["results"] if r["item"] == 9)
    rendered = repr(item9)
    assert "realuser123" not in rendered
    assert "hosts.yml" not in rendered
    assert item9["summary"]["gh_authenticated"] is True


def test_item_9_no_markers_is_zero_not_cannot_complete(tmp_path):
    repo = tmp_path / "clean-repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "x.py").write_text("print('clean')\n", encoding="utf-8")
    _git(repo, "add", "x.py")
    _git(repo, "commit", "-m", "initial")

    survey = run_partial_survey(repo)
    item9 = next(r for r in survey["results"] if r["item"] == 9)
    assert item9["cannot_complete"] is None
    assert item9["summary"]["marker_count"] == 0


def test_item_10_secrets_presence_only_never_reads_env_contents(target_repo):
    # A real secret-shaped value in .env -- item 10 must record PRESENCE only,
    # never surface the value itself anywhere in the survey output.
    (target_repo / ".env").write_text("API_KEY=sk-not-a-real-secret-abc123\n", encoding="utf-8")
    survey = run_partial_survey(target_repo)
    item10 = next(r for r in survey["results"] if r["item"] == 10)
    assert item10["summary"]["env_exists"] is True
    assert item10["summary"]["env_example_exists"] is True
    assert item10["summary"]["env_in_gitignore"] is True

    rendered = repr(item10)
    assert "sk-not-a-real-secret-abc123" not in rendered


def test_item_10_secrets_absent(tmp_path):
    repo = tmp_path / "no-env-repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "x.py").write_text("print('hi')\n", encoding="utf-8")
    _git(repo, "add", "x.py")
    _git(repo, "commit", "-m", "initial")

    survey = run_partial_survey(repo)
    item10 = next(r for r in survey["results"] if r["item"] == 10)
    assert item10["summary"]["env_exists"] is False
    assert item10["summary"]["env_example_exists"] is False
    assert item10["summary"]["env_in_gitignore"] is False


def test_all_five_items_present_and_no_more(target_repo):
    survey = run_partial_survey(target_repo)
    assert survey["ran_items"] == [1, 3, 8, 9, 10]
    assert [r["item"] for r in survey["results"]] == [1, 3, 8, 9, 10]
    deferred_nums = [n for n, _name, _why in survey["deferred_items"]]
    assert deferred_nums == [2, 4, 5, 6, 7]
    # every deferred item names WHY (the stack detector), not a silent omission
    for _n, _name, why in survey["deferred_items"]:
        assert "stack detector" in why


# ---------------------------------------------------------------------------
# 2. The zero-commits/zero-writes-in-the-work-repo safety probe.
# ---------------------------------------------------------------------------


def test_cold_start_writes_zero_commits_zero_files_into_target_repo(target_repo, sows_repo):
    pre_status = _git(target_repo, "status", "--porcelain").stdout
    pre_log = _git(target_repo, "log", "--oneline").stdout
    pre_files = sorted(p.relative_to(target_repo) for p in target_repo.rglob("*") if ".git" not in p.parts)

    project = derive_project_name(target_repo)
    survey = run_partial_survey(target_repo)
    result = write_ist_aufnahme_sow(sows_repo, project, survey)
    assert result["ok"], result["reason"]

    post_status = _git(target_repo, "status", "--porcelain").stdout
    post_log = _git(target_repo, "log", "--oneline").stdout
    post_files = sorted(p.relative_to(target_repo) for p in target_repo.rglob("*") if ".git" not in p.parts)

    assert pre_status == post_status == ""
    assert pre_log == post_log
    assert pre_files == post_files

    # the ONE write landed in the SOWS repo, under projects/<project>/sow/cold-start/
    sow_path = pathlib.Path(result["path"])
    assert sow_path.is_file()
    assert sow_path.is_relative_to(sows_repo)
    assert sow_path.parent == sows_repo / "projects" / project / "sow" / "cold-start"
    assert sow_path.name == f"{project.upper()}-COLD-START-SOW-01-ist-aufnahme.md"


def test_cold_start_sow_has_status_finding_lifecycle_recon(target_repo, sows_repo):
    from zero_employee.core import extract_frontmatter

    project = derive_project_name(target_repo)
    survey = run_partial_survey(target_repo)
    result = write_ist_aufnahme_sow(sows_repo, project, survey)
    assert result["ok"], result["reason"]

    text = pathlib.Path(result["path"]).read_text(encoding="utf-8")
    fm = extract_frontmatter(text)
    assert fm["status"] == "FINDING"
    assert fm["lifecycle"] == "RECON"
    assert fm["project"] == project
    assert fm["n"] == 1


def test_cold_start_sow_body_states_ran_and_deferred_items_plainly(target_repo, sows_repo):
    project = derive_project_name(target_repo)
    survey = run_partial_survey(target_repo)
    result = write_ist_aufnahme_sow(sows_repo, project, survey)
    assert result["ok"], result["reason"]

    body = pathlib.Path(result["path"]).read_text(encoding="utf-8")
    assert "RAN" in body
    assert "DEFERRED" in body
    for n in (1, 3, 8, 9, 10):
        assert f"Item {n}" in body
    for n in (2, 4, 5, 6, 7):
        assert f"Item {n}." in body
    assert "stack detector" in body


def test_cold_start_sow_lints_clean(target_repo, sows_repo):
    from zero_employee.core import lint_file

    project = derive_project_name(target_repo)
    survey = run_partial_survey(target_repo)
    result = write_ist_aufnahme_sow(sows_repo, project, survey)
    assert result["ok"], result["reason"]

    status, findings = lint_file(pathlib.Path(result["path"]), root=sows_repo)
    errors = [f for f in findings if f.severity == "ERROR"]
    assert not errors, [f"{f.code}: {f.message}" for f in errors]


# ---------------------------------------------------------------------------
# 3. RULING-278 s0 regression: a real, non-placeholder survey where `zeo
#    scaffold` produces an empty stub.
# ---------------------------------------------------------------------------


def test_ruling_278_gap_repro_claude_only_repo_gets_real_survey(tmp_path, sows_repo):
    """The exact RULING-278 s0 shape: a repo with .claude/ installed (via
    `zeo equip`) but no SOW/ruling content at all. `zeo scaffold` would
    produce ONLY a placeholder ("Define objective for workstream <name>.").
    `zeo cold-start` must now produce a REAL 5-item survey instead."""
    repo = tmp_path / "freshly-equipped-repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")

    equip_repo(repo)
    assert (repo / ".claude").is_dir()
    assert not (repo / "sow").exists()
    assert not (repo / "ruling").exists()

    # Contrast: zeo scaffold's own placeholder, cited verbatim in COLD-START-SOW-1's
    # own evidence (scaffold.py's scaffold_project_stream, "unknown - initial scaffold").
    scaffold_info = scaffold_project_stream(sows_repo, "contrast-project", "initial", sow_num=1)
    scaffold_body = pathlib.Path(sows_repo / scaffold_info["sow"]).read_text(encoding="utf-8")
    assert "Define objective for workstream" in scaffold_body

    # The real thing: cold-start's own partial survey.
    project = derive_project_name(repo)
    survey = run_partial_survey(repo)
    result = write_ist_aufnahme_sow(sows_repo, project, survey)
    assert result["ok"], result["reason"]
    cold_start_body = pathlib.Path(result["path"]).read_text(encoding="utf-8")

    # Non-placeholder: real, cited command output appears in the body, and the
    # placeholder string from scaffold's own default is NOT present.
    assert "Define objective for workstream" not in cold_start_body
    assert "git symbolic-ref --short HEAD" in cold_start_body
    assert "readme_found" in cold_start_body or "README" in cold_start_body


def test_cold_start_cli_end_to_end(target_repo, sows_repo):
    from zero_employee.cli import main

    rc = main(["cold-start", str(target_repo), "--sows-root", str(sows_repo)])
    assert rc == 0

    project = derive_project_name(target_repo)
    expected = (
        sows_repo / "projects" / project / "sow" / "cold-start" / f"{project.upper()}-COLD-START-SOW-01-ist-aufnahme.md"
    )
    assert expected.is_file()

    # zero writes into the target repo from the full CLI path too
    status = _git(target_repo, "status", "--porcelain").stdout
    assert status == ""


def test_cold_start_cli_missing_repo_path_errors(sows_repo, capsys):
    from zero_employee.cli import main

    rc = main(["cold-start", "/definitely/not/a/real/path", "--sows-root", str(sows_repo)])
    assert rc == 2


def test_derive_project_name_from_remote(target_repo):
    assert derive_project_name(target_repo) == "target-repo"


def test_derive_project_name_falls_back_to_dirname_when_no_remote(tmp_path):
    repo = tmp_path / "My Weird Repo Name"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "x.txt").write_text("hi\n", encoding="utf-8")
    _git(repo, "add", "x.txt")
    _git(repo, "commit", "-m", "initial")

    name = derive_project_name(repo)
    assert name == "my-weird-repo-name"
