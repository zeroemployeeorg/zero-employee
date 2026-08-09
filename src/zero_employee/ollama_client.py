"""Shared Ollama HTTP/CLI client used by migrate and sow draft."""

from __future__ import annotations

import json
import socket
import subprocess
import urllib.error
import urllib.request


DEFAULT_MODEL = "gemma4:latest"
DEFAULT_TIMEOUT = 180
OLLAMA_GENERATE_URL = "http://127.0.0.1:11434/api/generate"


def ollama_model(
    prompt: str,
    tag: str = DEFAULT_MODEL,
    timeout: int = DEFAULT_TIMEOUT,
    *,
    response_format: dict | None = None,
    temperature: float = 0,
    seed: int | None = 23,
) -> str:
    """Call local Ollama `/api/generate`, falling back to `ollama run` CLI."""
    payload_obj: dict = {
        "model": tag,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }
    if seed is not None:
        payload_obj["options"]["seed"] = seed
    if response_format is not None:
        payload_obj["format"] = response_format

    payload = json.dumps(payload_obj).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_GENERATE_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
            answer = result.get("response")
            if not isinstance(answer, str):
                raise RuntimeError("Ollama response has no string `response`")
            return answer
    except (
        urllib.error.URLError,
        TimeoutError,
        socket.timeout,
        json.JSONDecodeError,
    ) as http_error:
        try:
            result = subprocess.run(
                ["ollama", "run", "--hidethinking", tag],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Ollama HTTP and CLI calls timed out") from exc

        if result.returncode != 0:
            detail = result.stderr.strip()[:300]
            raise RuntimeError(f"Ollama HTTP failed ({http_error}); CLI failed ({result.returncode}): {detail}")

        return result.stdout
