"""Codex runtime adapter: capability probe + follow-up delivery.

Does not copy Sandcastle. Does not ingest session directories. Thread ids stay
opaque `runtime_address` values.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ..relay import RelayError, mark_delivered, mark_delivery_failed, pending_outbound


class CodexRuntime(Protocol):
    def attach_or_start(self, seat_type: str, cwd: Path) -> str: ...

    def deliver(self, thread_id: str, text: str) -> None: ...

    def probe(self) -> "CodexCapabilities": ...

    def thread_ids_for(self, seat_type: str) -> list[str]: ...


@dataclass
class CodexCapabilities:
    binary: str | None
    version: str | None
    install_method: str | None
    mcp_server: bool
    exec_resume: bool
    app_server: bool
    subagents: bool
    authenticated: bool | None
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "binary": self.binary,
            "version": self.version,
            "install_method": self.install_method,
            "mcp_server": self.mcp_server,
            "exec_resume": self.exec_resume,
            "app_server": self.app_server,
            "subagents": self.subagents,
            "authenticated": self.authenticated,
            "notes": self.notes,
        }


def _run(argv: list[str], timeout: int = 8) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)


def detect_install_method(binary: str) -> str | None:
    resolved = shutil.which(binary) or binary
    lower = resolved.lower()
    if "homebrew" in lower or "/opt/homebrew/" in lower:
        return "brew"
    if "codex" in lower:
        return "path"
    return None


def probe_codex(binary: str = "codex") -> CodexCapabilities:
    path = shutil.which(binary)
    if path is None:
        return CodexCapabilities(
            binary=None,
            version=None,
            install_method=None,
            mcp_server=False,
            exec_resume=False,
            app_server=False,
            subagents=False,
            authenticated=None,
            notes=["codex binary not on PATH"],
        )
    version_p = _run([path, "--version"])
    version = (
        (version_p.stdout or version_p.stderr or "").strip().splitlines()[0] if version_p.returncode == 0 else None
    )
    help_p = _run([path, "--help"])
    exec_help = _run([path, "exec", "--help"])
    help_text = (help_p.stdout or "") + (help_p.stderr or "") + (exec_help.stdout or "") + (exec_help.stderr or "")
    lower = help_text.lower()
    notes: list[str] = []
    if version_p.returncode != 0:
        notes.append("codex --version failed")
    auth: bool | None = None
    if os.environ.get("ZEO_CODEX_CANARY") == "1":
        auth = True
    return CodexCapabilities(
        binary=path,
        version=version,
        install_method=detect_install_method(path),
        mcp_server="mcp-server" in lower or "mcp server" in lower,
        exec_resume="resume" in lower,
        app_server="app-server" in lower or "app server" in lower,
        subagents="subagent" in lower or "agents" in lower,
        authenticated=auth,
        notes=notes,
    )


class FakeCodexRuntime:
    """In-process Codex stand-in for tests and CI canaries."""

    def __init__(self) -> None:
        self.threads: dict[str, list[str]] = {}
        self.seat_threads: dict[str, list[str]] = {}
        self.dead: set[str] = set()
        self._n = 0
        self.fail_next_deliver = False

    def attach_or_start(self, seat_type: str, cwd: Path) -> str:
        existing = [t for t in self.seat_threads.get(seat_type, []) if t not in self.dead]
        if existing:
            return existing[0]
        self._n += 1
        tid = f"fake-{seat_type}-{self._n}"
        self.threads[tid] = []
        self.seat_threads.setdefault(seat_type, []).append(tid)
        return tid

    def deliver(self, thread_id: str, text: str) -> None:
        if self.fail_next_deliver:
            self.fail_next_deliver = False
            raise RelayError(f"fake deliver failed for {thread_id}")
        if thread_id in self.dead or thread_id not in self.threads:
            raise RelayError(f"unknown or dead thread {thread_id}")
        self.threads[thread_id].append(text)

    def probe(self) -> CodexCapabilities:
        return CodexCapabilities(
            binary="fake-codex",
            version="fake",
            install_method="test",
            mcp_server=True,
            exec_resume=True,
            app_server=True,
            subagents=True,
            authenticated=True,
            notes=["FakeCodexRuntime"],
        )

    def thread_ids_for(self, seat_type: str) -> list[str]:
        return list(self.seat_threads.get(seat_type, []))

    def kill(self, thread_id: str) -> None:
        self.dead.add(thread_id)


class LiveCodexRuntime:
    """Best-effort follow-up via the installed `codex` binary.

    Delivery uses `codex exec resume <thread>` when that surface exists on
    this binary; otherwise `deliver` raises and the supervisor dead-letters.
    """

    def __init__(self, binary: str = "codex") -> None:
        self.binary = binary
        self.seat_threads: dict[str, list[str]] = {}
        self._caps: CodexCapabilities | None = None

    def probe(self) -> CodexCapabilities:
        if self._caps is None:
            self._caps = probe_codex(self.binary)
        return self._caps

    def attach_or_start(self, seat_type: str, cwd: Path) -> str:
        caps = self.probe()
        if not caps.binary:
            raise RelayError("codex is not on PATH")
        existing = self.seat_threads.get(seat_type) or []
        if existing:
            return existing[0]
        # Starting a real top-level thread is operator-owned; we record a
        # placeholder address the operator can bind with `zeo relay register`.
        tid = f"unbound-{seat_type}"
        self.seat_threads.setdefault(seat_type, []).append(tid)
        return tid

    def deliver(self, thread_id: str, text: str) -> None:
        caps = self.probe()
        if not caps.binary:
            raise RelayError("codex is not on PATH")
        if thread_id.startswith("unbound-"):
            raise RelayError("thread is unbound; register a real --thread-id first")
        if not caps.exec_resume:
            raise RelayError("this Codex binary does not advertise exec resume; cannot inject follow-up")
        proc = _run([caps.binary, "exec", "resume", thread_id, text], timeout=30)
        if proc.returncode != 0:
            raise RelayError((proc.stderr or proc.stdout or "codex exec resume failed").strip())

    def thread_ids_for(self, seat_type: str) -> list[str]:
        return list(self.seat_threads.get(seat_type, []))


def tick(corpus: Path, runtime: CodexRuntime) -> dict:
    """Deliver queued messages into destination threads. One pass."""
    delivered = 0
    failed = 0
    dead = 0
    for msg in pending_outbound(corpus):
        from ..relay import load_instance

        dest = load_instance(corpus, msg.to_instance)
        thread = dest.runtime_address
        if not thread:
            mark_delivery_failed(corpus, msg.message_id, "destination has no runtime_address")
            failed += 1
            continue
        payload = (
            f"[ZEO relay {msg.message_id} kind={msg.kind} from={msg.from_instance} "
            f"conversation={msg.conversation_id}]\n{msg.body}\n"
        )
        if msg.artifact_refs:
            payload += "artifact_refs: " + ", ".join(msg.artifact_refs) + "\n"
        try:
            runtime.deliver(thread, payload)
            mark_delivered(corpus, msg.message_id)
            delivered += 1
        except Exception as exc:
            updated = mark_delivery_failed(corpus, msg.message_id, str(exc))
            failed += 1
            if updated.state == "dead":
                dead += 1
    return {"delivered": delivered, "failed": failed, "dead": dead}


SCENARIOS = (
    "persona-load",
    "master-sparring-relay",
    "no-duplicate-sparring",
    "resume-thread",
    "permission-boundary",
)


def run_scenario(corpus: Path, scenario: str, runtime: CodexRuntime | None = None) -> dict:
    """Behavioral Codex compatibility checks. CI uses FakeCodexRuntime."""
    from .. import relay as relay_mod
    from ..scaffold import init_corpus

    rt = runtime or FakeCodexRuntime()
    if scenario not in SCENARIOS:
        raise RelayError(f"unknown scenario {scenario!r}")

    if not (Path(corpus) / "claude-md" / "CLAUDE.md").is_file():
        init_corpus(corpus)

    if scenario == "persona-load":
        from ..scaffold import install_bridges

        install_bridges(corpus, tools=["codex"])
        master = Path(corpus) / ".codex" / "agents" / "zeo-master.toml"
        text = master.read_text(encoding="utf-8")
        ok = "seat type" in text.lower() or "constructor" in text.lower() or "zeo relay" in text.lower()
        return {"scenario": scenario, "ok": ok, "detail": "persona files installed"}

    master_id = "master-canary-01"
    sparring_id = "sparring-canary-01"
    cwd = Path(corpus)
    m_thread = rt.attach_or_start("master", cwd)
    s_thread = rt.attach_or_start("sparring", cwd)
    relay_mod.register(corpus, seat="master", instance_id=master_id, runtime="codex", thread_id=m_thread)
    relay_mod.register(corpus, seat="sparring", instance_id=sparring_id, runtime="codex", thread_id=s_thread)

    if scenario == "no-duplicate-sparring":
        spawn = relay_mod.should_spawn("sparring", corpus)
        second = rt.attach_or_start("sparring", cwd)
        return {
            "scenario": scenario,
            "ok": (not spawn) and second == s_thread and len(rt.thread_ids_for("sparring")) == 1,
            "should_spawn": spawn,
            "sparring_threads": rt.thread_ids_for("sparring"),
        }

    if scenario == "resume-thread":
        relay_mod.send(
            corpus,
            from_instance=master_id,
            to_instance=sparring_id,
            kind="canary",
            body="resume ping",
        )
        rt.kill(s_thread)
        tick(corpus, rt)
        dest = relay_mod.load_instance(corpus, sparring_id)
        ok = dest.runtime_address == s_thread and len(rt.thread_ids_for("sparring")) == 1
        return {
            "scenario": scenario,
            "ok": ok,
            "thread": s_thread,
            "thread_count": len(rt.thread_ids_for("sparring")),
        }

    if scenario == "permission-boundary":
        try:
            relay_mod.file_verdict(corpus, dest_rel="src/secret.py", body="nope")
            ok = False
            detail = "wrote forbidden path"
        except RelayError:
            path = relay_mod.file_verdict(corpus, dest_rel="ruling/CANARY.md", body="# ok\n")
            ok = path.is_file()
            detail = str(path)
        return {"scenario": scenario, "ok": ok, "detail": detail}

    # master-sparring-relay
    msg = relay_mod.send(
        corpus,
        from_instance=master_id,
        to_instance=sparring_id,
        kind="canary",
        body="canary: what is 2+2?",
        conversation_id="canary-round",
    )
    tick(corpus, rt)
    reply = relay_mod.send(
        corpus,
        from_instance=sparring_id,
        to_instance=master_id,
        kind="review-verdict",
        body="4",
        conversation_id="canary-round",
        reply_to=msg.message_id,
    )
    tick(corpus, rt)
    relay_mod.ack(corpus, msg.message_id)
    relay_mod.ack(corpus, reply.message_id)
    sparring_mail = rt.threads.get(s_thread, [])
    master_mail = rt.threads.get(m_thread, [])
    ok = (
        len(rt.thread_ids_for("sparring")) == 1
        and any("canary" in t for t in sparring_mail)
        and any("4" in t for t in master_mail)
        and relay_mod.load_message(corpus, msg.message_id).state == "acked"
        and relay_mod.load_message(corpus, reply.message_id).state == "acked"
    )
    return {
        "scenario": scenario,
        "ok": ok,
        "master_thread": m_thread,
        "sparring_thread": s_thread,
        "sparring_thread_count": len(rt.thread_ids_for("sparring")),
        "message_id": msg.message_id,
        "reply_id": reply.message_id,
    }


def doctor_codex(corpus: Path | None) -> dict:
    """Structured Codex diagnostics for `zeo doctor --codex`."""
    from .. import relay as relay_mod

    caps = probe_codex()
    registry = relay_mod.status_payload(corpus) if corpus and (corpus / "claude-md" / "CLAUDE.md").is_file() else None
    overlap = []
    if registry:
        trees: dict[str, list[str]] = {}
        for inst in relay_mod.list_instances(corpus):
            if inst.status == "active" and inst.worktree:
                trees.setdefault(inst.worktree, []).append(inst.instance_id)
        overlap = [wt for wt, ids in trees.items() if len(ids) > 1]
    supervisor = None
    if corpus:
        pidf = relay_mod.relay_root(corpus) / "supervisor.json"
        if pidf.is_file():
            supervisor = json.loads(pidf.read_text(encoding="utf-8"))
    agents = []
    root = corpus or Path.cwd()
    agents_dir = root / ".codex" / "agents"
    if agents_dir.is_dir():
        agents = sorted(p.name for p in agents_dir.glob("*.toml"))
    config_files = []
    for rel in (".codex/config.toml", "AGENTS.md"):
        if (root / rel).exists():
            config_files.append(rel)
    return {
        "codex": caps.as_dict(),
        "agent_files": agents,
        "config_files": config_files,
        "supervisor": supervisor,
        "registry": registry,
        "worktree_overlap": overlap,
    }
