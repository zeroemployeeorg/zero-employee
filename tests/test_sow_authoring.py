"""SOW authoring ergonomics: new/set/doctor/draft without hand-written YAML."""

from __future__ import annotations

import io
import json
import pathlib

from zero_employee import cli
from zero_employee.core import extract_frontmatter, lint_file, parse_current_rev, find_canonical_claude_md
from zero_employee.scaffold import init_corpus, scaffold_project_stream
from zero_employee.sow_authoring import (
    SCHEMA_REV,
    add_list_value,
    body_contains_frontmatter,
    canonical_sow_filename,
    create_sow,
    doctor_file,
    draft_sow,
    git_changed_markdown,
    remove_list_value,
    render_sow,
    set_field,
    split_frontmatter_body,
    transactional_create,
)


def _corpus(tmp_path: pathlib.Path) -> pathlib.Path:
    root = tmp_path / "org"
    init_corpus(root)
    return root


def test_sow_new_happy_path_grades(tmp_path):
    root = _corpus(tmp_path)
    result, err = create_sow(
        root,
        project="test-project",
        stream="test-stream",
        title="Test SOW",
        done_when="pytest -> 0 failures",
        restaufwand=1,
    )
    assert err == ""
    assert result is not None
    path = root / result.path
    assert path.is_file()
    assert "SOW-01" in path.name
    canon = find_canonical_claude_md(root)
    rev = parse_current_rev(canon.read_text(encoding="utf-8"))
    status, findings = lint_file(path, current_rev=rev, root=root, commit_mode=True)
    assert status == "PASS", findings


def test_sow_new_auto_increments_n(tmp_path):
    root = _corpus(tmp_path)
    first, _ = create_sow(root, project="p", stream="s", title="First SOW", done_when="x", restaufwand=1)
    second, _ = create_sow(root, project="p", stream="s", title="Second SOW", done_when="x", restaufwand=1)
    assert first is not None and second is not None
    assert first.n == 1
    assert second.n == 2
    assert "SOW-02" in second.path


def test_yaml_edge_cases_roundtrip(tmp_path):
    root = _corpus(tmp_path)
    title = 'Title: with "quotes" and café — colon'
    result, err = create_sow(
        root,
        project="edge",
        stream="yaml-edge",
        title=title,
        done_when='pytest -k "colon: case" -> 0 failures',
        restaufwand=1,
    )
    assert result is not None, err
    text = (root / result.path).read_text(encoding="utf-8")
    fm = extract_frontmatter(text)
    assert isinstance(fm, dict)
    assert fm["done_when"] == 'pytest -k "colon: case" -> 0 failures'
    assert fm["schema_rev"] == SCHEMA_REV


def test_transactional_refuse_leaves_no_file(tmp_path):
    root = _corpus(tmp_path)
    chain = root / "projects" / "p" / "sow" / "s"
    chain.mkdir(parents=True)
    # Missing done_when for working status DESIGN
    bad = {
        "sow": "s",
        "n": 1,
        "schema_rev": 17,
        "project": "p",
        "status": "DESIGN",
        "lifecycle": "DESIGN-MEMO",
        "created": "2026-08-09",
        "updated": "2026-08-09",
        "genre": "sow",
        "restaufwand": 1,
        "sow_repo": "example-org/org",
        "work_repo": "example-org/p",
        "requested_by": "test",
    }
    content = render_sow(bad, "# body\n")
    dest = chain / canonical_sow_filename("s", 1, "refuse")
    ok, reason, _ = transactional_create(dest, content, root=root)
    assert not ok
    assert "done_when" in reason.lower() or "schema" in reason.lower() or "working" in reason.lower()
    assert not dest.exists()
    assert list(chain.glob("*.md")) == []


def test_sow_set_preserves_body(tmp_path):
    root = _corpus(tmp_path)
    result, _ = create_sow(
        root,
        project="zero-employee",
        stream="doctrine-migration",
        title="Make local doctrine migration first-class",
        done_when="pytest passes",
        restaufwand=5,
    )
    path = root / result.path
    original = path.read_text(encoding="utf-8")
    _, body = split_frontmatter_body(original)
    ok, reason = set_field(path, "status", "PROGRESS", root=root)
    assert ok, reason
    text = path.read_text(encoding="utf-8")
    _, body_after = split_frontmatter_body(text)
    assert body_after == body
    fm = extract_frontmatter(text)
    assert fm["status"] == "PROGRESS"


