"""Smoke-test a running Motherbrain over MCP streamable HTTP.
   ssh vps 'cd /opt/motherbrain && set -a && . ./.env && .venv/bin/python -' < deploy/vps/smoke.py
"""
import asyncio, json, os, subprocess

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

host = os.environ.get("MB_SMOKE_HOST") or subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True).stdout.split()[0]
URL = f"http://{host}:{os.environ.get('MB_PORT', '8790')}/mcp"
print("cudos key set:", bool(os.environ.get("MB_CUDOS_API_KEY")))


async def call(s, name, args):
    r = await s.call_tool(name, args)
    return json.loads(r.content[0].text) if r.content else None


async def main():
    async with streamablehttp_client(URL, headers={"Authorization": f"Bearer {os.environ['MB_API_KEY']}"}) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            print("tools:", sorted(t.name for t in (await s.list_tools()).tools))
            print("join:", (await call(s, "mb_join", {"agent_id": "omega-vps", "kind": "omega", "role": "fleet lead"}))["members"])
            print("jev:", await call(s, "mb_jev", {"text": "Prod deploy failed last night because the VPN was down; rsync timed out."}))
            w1 = await call(s, "mb_write", {"text": "The Omega gateway runs on the VPS behind cloudflared; litellm on :4000.", "agent_id": "omega-vps"})
            print("write:", {k: w1[k] for k in ("label", "priority", "scene", "jev")})
            print("search:", [m["text"][:60] for m in (await call(s, "mb_search", {"query": "where does litellm run?", "agent_id": "hermes-laptop"}))["memories"]][:2])


asyncio.run(main())
