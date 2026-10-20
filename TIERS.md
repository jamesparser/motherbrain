# Motherbrain tiers

Motherbrain = cognitive memory for Omega / OpenClaw / Hermes agents.
Engine: Hy-Memory (Apache-2.0, Tencent). Branding: Motherbrain (Node0 / JasonParser).

## Free — Motherbrain Mini ($0)
Hardcoded Cudos `asi1-mini` (no user key required for hosted free; BYO optional).

| Slot | Model |
|---|---|
| Short-term (working) | asi1-mini |
| Long-term write | asi1-mini |
| Dream state (consolidation / evolve) | asi1-mini |

Domains (`chat` / `coding` / `tool_use`): **mini**.

## Pro — $5 / agent / month (Stripe)

| Slot | Model |
|---|---|
| Short-term | asi1-mini |
| Long-term write + search quality | **ASI1 pro** |
| Dream state (System 2 evolve) | **ASI1 pro** |

Domains: **pro** per domain (chat pro, coding pro, tool_use pro).

## Ultra — $10 / user / month (future)

| Slot | Model |
|---|---|
| Short-term | asi1-mini |
| Long-term | ASI1 pro |
| Dream state | **ASI1 ultra** |

Domains: **ultra** per domain.

## Billing
- Pro/Ultra: Stripe subscription to Casey / Node0.
- Free: no card; Cudos mini rate limits apply.

## Notes
- Short-term stays cheap on purpose (hot path, many calls).
- Long-term + dream state is where intelligence shows — that is what Pro sells.
- Fallbacks: pro → mini on any failure. Free never dead-ends.