def test_sow_add_remove_binds(tmp_path):
    root = _corpus(tmp_path)
    result, _ = create_sow(
        root,
        project="p",
        stream="s",
        title="Binds Test",
        done_when="x",
        restaufwand=1,
    )
    path = root / result.path
    ok, reason = add_list_value(path, "binds", "doctrine-migration", root=root)
    assert ok, reason
    fm = extract_frontmatter(path.read_text(encoding="utf-8"))
    assert "doctrine-migration" in fm["binds"]
    ok, reason = remove_list_value(path, "binds", "doctrine-migration", root=root)
    assert ok, reason
    fm = extract_frontmatter(path.read_text(encoding="utf-8"))
    assert not fm.get("binds")


def test_cli_sow_new(tmp_path, capsys, monkeypatch):
    root = _corpus(tmp_path)
    monkeypatch.chdir(root)
    # Non-interactive: avoid edit prompt
    monkeypatch.setattr("sys.stdin", io.StringIO("n\n"))
    rc = cli.main(
        [
            "sow",
            "new",
            "test-project",
            "test-stream",
            "--title",
            "Test SOW",
            "--done-when",
            "pytest -> 0 failures",
            "--restaufwand",
            "1",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "Created:" in out
    assert "schema_rev: 17" in out
    assert "✓ zeo lint passes" in out


def test_draft_rejects_frontmatter_then_accepts_body(tmp_path):
    root = _corpus(tmp_path)
    calls = {"n": 0}

    def fake_model(prompt, tag="x", *a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return "---\nschema_rev: 17\nsow: s\n---\n\n## Problem\nbad\n"
        return "## Problem\n\nGood problem.\n\n## Desired invariant\n\nIt works.\n\n## Approach\n\nDo it.\n\n## Done when\n\npytest passes\n"

    peer_in = io.StringIO(
        json.dumps({"role": "peer", "action": "seed", "notes": "write a design sow"})
        + "\n"
        + json.dumps({"role": "peer", "action": "revise", "notes": "no yaml"})
        + "\n"
        + json.dumps({"role": "peer", "action": "accept"})
        + "\n"
    )
    peer_out = io.StringIO()
    result, err = draft_sow(
        root,
        project="p",
        stream="draft-stream",
        title="Draft Title",
        status="DESIGN",
        done_when="pytest passes",
        restaufwand=1,
        peer="agent",
        model_fn=fake_model,
        stdin=peer_in,
        stdout=peer_out,
        cap=5,
    )
    assert result is not None, err
    text = (root / result.path).read_text(encoding="utf-8")
    assert "## Problem" in text
    assert "schema_rev: 17" in text.split("---")[1]
    # body should not re-introduce a second frontmatter from model
    body = text.split("---", 2)[-1]
    assert not body_contains_frontmatter(body)


def test_doctor_ready(tmp_path):
    root = _corpus(tmp_path)
    result, _ = create_sow(
        root,
        project="p",
        stream="s",
        title="Doctor Me",
        done_when="ok",
        restaufwand=1,
    )
    ready, oks, fails = doctor_file(root / result.path, root=root)
    assert ready, fails
    assert any("lint passes" in x for x in oks)


def test_doctor_changed_filters(tmp_path):
    root = _corpus(tmp_path)
    result, _ = create_sow(
        root,
        project="p",
        stream="s",
        title="Changed",
        done_when="ok",
        restaufwand=1,
    )
    # Without git, git_changed may be empty — still callable
    paths = git_changed_markdown(root)
    assert isinstance(paths, list)


def test_scaffold_uses_shared_serializer(tmp_path):
    root = _corpus(tmp_path)
    info = scaffold_project_stream(root, "ducktyper", "ui-refresh", title="UI Framework Refresh")
    sow = root / info["sow"]
    fm = extract_frontmatter(sow.read_text(encoding="utf-8"))
    assert fm["schema_rev"] == 17
    assert fm["project"] == "ducktyper"
    # yaml library dump — values with special chars would be quoted; plain ints unquoted
    assert isinstance(fm["n"], int)


def test_body_contains_frontmatter_detection():
    assert body_contains_frontmatter("---\nschema_rev: 17\n---\n\n## Problem\n")
    assert not body_contains_frontmatter("## Problem\n\nHello\n")
