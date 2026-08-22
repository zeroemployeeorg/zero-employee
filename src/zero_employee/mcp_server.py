"""Minimal MCP stdio server wrapping the same ZEO library as the CLI.

No extra dependency: JSON-RPC 2.0 over newline-delimited stdin/stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

from . import relay as relay_mod

ToolFn = Callable[[dict[str, Any]], dict[str, Any]]


def _corpus(arguments: dict[str, Any]) -> Path:
    from .cli import _discover_root

    raw = arguments.get("root")
    root = _discover_root(raw) if raw else _discover_root(None)
    if root is None:
        raise RuntimeError("could not discover corpus (claude-md/CLAUDE.md)")
    return root


def _tool_orient(arguments: dict[str, Any]) -> dict[str, Any]:
    from .orient import build_orientation, render_orientation_json

    root = _corpus(arguments)
    return json.loads(render_orientation_json(build_orientation(root=root)))


def _tool_triage(arguments: dict[str, Any]) -> dict[str, Any]:
    from .cli import main
    from io import StringIO
    import contextlib

    root = _corpus(arguments)
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["--triage", str(root)])
    return {"exit_code": rc, "text": buf.getvalue()}


def _tool_inbox(arguments: dict[str, Any]) -> dict[str, Any]:
    from .cli import main
    from io import StringIO
    import contextlib

    stream = arguments.get("stream")
    if not stream:
        raise RuntimeError("stream is required")
    root = _corpus(arguments)
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["--inbox", str(stream), str(root)])
    return {"exit_code": rc, "text": buf.getvalue()}


def _tool_relay_resolve(arguments: dict[str, Any]) -> dict[str, Any]:
    root = _corpus(arguments)
    found = relay_mod.resolve(
        root,
        seat=arguments.get("seat"),
        instance_id=arguments.get("instance"),
    )
    return {"instances": [i.model_dump(mode="json") for i in found]}


def _tool_relay_send(arguments: dict[str, Any]) -> dict[str, Any]:
    root = _corpus(arguments)
    refs = arguments.get("artifact_refs") or []
    if isinstance(refs, str):
        refs = [refs]
    msg = relay_mod.send(
        root,
        from_instance=arguments["from_instance"],
        to_instance=arguments["to_instance"],
        kind=arguments.get("kind") or "follow-up",
        body=arguments.get("body") or "",
        conversation_id=arguments.get("conversation_id"),
        reply_to=arguments.get("reply_to"),
        artifact_refs=list(refs),
        message_id=arguments.get("message_id"),
    )
    return msg.model_dump(mode="json")


def _tool_relay_receive(arguments: dict[str, Any]) -> dict[str, Any]:
    root = _corpus(arguments)
    instance = arguments.get("instance")
    if not instance:
        raise RuntimeError("instance is required")
    msgs = relay_mod.receive(root, instance)
    return {"messages": [m.model_dump(mode="json") for m in msgs]}


def _tool_relay_ack(arguments: dict[str, Any]) -> dict[str, Any]:
    root = _corpus(arguments)
    mid = arguments.get("message_id") or arguments.get("message")
    if not mid:
        raise RuntimeError("message_id is required")
    return relay_mod.ack(root, mid).model_dump(mode="json")


def _tool_relay_status(arguments: dict[str, Any]) -> dict[str, Any]:
    return relay_mod.status_payload(_corpus(arguments))


def _tool_doctor(arguments: dict[str, Any]) -> dict[str, Any]:
    from .runtimes.codex import probe_codex

    return {"codex": probe_codex().as_dict()}


def _tool_verify(arguments: dict[str, Any]) -> dict[str, Any]:
    from .cli import main
    from io import StringIO
    import contextlib

    path = arguments.get("path")
    if not path:
        raise RuntimeError("path is required")
    buf = StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = main([str(path)])
    return {"exit_code": rc, "text": buf.getvalue()}


TOOLS: dict[str, tuple[str, dict[str, Any], ToolFn]] = {
    "zeo_orient": ("Agent briefing JSON", {"type": "object", "properties": {"root": {"type": "string"}}}, _tool_orient),
    "zeo_triage": ("Operator worklist", {"type": "object", "properties": {"root": {"type": "string"}}}, _tool_triage),
    "zeo_inbox": (
        "Artifact inbox for one stream",
        {
            "type": "object",
            "properties": {"stream": {"type": "string"}, "root": {"type": "string"}},
            "required": ["stream"],
        },
        _tool_inbox,
    ),
    "zeo_relay_resolve": (
        "Resolve active seat instances",
        {
            "type": "object",
            "properties": {
                "seat": {"type": "string"},
                "instance": {"type": "string"},
                "root": {"type": "string"},
            },
        },
        _tool_relay_resolve,
    ),
    "zeo_relay_send": (
        "Send a relay message between instances",
        {
            "type": "object",
            "properties": {
                "from_instance": {"type": "string"},
                "to_instance": {"type": "string"},
                "kind": {"type": "string"},
                "body": {"type": "string"},
                "conversation_id": {"type": "string"},
                "reply_to": {"type": "string"},
                "artifact_refs": {"type": "array", "items": {"type": "string"}},
                "message_id": {"type": "string"},
                "root": {"type": "string"},
            },
            "required": ["from_instance", "to_instance"],
        },
        _tool_relay_send,
    ),
    "zeo_relay_receive": (
        "Receive pending relay messages",
        {
            "type": "object",
            "properties": {"instance": {"type": "string"}, "root": {"type": "string"}},
            "required": ["instance"],
        },
        _tool_relay_receive,
    ),
    "zeo_relay_ack": (
        "Acknowledge a relay message",
        {
            "type": "object",
            "properties": {"message_id": {"type": "string"}, "root": {"type": "string"}},
            "required": ["message_id"],
        },
        _tool_relay_ack,
    ),
    "zeo_relay_status": (
        "Relay registry and ledger counts",
        {"type": "object", "properties": {"root": {"type": "string"}}},
        _tool_relay_status,
    ),
    "zeo_doctor": ("Codex capability probe", {"type": "object", "properties": {}}, _tool_doctor),
    "zeo_verify": (
        "Lint one governed file",
        {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        _tool_verify,
    ),
}


def _tools_list() -> list[dict[str, Any]]:
    return [{"name": name, "description": desc, "inputSchema": schema} for name, (desc, schema, _) in TOOLS.items()]


def _handle(req: dict[str, Any]) -> dict[str, Any]:
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params") or {}
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": params.get("protocolVersion") or "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "zeo", "version": "0.7.0"},
            },
        }
    if method == "notifications/initialized":
        return {}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": _tools_list()}}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in TOOLS:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"unknown tool {name}"},
            }
        try:
            result = TOOLS[name][2](arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]},
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": str(exc)}],
                },
            }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"unknown method {method}"},
    }


def serve(stdin=None, stdout=None) -> int:
    inn = stdin or sys.stdin
    out = stdout or sys.stdout
    for line in inn:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = _handle(req)
        if not resp:
            continue
        out.write(json.dumps(resp) + "\n")
        out.flush()
    return 0
