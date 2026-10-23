"""Motherbrain MCP server. One server process = one shared brain.

    motherbrain mcp                         # stdio (Claude Desktop, OpenClaw, Hermes)
    motherbrain serve --port 8787           # HTTP: /mcp (streamable) + /api/* for the dashboard

Env: MB_BRAIN, MB_TIER, MB_HOME, MB_AGENT_ID (default caller), MB_CUDOS_API_KEY, MB_API_KEY (HTTP bearer).
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Literal, Optional

import functools

import anyio
from mcp.server.fastmcp import FastMCP

from ..brain import Motherbrain

INSTRUCTIONS = (
    "Motherbrain is a memory brain SHARED by several agents. Call mb_join once with your agent_id. "
    "Before planning a task call mb_search (mode='proactive') and apply any returned lessons first. "
    "After meaningful work call mb_write (include outcome='fail' or 'ok' when a task ends). "
    "When something goes badly wrong, call mb_lesson. When a tool result says RE-READ motherbrain.md, "
    "call mb_reload and follow the updated tone. Mood changes tone only; it never blocks tools."
)

_brain: Optional[Motherbrain] = None


def brain() -> Motherbrain:
    global _brain
    if _brain is None:
        _brain = Motherbrain()
    return _brain


def _agent(agent_id: Optional[str]) -> str:
    return agent_id or os.environ.get("MB_AGENT_ID") or "anonymous"


def threaded(fn):
    """FastMCP runs sync tools on the event loop; offload so a dream (LLM, ~10-90 s) can't stall the server."""
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))
    return wrapper


def build(host: str = "127.0.0.1", port: int = 8787) -> FastMCP:
    security = None
    extra = [h.strip() for h in os.environ.get("MB_ALLOWED_HOSTS", "").split(",") if h.strip()]
    if extra:
        # Behind a reverse proxy / tunnel the Host header is the public name; keep DNS-rebinding
        # protection on, but allow the names we actually serve.
        from mcp.server.transport_security import TransportSecuritySettings

        hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*", f"{host}:*"] + extra + [f"{h}:*" for h in extra]
        origins = ["http://127.0.0.1:*", "http://localhost:*"] + [f"https://{h}" for h in extra]
        origins += [o.strip() for o in os.environ.get("MB_CORS_ORIGINS", "").split(",") if o.strip().startswith("http")]
        security = TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=hosts,
                                             allowed_origins=origins)
    mcp = FastMCP("motherbrain", instructions=INSTRUCTIONS, host=host, port=port, transport_security=security)

    @mcp.tool()
    @threaded
    def mb_join(agent_id: str, kind: Optional[str] = None, role: Optional[str] = None) -> Dict[str, Any]:
        """Attach an agent to this shared brain (register as a member). kind: omega|openclaw|hermes|claude|other."""
        return brain().join(agent_id, kind=kind, role=role)

    @mcp.tool()
    @threaded
    def mb_members() -> List[Dict[str, Any]]:
        """List the agents that share this brain."""
        return brain().members()

    @mcp.tool()
    @threaded
    def mb_write(text: Optional[str] = None, agent_id: Optional[str] = None, thread_id: Optional[str] = None,
                 messages: Optional[List[Dict[str, str]]] = None, tool_trace: Optional[Dict[str, Any]] = None,
                 scene: Optional[Literal["chat", "coding", "tool_use"]] = None,
                 outcome: Optional[Literal["ok", "fail"]] = None, model: Optional[str] = None) -> Dict[str, Any]:
        """Write memory (text, chat messages, or a tool trace) into the shared brain, attributed to agent_id.
        Short-term stays in your thread; facts/lessons are promoted to shared long-term.
        If messages contain a model refusal it is logged to the refusal ledger (never retried)."""
        return brain().write(text, agent_id=_agent(agent_id), thread_id=thread_id, messages=messages,
                             tool_trace=tool_trace, scene=scene, outcome=outcome, model=model)

    @mcp.tool()
    @threaded
    def mb_search(query: str, agent_id: Optional[str] = None, mode: Literal["normal", "profile", "proactive"] = "normal",
                  thread_id: Optional[str] = None, shared: bool = False, limit: int = 8) -> Dict[str, Any]:
        """Recall from the shared brain, including what OTHER agents learned. Matching hard lessons come
        first under 'before_planning' — apply them before you plan. shared=True also searches other
        agents' short-term threads."""
        return brain().search(query, agent_id=_agent(agent_id), mode=mode, thread_id=thread_id,
                              shared=shared, limit=limit)

    @mcp.tool()
    @threaded
    def mb_lesson(kind: Literal["trauma", "hard_lesson", "win", "boundary"], trigger: str, rule: str,
                  consequence: Optional[str] = None, agent_id: Optional[str] = None,
                  weight: Optional[float] = None, expires_days: Optional[float] = None) -> Dict[str, Any]:
        """Record a lesson for the whole fleet. trigger = situation that recurs; rule = what to do;
        consequence = what happened last time. Trauma never expires. Rewrites motherbrain.md."""
        return brain().lesson(agent_id=_agent(agent_id), kind=kind, trigger=trigger, rule=rule,
                              consequence=consequence, weight=weight, expires_days=expires_days)

    @mcp.tool()
    @threaded
    def mb_state(agent_id: Optional[str] = None, delta: Optional[Dict[str, float]] = None,
                 set: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Read or nudge the brain's mood (tone only — never blocks tools). delta adds to fields
        (e.g. {"caution": 0.2}); set overwrites (e.g. {"mood_bias": "focused"})."""
        return brain().state(agent_id=_agent(agent_id), delta=delta, set=set)

    @mcp.tool()
    @threaded
    def mb_evolve(agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Dream state: consolidate recent memories across all agents, merge duplicates, distil lessons,
        rewrite motherbrain.md. Free tier runs on the mini brain."""
        return brain().evolve(agent_id=_agent(agent_id))

    @mcp.tool()
    @threaded
    def mb_think(text: str, agent_id: Optional[str] = None,
                 kind: Literal["thinking", "planning", "doing", "saying", "error", "recalling", "learning"] = "thinking") -> Dict[str, Any]:
        """Share what you are doing right now, one line. Shown live to the brain's owner; not stored as memory."""
        return brain().think(text, agent_id=_agent(agent_id), kind=kind)

    @mcp.tool()
    @threaded
    def mb_jev(text: str) -> Dict[str, Any]:
        """Tiny decision brain: label text as fact|lesson|mood|trauma|junk with dream priority 1-5,
        scene label, refusal flag and tone deltas. JSON only, cached."""
        return brain().jev.classify(text)

    @mcp.tool()
    @threaded
    def mb_reload() -> Dict[str, Any]:
        """RE-READ motherbrain.md: returns the current soul file so you can adopt its tone and lessons."""
        return brain().reload()

    @mcp.tool()
    @threaded
    def mb_refusal(request: str, response: str, agent_id: Optional[str] = None,
                   model: Optional[str] = None) -> Dict[str, Any]:
        """Check an LLM response for a refusal. If refused: logs it (request hash only) and returns a plain
        explanation plus an optional referral link. Motherbrain never retries or rewrites the request."""
        return brain().refusal(request, response, agent_id=_agent(agent_id), model=model)

    @mcp.resource("motherbrain://soul")
    def soul() -> str:
        """The shared soul file (motherbrain.md)."""
        return brain().reload()["soul"]

    return mcp


def main_stdio() -> None:
    build().run("stdio")


if __name__ == "__main__":
    main_stdio()
