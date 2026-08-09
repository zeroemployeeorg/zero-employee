"""Session and repo cost proxies for zeo.

Two products share one rate table and one token estimator:

  Ahead of work — estimate tokens in a tree (or corpus artifacts) and multiply by
  a dated model rate → “already ~N tokens / ~$X before work begins.”

  After a run — prefer usage fields from a transcript or session-costs.jsonl
  (vendor ground truth) and multiply by the same rates → “this session cost ~$Y.”

Local token estimates are PROXY (tiktoken cl100k_base, else chars/3.6). Claude’s
tokenizer is not public; Anthropic documents that third-party tokenizers mis-estimate
Claude. Optional --count-via anthropic uses the free count_tokens endpoint to calibrate
a ratio on a small sample — never a full-tree blast.
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import subprocess
import tomllib
import urllib.error
import urllib.request
from typing import Any, Callable

# Keep in sync with core.CHARS_PER_TOKEN (chars fallback when tiktoken is absent).
CHARS_PER_TOKEN = 3.6

_RATES_PATH = pathlib.Path(__file__).parent / "data" / "model_rates.toml"

_BINARY_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".pdf",
        ".zip",
        ".gz",
        ".bz2",
        ".xz",
        ".7z",
        ".tar",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".otf",
        ".pyc",
        ".pyo",
        ".so",
        ".dylib",
        ".dll",
        ".exe",
        ".bin",
        ".o",
        ".a",
        ".class",
        ".jar",
        ".wasm",
        ".mp3",
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
        ".sqlite",
        ".db",
        ".lock",
    }
)

_WALK_SKIP_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".eggs",
        ".cursor",
    }
)

EstimateFn = Callable[[str], int]


class UnknownModelError(KeyError):
    """Raised when --model does not match a row in model_rates.toml."""


def _load_rates_raw(path: pathlib.Path | None = None) -> dict[str, Any]:
    p = path or _RATES_PATH
    with open(p, "rb") as f:
        return tomllib.load(f)


def load_rate_table(path: pathlib.Path | None = None) -> dict[str, Any]:
    """Return {as_of, source, default_model, models: {id: rates}}."""
    raw = _load_rates_raw(path)
    models = raw.get("models") or {}
    if not isinstance(models, dict) or not models:
        raise ValueError(f"no [models] in rate table: {path or _RATES_PATH}")
    return {
        "as_of": str(raw.get("as_of") or ""),
        "source": str(raw.get("source") or ""),
        "default_model": str(raw.get("default_model") or next(iter(models))),
        "models": {str(k): dict(v) for k, v in models.items()},
    }


def list_models(path: pathlib.Path | None = None) -> list[str]:
    return sorted(load_rate_table(path)["models"])


def get_model_rates(model: str | None = None, path: pathlib.Path | None = None) -> dict[str, Any]:
    """Resolve a model row. Fails closed with known ids if missing."""
    table = load_rate_table(path)
    mid = model or table["default_model"]
    row = table["models"].get(mid)
    if row is None:
        known = ", ".join(sorted(table["models"]))
        raise UnknownModelError(f"unknown model {mid!r}; known: {known}")
    return {
        "model": mid,
        "as_of": table["as_of"],
        "source": table["source"],
        "input_per_mtok": float(row.get("input_per_mtok") or 0),
        "output_per_mtok": float(row.get("output_per_mtok") or 0),
        "cache_read_per_mtok": float(row.get("cache_read_per_mtok") or 0),
        "cache_write_per_mtok": float(row.get("cache_write_per_mtok") or 0),
    }


def usd_for_usage(
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    rates: dict[str, Any],
) -> float:
    """DERIVED USD from token buckets and a rate row (per MTok)."""
    m = 1_000_000.0
    return (
        (input_tokens / m) * float(rates["input_per_mtok"])
        + (output_tokens / m) * float(rates["output_per_mtok"])
        + (cache_read_tokens / m) * float(rates["cache_read_per_mtok"])
        + (cache_write_tokens / m) * float(rates["cache_write_per_mtok"])
    )


def usd_for_input_tokens(tokens: int, rates: dict[str, Any]) -> float:
    """Ahead-of-work proxy: treat corpus/repo tokens as input-only."""
    return usd_for_usage(input_tokens=tokens, rates=rates)


# --- token estimators ---------------------------------------------------------

_tiktoken_enc = None
_tiktoken_tried = False


def tokenizer_label(count_via: str = "local") -> str:
    if count_via == "anthropic":
        return "anthropic:count_tokens (estimate; free endpoint)"
    if _ensure_tiktoken() is not None:
        return "tiktoken:cl100k_base (proxy; not Claude)"
    return f"chars/{CHARS_PER_TOKEN} (proxy; not Claude)"


def _ensure_tiktoken():
    global _tiktoken_enc, _tiktoken_tried
    if _tiktoken_tried:
        return _tiktoken_enc
    _tiktoken_tried = True
    try:
        import tiktoken  # type: ignore

        _tiktoken_enc = tiktoken.get_encoding("cl100k_base")
    except Exception:
        _tiktoken_enc = None
    return _tiktoken_enc


def estimate_tokens_local(text: str) -> int:
    """ESTIMATED tokens via tiktoken cl100k_base, else chars/CHARS_PER_TOKEN. Never a count."""
    enc = _ensure_tiktoken()
    if enc is not None:
        try:
            return len(enc.encode(text, disallowed_special=()))
        except Exception:
            pass
    return int(len(text) / CHARS_PER_TOKEN)


def anthropic_count_tokens(
    text: str,
    model: str,
    *,
    api_key: str | None = None,
    timeout: float = 30.0,
) -> int:
    """Call Anthropic's free POST /v1/messages/count_tokens. Raises on failure."""
    key = api_key or os.environ.get("ANTHROPIC_API_KEY") or ""
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set; cannot use --count-via anthropic")
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": text}],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages/count_tokens",
        data=body,
        method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"anthropic count_tokens HTTP {e.code}: {detail}") from e
    except Exception as e:
        raise RuntimeError(f"anthropic count_tokens failed: {e}") from e
    n = payload.get("input_tokens")
    if not isinstance(n, int):
        raise RuntimeError(f"anthropic count_tokens: unexpected payload {payload!r}")
    return n


