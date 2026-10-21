# Motherbrain wrappers (thin)

Every wrapper points at the **same** brain. The brain lives on the Omega VPS
(`motherbrain.service`, tailnet only): `http://<vps-tailnet-ip>:8790/mcp`.
Bearer token = `MB_API_KEY` in `/opt/motherbrain/.env` on the VPS.

## Any MCP client over HTTP (Omega, OpenClaw, Hermes, Claude Code)

```json
{
  "mcpServers": {
    "motherbrain": {
      "type": "http",
      "url": "http://<vps-tailnet-ip>:8790/mcp",
      "headers": { "Authorization": "Bearer <MB_API_KEY>" }
    }
  }
}
```

Claude Code: `claude mcp add --transport http motherbrain http://<vps-tailnet-ip>:8790/mcp --header "Authorization: Bearer <MB_API_KEY>"`

## Agents running ON the VPS (stdio, same DB)

```json
{
  "mcpServers": {
    "motherbrain": {
      "command": "/opt/motherbrain/.venv/bin/motherbrain",
      "args": ["mcp"],
      "env": { "MB_HOME": "/var/lib/motherbrain", "MB_BRAIN": "omega-fleet", "MB_AGENT_ID": "omega-1",
               "MB_CUDOS_API_KEY": "<same as .env>" }
    }
  }
}
```
Note: stdio MCP clients do not inherit your shell env — pass `env` explicitly.

## Agent loop (all wrappers)
1. `mb_join(agent_id, kind)` once.
2. Before planning: `mb_search(query=<task>, mode="proactive")` → apply `before_planning` lessons first.
3. After work: `mb_write(text|messages|tool_trace, outcome="ok"|"fail")`.
4. On a costly mistake: `mb_lesson(kind="hard_lesson"|"trauma", trigger, rule, consequence)`.
5. When a result says `RE-READ motherbrain.md`: `mb_reload` and adopt the tone.
6. Nightly (cron) or on demand: `mb_evolve` (dream).

See `hermes/SKILL.md` and `omega/AGENTS.md` for drop-in prompt blocks.
