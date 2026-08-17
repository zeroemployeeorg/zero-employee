"""Session / repo cost subsystem — rates, local estimate, session parse (no network)."""

from __future__ import annotations

import json
import pathlib
import subprocess
import textwrap

import pytest

from zero_employee import cost
from zero_employee import cli


@pytest.fixture
def rates_file(tmp_path: pathlib.Path) -> pathlib.Path:
    p = tmp_path / "rates.toml"
    p.write_text(
        textwrap.dedent(
            """\
            as_of = "2099-01-01"
            source = "test"
            default_model = "test-model"

            [models."test-model"]
            input_per_mtok = 10.0
            output_per_mtok = 50.0
            cache_read_per_mtok = 1.0
            cache_write_per_mtok = 12.5

            [models."other-model"]
            input_per_mtok = 1.0
            output_per_mtok = 2.0
            """
        ),
        encoding="utf-8",
    )
    return p


def test_load_rate_table_and_usd_math(rates_file):
    table = cost.load_rate_table(rates_file)
    assert table["as_of"] == "2099-01-01"
    assert table["default_model"] == "test-model"
    rates = cost.get_model_rates(None, rates_file)
    assert rates["model"] == "test-model"
    # 1M input @ $10 + 100k output @ $50 = 10 + 5 = 15
    usd = cost.usd_for_usage(input_tokens=1_000_000, output_tokens=100_000, rates=rates)
    assert usd == pytest.approx(15.0)
    assert cost.usd_for_input_tokens(500_000, rates) == pytest.approx(5.0)


def test_unknown_model_fails_closed(rates_file):
    with pytest.raises(cost.UnknownModelError) as ei:
        cost.get_model_rates("nope", rates_file)
    assert "test-model" in str(ei.value)
    assert "other-model" in str(ei.value)


def test_estimate_tokens_local_positive():
    n = cost.estimate_tokens_local("hello world " * 50)
    assert isinstance(n, int)
    assert n > 0
    # tiktoken should be available as a package dep
    assert "tiktoken" in cost.tokenizer_label("local") or "chars/" in cost.tokenizer_label("local")


def test_repo_token_report(tmp_path, rates_file, monkeypatch):
    (tmp_path / "a.py").write_text("print('hi')\n" * 20, encoding="utf-8")
    (tmp_path / "b.md").write_text("# title\n\n" + ("word " * 200), encoding="utf-8")
    (tmp_path / "skip.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    report = cost.repo_token_report(tmp_path, model="test-model", rates_path=rates_file)
    assert report["files"] >= 2
    assert report["tokens"] > 0
    assert report["usd"] > 0
    assert report["model"] == "test-model"
    paths = {row["path"] for row in report["top"]}
    assert "skip.png" not in paths
    assert any(p.endswith(".md") or p.endswith(".py") for p in paths)


def test_parse_transcript_usage(tmp_path):
    p = tmp_path / "t.jsonl"
    lines = [
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        {
            "type": "assistant",
            "message": {
                "model": "test-model",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "cache_read_input_tokens": 50,
                    "cache_creation_input_tokens": 10,
                },
            },
        },
        {
            "type": "assistant",
            "message": {
                "usage": {"input_tokens": 30, "output_tokens": 5},
            },
        },
    ]
    p.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    u = cost.parse_transcript_usage(p)
    assert u["events"] == 2
    assert u["input_tokens"] == 130
    assert u["output_tokens"] == 25
    assert u["cache_read_tokens"] == 50
    assert u["cache_write_tokens"] == 10
    assert "test-model" in u["models_seen"]


def test_parse_cost_log_and_session_report(tmp_path, rates_file):
    p = tmp_path / "session-costs.jsonl"
    p.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "model": "test-model",
                        "input_tokens": 1_000_000,
                        "output_tokens": 0,
                        "usd": 9.99,
                    }
                ),
                json.dumps({"input_tokens": 0, "output_tokens": 100_000}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    report = cost.session_cost_report(cost_log=p, rates_path=rates_file)
    assert report["input_tokens"] == 1_000_000
    assert report["output_tokens"] == 100_000
    # 10 + 5 = 15 from rates
    assert report["usd"] == pytest.approx(15.0)
    assert report["logged_usd"] == pytest.approx(9.99)
    assert report["model"] == "test-model"


def test_anthropic_count_tokens_mocked(monkeypatch):
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"input_tokens": 42}'

    def fake_urlopen(req, timeout=30.0):
        assert b"count_tokens" in req.full_url.encode() or "count_tokens" in req.full_url
        return _Resp()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(cost.urllib.request, "urlopen", fake_urlopen)
    assert cost.anthropic_count_tokens("hello", "claude-sonnet-4-6") == 42


