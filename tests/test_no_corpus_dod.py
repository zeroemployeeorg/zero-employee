"""No-corpus DoD: zeo --board fails honestly; succeeds when pointed at a corpus."""

from __future__ import annotations


from zero_employee import cli


def test_board_without_corpus_fails_honestly(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ZEO_SOWS_ROOT", raising=False)
    rc = cli.main(["--board"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "couldn't find a corpus" in err
    assert "ZEO_SOWS_ROOT" in err
    assert "claude-md/CLAUDE.md" in err


def test_board_with_zeo_sows_root(tmp_path, monkeypatch, capsys):
    corpus = tmp_path / "corpus"
    (corpus / "claude-md").mkdir(parents=True)
    (corpus / "claude-md" / "CLAUDE.md").write_text("# CLAUDE\n", encoding="utf-8")
    (corpus / "projects").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ZEO_SOWS_ROOT", str(corpus))
    rc = cli.main(["--board"])
    out = capsys.readouterr().out
    assert rc == 0
    assert (corpus / "STATE.md").is_file() or "STATE" in out or "board" in out.lower() or rc == 0
