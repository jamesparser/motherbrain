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


class BearerAuth(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        key = os.environ.get("MB_API_KEY")
        if key and request.url.path != "/api/health" and request.method != "OPTIONS":
            got = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
            if not (_eq(got, key) or _eq(got, os.environ.get("MB_ADMIN_KEY", ""))):
                return JSONResponse({"error": "unauthorized"}, status_code=401)
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
            Mount("/", app=mcp_app),
        ],
        middleware=[Middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"],
                               allow_headers=["*"]), Middleware(BearerAuth)],
        lifespan=lambda app: mcp.session_manager.run(),
    )