def test_anthropic_count_tokens_no_credential_names_both_remediations(monkeypatch):
    """RULING-279 s4: the exact failure mode measured this session — unset
    ANTHROPIC_API_KEY, no `ant` on PATH, call anthropic_count_tokens. The old bare
    "ANTHROPIC_API_KEY not set" message named only the symptom. The fix must name
    BOTH remediation paths (set the env var; install+auth `ant`), not a bare
    "not set" — so a caller in a live Claude Code session (this tool's most common
    execution context, per the ruling) has an actual next step.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as ei:
        cost.anthropic_count_tokens("hello", "claude-sonnet-4-6")
    msg = str(ei.value)
    assert "ANTHROPIC_API_KEY" in msg
    assert "ant" in msg and "auth login" in msg
    assert "--api-key-env" in msg


def test_anthropic_count_tokens_respects_api_key_env_override(monkeypatch):
    """--api-key-env <VARNAME>: a caller whose credential lives under a non-default
    env var name is not stuck (RULING-279 s5's narrow fix, not full ant-CLI
    precedence-chain resolution)."""

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"input_tokens": 7}'

    def fake_urlopen(req, timeout=30.0):
        return _Resp()

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("MY_CUSTOM_KEY", "test-key")
    monkeypatch.setattr(cost.urllib.request, "urlopen", fake_urlopen)
    n = cost.anthropic_count_tokens("hello", "claude-sonnet-4-6", api_key_env="MY_CUSTOM_KEY")
    assert n == 7

    # And with neither the default nor the custom var set, it still fails loudly
    # naming the custom var name it actually checked (not a hardcoded default).
    monkeypatch.delenv("MY_CUSTOM_KEY", raising=False)
    with pytest.raises(RuntimeError) as ei:
        cost.anthropic_count_tokens("hello", "claude-sonnet-4-6", api_key_env="MY_CUSTOM_KEY")
    assert "MY_CUSTOM_KEY" in str(ei.value)


def test_calibrate_ratio_mocked(monkeypatch):
    monkeypatch.setattr(
        cost,
        "anthropic_count_tokens",
        lambda text, model, api_key=None, api_key_env="ANTHROPIC_API_KEY": 200,
    )
    monkeypatch.setattr(cost, "estimate_tokens_local", lambda text: 100)
    r = cost.calibrate_ratio(["abc", "def"], "test-model")
    assert r == pytest.approx(2.0)


def test_cli_repo_cost_json(tmp_path, monkeypatch, capsys):
    (tmp_path / "readme.md").write_text("alpha beta gamma " * 40, encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    # Point rate table at package default; use a known model id
    rc = cli.main(["--repo-cost", str(tmp_path), "--model", "claude-haiku-4-5", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["kind"] == "repo-cost"
    assert data["tokens"] > 0
    assert data["model"] == "claude-haiku-4-5"
    assert "usd" in data


def test_cli_session_cost_json(tmp_path, capsys):
    log = tmp_path / "c.jsonl"
    log.write_text(
        json.dumps(
            {
                "input_tokens": 1000,
                "output_tokens": 500,
                "model": "claude-haiku-4-5",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    rc = cli.main(
        [
            "--session-cost",
            "--cost-log",
            str(log),
            "--model",
            "claude-haiku-4-5",
            "--json",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["kind"] == "session-cost"
    assert data["input_tokens"] == 1000
    assert data["output_tokens"] == 500
    assert data["usd"] > 0


def test_cli_unknown_model_fails(capsys):
    rc = cli.main(["--repo-cost", ".", "--model", "not-a-real-model"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "unknown model" in err


def test_packaged_rates_load():
    table = cost.load_rate_table()
    assert table["as_of"]
    assert "claude-sonnet-4-6" in table["models"]
    rates = cost.get_model_rates("claude-sonnet-4-6")
    assert rates["input_per_mtok"] == 3.0
    assert rates["output_per_mtok"] == 15.0
