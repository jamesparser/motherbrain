"""HTTP server: MCP over streamable HTTP at /mcp + read API for the dashboard at /api/*.

Auth: `Authorization: Bearer $MB_API_KEY` on everything except /api/health (when MB_API_KEY is set).
Tier changes (/api/tier) require MB_ADMIN_KEY — called by the dashboard's Stripe webhook.
"""
from __future__ import annotations

import hmac
import os

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .mcp.server import brain, build


def _eq(a: str, b: str) -> bool:
    return bool(a) and bool(b) and hmac.compare_digest(a.encode(), b.encode())


class RateLimit:
    """Sliding-window limiter (in-process). Protects the paid brain behind a published judge key."""

    def __init__(self):
        import collections
        import threading

        self.hits = collections.defaultdict(collections.deque)
        self.lock = threading.Lock()

    def allow(self, key: str, limit: int, window: float) -> bool:
        import time

        now = time.time()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True


LIMITS = RateLimit()
PUBLIC_MAX_BODY = 6000


class BearerAuth(BaseHTTPMiddleware):
    """MB_API_KEY / MB_ADMIN_KEY = full access. MB_PUBLIC_KEY = judge/demo key: rate limited,
    no tier changes, dreams capped globally (they run on the strongest model)."""

    async def dispatch(self, request: Request, call_next):
        key = os.environ.get("MB_API_KEY")
        path = request.url.path
        if key and path != "/api/health" and request.method != "OPTIONS":
            got = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
            if _eq(got, key) or _eq(got, os.environ.get("MB_ADMIN_KEY", "")):
                return await call_next(request)
            if not _eq(got, os.environ.get("MB_PUBLIC_KEY", "")):
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            if path.startswith("/api/tier"):
                return JSONResponse({"error": "not allowed with the public key"}, status_code=403)
            if int(request.headers.get("content-length") or 0) > PUBLIC_MAX_BODY:
                return JSONResponse({"error": "request too large for the public key"}, status_code=413)
            ip = (request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for", "").split(",")[0]
                  or (request.client.host if request.client else "?")).strip()
            per_min = int(os.environ.get("MB_PUBLIC_RPM", "30"))
            if not (LIMITS.allow("ip:" + ip, per_min, 60) and LIMITS.allow("all", per_min * 10, 60)):
                return JSONResponse({"error": "rate limited, try again in a minute"}, status_code=429)
            if path.endswith("/evolve") and not LIMITS.allow("evolve", 1, float(os.environ.get("MB_PUBLIC_DREAM_EVERY", "600"))):
                return JSONResponse({"error": "the brain dreamed recently; one dream per 10 minutes on the demo"},
                                    status_code=429)
        return await call_next(request)


async def health(_: Request):
    b = brain()
    return JSONResponse({"ok": True, "brain": b.brain_id, "tier": b.tier})


async def snapshot(_: Request):
    return JSONResponse(brain().snapshot())


async def refusals(_: Request):
    return JSONResponse(brain().store.refusals(brain().brain_id))


async def set_tier(request: Request):
    got = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not _eq(got, os.environ.get("MB_ADMIN_KEY", "")):
        return JSONResponse({"error": "admin key required"}, status_code=403)
    body = await request.json()
    tier = body.get("tier")
    from .router import Router

    b = brain()
    b.router = Router(tier)
    b.jev.router = b.router
    b.brain = b.store.ensure_brain(b.brain_id, b.router.tier)
    b.store.event(b.brain_id, "tier", None, tier=tier, source=body.get("source"))
    return JSONResponse({"ok": True, "tier": b.tier})


TOOLS = {
    "join": lambda b, a: b.join(a["agent_id"], kind=a.get("kind"), role=a.get("role")),
    "members": lambda b, a: b.members(),
    "write": lambda b, a: b.write(a.get("text"), agent_id=a.get("agent_id") or "anonymous", thread_id=a.get("thread_id"),
                                  messages=a.get("messages"), tool_trace=a.get("tool_trace"), scene=a.get("scene"),
                                  outcome=a.get("outcome"), model=a.get("model")),
    "search": lambda b, a: b.search(a["query"], agent_id=a.get("agent_id") or "anonymous", mode=a.get("mode", "normal"),
                                    thread_id=a.get("thread_id"), shared=bool(a.get("shared")), limit=int(a.get("limit", 8))),
    "lesson": lambda b, a: b.lesson(agent_id=a.get("agent_id") or "anonymous", kind=a["kind"], trigger=a["trigger"],
                                    rule=a["rule"], consequence=a.get("consequence")),
    "state": lambda b, a: b.state(agent_id=a.get("agent_id"), delta=a.get("delta"), set=a.get("set")),
    "evolve": lambda b, a: b.evolve(agent_id=a.get("agent_id")),
    "reload": lambda b, a: {**b.reload(), "hash": b.soul.hash or b._rewrite_soul("reload")["hash"]},
    "refusal": lambda b, a: b.refusal(a["request"], a["response"], agent_id=a.get("agent_id"), model=a.get("model")),
}


async def tool(request: Request):
    """Plain JSON twin of the MCP tools, for harnesses without an MCP client (Omega plugin, cron)."""
    name = request.path_params["name"]
    fn = TOOLS.get(name)
    if fn is None:
        return JSONResponse({"error": f"unknown tool {name}", "tools": sorted(TOOLS)}, status_code=404)
    try:
        args = await request.json()
    except Exception:
        args = {}
    try:
        return JSONResponse(fn(brain(), args or {}))
    except (KeyError, ValueError, TypeError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)


def create_app(host: str = "0.0.0.0", port: int = 8787) -> Starlette:
    mcp = build(host, port)
    mcp_app = mcp.streamable_http_app()  # serves /mcp
    origins = [o.strip() for o in os.environ.get("MB_CORS_ORIGINS", "*").split(",") if o.strip()]
    return Starlette(
        routes=[
            Route("/api/health", health),
            Route("/api/snapshot", snapshot),
            Route("/api/refusals", refusals),
            Route("/api/tier", set_tier, methods=["POST"]),
            Route("/api/tools/{name}", tool, methods=["POST"]),
            Mount("/", app=mcp_app),
        ],
        middleware=[Middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"],
                               allow_headers=["*"]), Middleware(BearerAuth)],
        lifespan=lambda app: mcp.session_manager.run(),
    )