def calibrate_ratio(
    samples: list[str],
    model: str,
    *,
    api_key: str | None = None,
    local_fn: EstimateFn | None = None,
) -> float:
    """claude_tokens / local_tokens over non-empty samples. Returns 1.0 if empty."""
    local_fn = local_fn or estimate_tokens_local
    local_sum = 0
    claude_sum = 0
    for text in samples:
        if not text:
            continue
        lt = local_fn(text)
        if lt <= 0:
            continue
        ct = anthropic_count_tokens(text, model, api_key=api_key)
        local_sum += lt
        claude_sum += ct
    if local_sum <= 0:
        return 1.0
    return claude_sum / local_sum


def make_estimator(
    count_via: str = "local",
    *,
    model: str | None = None,
    calibrate: bool = False,
    calibrate_samples: list[str] | None = None,
    api_key: str | None = None,
) -> tuple[EstimateFn, str, float | None]:
    """Return (estimate_fn, label, calibration_ratio_or_None).

    count_via=local: tiktoken/chars, optionally scaled by Anthropic calibration ratio.
    count_via=anthropic: every call hits the API (only for small samples — caller must not
    walk a whole repo with this).
    """
    ratio: float | None = None
    if count_via == "anthropic":
        mid = model or load_rate_table()["default_model"]

        def _fn(text: str) -> int:
            return anthropic_count_tokens(text, mid, api_key=api_key)

        return _fn, tokenizer_label("anthropic"), None

    if calibrate:
        samples = calibrate_samples or []
        mid = model or load_rate_table()["default_model"]
        ratio = calibrate_ratio(samples, mid, api_key=api_key)
        r = ratio

        def _fn_cal(text: str) -> int:
            return max(0, int(round(estimate_tokens_local(text) * r)))

        label = f"{tokenizer_label('local')} x anthropic_calibrate={ratio:.4f}"
        return _fn_cal, label, ratio

    return estimate_tokens_local, tokenizer_label("local"), None


# --- repo / file walks --------------------------------------------------------


def _looks_binary(path: pathlib.Path, sample: bytes | None = None) -> bool:
    if path.suffix.lower() in _BINARY_EXTENSIONS:
        return True
    if sample is None:
        try:
            with open(path, "rb") as f:
                sample = f.read(8192)
        except OSError:
            return True
    if b"\x00" in sample:
        return True
    return False


def _git_tracked_files(root: pathlib.Path) -> list[pathlib.Path] | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            timeout=60,
            check=False,
        )
    except Exception:
        return None
    if out.returncode != 0:
        return None
    names = [n for n in out.stdout.split(b"\x00") if n]
    files = []
    for raw in names:
        try:
            rel = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        p = root / rel
        if p.is_file():
            files.append(p)
    return files


def _walk_files(root: pathlib.Path) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _WALK_SKIP_DIRS and not d.startswith(".git")]
        for name in filenames:
            p = pathlib.Path(dirpath) / name
            files.append(p)
    return files


def iter_repo_text_files(root: pathlib.Path) -> list[pathlib.Path]:
    root = pathlib.Path(root).resolve()
    tracked = _git_tracked_files(root)
    candidates = tracked if tracked is not None else _walk_files(root)
    out: list[pathlib.Path] = []
    for p in candidates:
        if not p.is_file():
            continue
        if _looks_binary(p):
            continue
        out.append(p)
    return out


