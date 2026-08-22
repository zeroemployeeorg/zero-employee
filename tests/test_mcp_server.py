"""MCP stdio tools wrap the same relay library."""

from __future__ import annotations

import io
import json

from zero_employee.mcp_server import TOOLS, serve
from zero_employee.scaffold import init_corpus
from zero_employee import relay


def test_tools_list_includes_relay():
    names = set(TOOLS)
    for n in (
        "zeo_orient",
        "zeo_relay_resolve",
        "zeo_relay_send",
        "zeo_relay_receive",
        "zeo_relay_ack",
        "zeo_relay_status",
        "zeo_doctor",
    ):
        assert n in names


def test_stdio_initialize_and_relay_status(tmp_path):
    root = tmp_path / "org"
    init_corpus(root)
    relay.register(root, seat="master", instance_id="m1", runtime="codex", thread_id="t")
    reqs = [
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t"}},
            }
        ),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "zeo_relay_status", "arguments": {"root": str(root)}},
            }
        ),
    ]
    inn = io.StringIO("\n".join(reqs) + "\n")
    out = io.StringIO()
    assert serve(inn, out) == 0
    lines = [json.loads(line) for line in out.getvalue().splitlines() if line.strip()]
    assert lines[0]["result"]["serverInfo"]["name"] == "zeo"
    tool_names = {t["name"] for t in lines[1]["result"]["tools"]}
    assert "zeo_relay_send" in tool_names
    payload = json.loads(lines[2]["result"]["content"][0]["text"])
    assert payload["instances"]
