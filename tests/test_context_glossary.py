"""A1: CONTEXT.md carries the product vocabulary and cross-project distinctions."""

from __future__ import annotations

import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[1]
_CONTEXT = (_REPO / "CONTEXT.md").read_text(encoding="utf-8")


REQUIRED_HEADINGS = (
    "corpus",
    "project",
    "stream",
    "SOW",
    "ruling",
    "design",
    "learning",
    "intake",
    "seat type",
    "seat instance",
    "runtime address",
    "instance registry",
    "relay message",
    "supervisor",
    "execution",
    "iteration",
    "session",
    "receipt",
    "board / view versus source artifact",
    "binding",
    "acknowledgement",
    "conformance",
    "landing",
    "delivery",
    "host repository",
    "governed repository",
    "corpus root",
    "worktree",
    "branch",
)

REQUIRED_DISTINCTIONS = (
    "seat type",
    "seat instance",
    "runtime address",
    "organizational identity",
    "remote contain",
    "board row is a derived pointer",
    "session fork",
    "branch fork",
    "worktree isolation",
)


def test_context_md_exists_at_repo_root():
    assert (_REPO / "CONTEXT.md").is_file()


def test_required_terms_have_headings_and_avoid_lists():
    lower = _CONTEXT.lower()
    for term in REQUIRED_HEADINGS:
        heading = f"## {term.lower()}"
        assert heading in lower, f"missing glossary heading for {term!r}"
    # Every defined term carries an Avoid list (ruling A1).
    assert _CONTEXT.count("**Avoid:**") >= len(REQUIRED_HEADINGS)


def test_cross_project_distinctions_remain_present():
    lower = _CONTEXT.lower()
    for needle in REQUIRED_DISTINCTIONS:
        assert needle in lower, f"missing distinction {needle!r}"
    assert "agentprovider" in lower.replace(" ", "") or "agent provider" in lower
    assert "not a persistent seat instance" in lower or "not mean master is already" in lower
    assert "constructor" in lower
    assert "zeo relay start" in lower
    assert "rulings decide conflicts" in lower