def repo_token_report(
    root: pathlib.Path | str,
    *,
    estimate: EstimateFn | None = None,
    top_n: int = 20,
    model: str | None = None,
    rates_path: pathlib.Path | None = None,
) -> dict[str, Any]:
    """Ahead-of-work: estimate tokens across a tree and DERIVE input-only USD."""
    root = pathlib.Path(root).resolve()
    estimate = estimate or estimate_tokens_local
    rates = get_model_rates(model, rates_path)
    files = iter_repo_text_files(root)
    per_file: list[dict[str, Any]] = []
    total = 0
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        tok = estimate(text)
        total += tok
        try:
            rel = str(p.relative_to(root))
        except ValueError:
            rel = str(p)
        per_file.append({"path": rel, "tokens": tok, "bytes": len(text.encode("utf-8"))})
    per_file.sort(key=lambda x: -x["tokens"])
    usd = usd_for_input_tokens(total, rates)
    return {
        "kind": "repo-cost",
        "root": str(root),
        "files": len(per_file),
        "tokens": total,
        "usd": usd,
        "model": rates["model"],
        "as_of": rates["as_of"],
        "source": rates["source"],
        "tokenizer": tokenizer_label("local"),
        "top": per_file[:top_n],
        "honesty": "ESTIMATE tokens x DERIVED USD (input rate only); not vendor billing",
    }


def fixed_tax_sample_texts(root: pathlib.Path) -> list[str]:
    """Texts used for Anthropic calibration (CLAUDE.md + roles + authoring)."""
    root = pathlib.Path(root).resolve()
    samples: list[str] = []
    for rel in ("claude-md/CLAUDE.md",):
        f = root / rel
        if f.is_file():
            samples.append(f.read_text(encoding="utf-8", errors="replace"))
    for d in ("roles", "authoring"):
        dd = root / d
        if dd.is_dir():
            for f in sorted(dd.glob("*.md")):
                samples.append(f.read_text(encoding="utf-8", errors="replace"))
    return samples


# --- session usage ------------------------------------------------------------


def _as_int(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _usage_from_obj(obj: Any) -> dict[str, int] | None:
    """Pull input/output/cache token fields from a nested JSON object."""
    if not isinstance(obj, dict):
        return None
    candidates = [obj]
    for k in ("usage", "message", "response", "result", "data"):
        nested = obj.get(k)
        if isinstance(nested, dict):
            candidates.append(nested)
            u = nested.get("usage")
            if isinstance(u, dict):
                candidates.append(u)
    for c in candidates:
        if not isinstance(c, dict):
            continue
        # Common Anthropic / Claude Code shapes
        inp = c.get("input_tokens", c.get("inputTokens", c.get("prompt_tokens")))
        out = c.get("output_tokens", c.get("outputTokens", c.get("completion_tokens")))
        if inp is None and out is None:
            # some logs store total only
            if "tokens" in c and "usd" not in c:
                continue
            continue
        cache_read = c.get(
            "cache_read_input_tokens",
            c.get("cache_read_tokens", c.get("cacheReadInputTokens", 0)),
        )
        cache_write = c.get(
            "cache_creation_input_tokens",
            c.get("cache_write_tokens", c.get("cacheCreationInputTokens", 0)),
        )
        return {
            "input_tokens": _as_int(inp),
            "output_tokens": _as_int(out),
            "cache_read_tokens": _as_int(cache_read),
            "cache_write_tokens": _as_int(cache_write),
        }
    return None


def parse_transcript_usage(path: pathlib.Path | str) -> dict[str, Any]:
    """Sum usage fields from a Claude Code (or similar) JSONL transcript.

    Dedupes by message.id when present: streaming/tool-chunk events repeat the same
    usage snapshot under one id; summing every line overcounts (measured ~2.7x).
    """
    path = pathlib.Path(path)
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "events": 0,
        "lines": 0,
        "source": "transcript",
        "path": str(path),
    }
    models: list[str] = []
    # message.id -> (model, usage_dict); anonymous when no id
    seen: dict[str, tuple[str | None, dict[str, int]]] = {}
    anonymous: list[tuple[str | None, dict[str, int]]] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        totals["lines"] += 1
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        msg = obj.get("message") if isinstance(obj.get("message"), dict) else None
        usage = _usage_from_obj(obj)
        if usage is None:
            continue
        model = None
        mid = None
        if msg:
            model = msg.get("model") if isinstance(msg.get("model"), str) else None
            mid = msg.get("id")
        if not model and isinstance(obj.get("model"), str):
            model = obj.get("model")
        if mid is not None:
            seen[str(mid)] = (model, usage)
        else:
            anonymous.append((model, usage))

    for model, usage in list(seen.values()) + anonymous:
        totals["input_tokens"] += usage["input_tokens"]
        totals["output_tokens"] += usage["output_tokens"]
        totals["cache_read_tokens"] += usage["cache_read_tokens"]
        totals["cache_write_tokens"] += usage["cache_write_tokens"]
        totals["events"] += 1
        if isinstance(model, str) and model and model not in models:
            models.append(model)
    totals["models_seen"] = models
    return totals


