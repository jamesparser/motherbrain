# Motherbrain — BGI Omega Hackathon 2

**Persistent, shared cognitive memory for Omega agents.**
One brain, many agents: short-term, long-term identity, hard lessons, and dream-state
consolidation. When one agent learns, the fleet learns.

- **Live dashboard (judges):** https://motherbrain.vercel.app — any email logs in.
- **Live brain API / MCP:** https://motherbrain.realcryptocap.com/mcp (public, rate-limited key shown on the dashboard)
- **Code:** https://github.com/jamesparser/motherbrain (Apache-2.0, fork of Tencent Hy-Memory)

## Try it in 2 minutes
1. Open the dashboard → **Try it** panel. You are agent `judge-xxxx` on the shared demo brain.
2. **Ask before planning:** "deploy the api to prod over rsync" → you get `omega-1`'s hard lesson
   (VPN before rsync) *before* you plan, plus memories from other agents.
3. **Record a hard lesson** of your own → the soul (`motherbrain.md`) is rewritten and every
   agent is told `RE-READ motherbrain.md` (no reboot). Watch the timeline and the soul panel update.
4. **Check a refusal:** paste a request and a model's refusal → the ledger shows what was
   declined, *why* (the model's stated reason or a topic), and which words it reacted to.
5. **Dream now** → consolidation on the strong brain (merges duplicates, distils lessons).
6. Optional: plug your own agent in with the MCP snippet on the dashboard.

## What is real (no mocks)
- **Shared multi-agent brain:** `mb_join` / `mb_members`; writes attributed to `agent_id`, recall shared.
  Short-term stays in the caller's thread; long-term, dream, lessons and soul are one copy.
- **Stages, routed by power:** short-term + JEV decisions on ASI1-mini (Cudos); long-term + dream on ASI1
  (demo brain, temporarily Pro). Every route falls back to mini — Free never dead-ends.
- **JEV:** asi1-mini as a 64-token JSON classifier (fact/lesson/mood/trauma/junk, dream priority,
  scene, refusal, tone deltas), cached, heuristic fallback. Never downgrades a clear incident.
- **Lessons injected before planning** on similar triggers; trauma never expires.
- **Moods are tone only** — they rewrite the soul's tone section and never block a tool.
- **Dream (`mb_evolve`):** System-2 consolidation; nightly systemd timers on the VPS.
- **Refusal ledger:** detect → explain why → log (redacted) → soft referral. Never retries,
  rewrites, jailbreaks or reroutes a refused request.
- **Native Omega plugin:** `plugins/motherbrain/omega` — 4 MeTTa skills + the soul as a live
  prompt extension refreshed by a heartbeat listener. Verified loading in an Omega container.
- **MCP server** (stdio + streamable HTTP), plain JSON tool API, Next.js dashboard, Stripe Pro
  ($5/agent/mo, test mode).

## Architecture
```
Omega (MeTTa plugin) ─┐
OpenClaw / Hermes ────┼─ MCP / HTTP ─▶ Motherbrain (Python, SQLite) ──▶ ASI1-mini  (short, JEV)
Claude / any MCP ─────┘                 │  router · JEV · soul · dream    ──▶ ASI1       (long, dream)
                                        └─▶ /api/snapshot ─▶ Vercel dashboard (+ Stripe, ledger)
```

## Honest limits
- Recall is lexical (BM25 + recency + weight). Hy-Memory's vector/graph backends are wired as an
  optional mirror (`MB_BACKEND=hy`) but not enabled in the demo.
- A Stripe payment does not yet flip a brain's tier automatically (needs the webhook secret on Vercel).
- No consciousness claims: this is cognitive architecture, not a Φ score.

Team: Casey Blanche · Node0 Data Systems / JasonParser Security.