def append_session_cost_log(path: pathlib.Path | str, report: dict[str, Any]) -> None:
    """Append one JSONL record from a session_cost_report to a cost log file."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "kind": "session-cost",
        "usage_source": report.get("usage_source"),
        "path": report.get("path"),
        "events": report.get("events"),
        "input_tokens": report.get("input_tokens"),
        "output_tokens": report.get("output_tokens"),
        "cache_read_tokens": report.get("cache_read_tokens"),
        "cache_write_tokens": report.get("cache_write_tokens"),
        "usd": report.get("usd"),
        "model": report.get("model"),
        "as_of": report.get("as_of"),
        "honesty": report.get("honesty"),
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def parse_cost_log(path: pathlib.Path | str) -> dict[str, Any]:
    """Sum tools/stream-instruments/session-costs.jsonl style lines."""
    path = pathlib.Path(path)
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "events": 0,
        "lines": 0,
        "source": "cost-log",
        "path": str(path),
        "logged_usd": 0.0,
    }
    models: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        totals["lines"] += 1
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        usage = _usage_from_obj(obj)
        if usage is None:
            # flat fields at top level
            if any(k in obj for k in ("input_tokens", "output_tokens", "tokens_in", "tokens_out")):
                usage = {
                    "input_tokens": _as_int(obj.get("input_tokens", obj.get("tokens_in", 0))),
                    "output_tokens": _as_int(obj.get("output_tokens", obj.get("tokens_out", 0))),
                    "cache_read_tokens": _as_int(obj.get("cache_read_tokens", obj.get("cache_read_input_tokens", 0))),
                    "cache_write_tokens": _as_int(
                        obj.get("cache_write_tokens", obj.get("cache_creation_input_tokens", 0))
                    ),
                }
        if usage is None:
            continue
        totals["input_tokens"] += usage["input_tokens"]
        totals["output_tokens"] += usage["output_tokens"]
        totals["cache_read_tokens"] += usage["cache_read_tokens"]
        totals["cache_write_tokens"] += usage["cache_write_tokens"]
        totals["events"] += 1
        if "usd" in obj:
            try:
                totals["logged_usd"] += float(obj["usd"])
            except (TypeError, ValueError):
                pass
        m = obj.get("model")
        if isinstance(m, str) and m and m not in models:
            models.append(m)
    totals["models_seen"] = models
    return totals


def session_cost_report(
    *,
    transcript: pathlib.Path | str | None = None,
    cost_log: pathlib.Path | str | None = None,
    model: str | None = None,
    rates_path: pathlib.Path | None = None,
) -> dict[str, Any]:
    """After-run: usage from transcript or cost log × dated rates → DERIVED USD."""
    if transcript is None and cost_log is None:
        raise ValueError("session_cost_report requires --transcript or --cost-log")
    if transcript is not None:
        usage = parse_transcript_usage(transcript)
    else:
        usage = parse_cost_log(cost_log)  # type: ignore[arg-type]

    rates = get_model_rates(model, rates_path)
    # If caller did not pin a model and the log saw exactly one, prefer that when known.
    if model is None and usage.get("models_seen"):
        seen = usage["models_seen"]
        table = load_rate_table(rates_path)
        for m in seen:
            if m in table["models"]:
                rates = get_model_rates(m, rates_path)
                break

    usd = usd_for_usage(
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        cache_read_tokens=usage["cache_read_tokens"],
        cache_write_tokens=usage["cache_write_tokens"],
        rates=rates,
    )
    return {
        "kind": "session-cost",
        "usage_source": usage["source"],
        "path": usage["path"],
        "events": usage["events"],
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "cache_read_tokens": usage["cache_read_tokens"],
        "cache_write_tokens": usage["cache_write_tokens"],
        "total_tokens": (
            usage["input_tokens"] + usage["output_tokens"] + usage["cache_read_tokens"] + usage["cache_write_tokens"]
        ),
        "usd": usd,
        "logged_usd": usage.get("logged_usd"),
        "model": rates["model"],
        "as_of": rates["as_of"],
        "source": rates["source"],
        "models_seen": usage.get("models_seen") or [],
        "honesty": "usage (from transcript/cost-log) x DERIVED USD; not vendor invoice",
    }


def format_usd(n: float) -> str:
    if n >= 1:
        return f"${n:.2f}"
    if n >= 0.01:
        return f"${n:.3f}"
    return f"${n:.4f}"
