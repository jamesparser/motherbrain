# Agent state vector (Motherbrain)

More than a mood ring: these values **steer planning** and are stored as memory.

| Field | Range | Effect |
|---|---|---|
| confidence | 0-1 | low → ask / re-verify; high → act |
| caution | 0-1 | high → require union verify, smaller steps |
| urgency | 0-1 | high → shorter loops, less exploration |
| fatigue | 0-1 | high → hand off / shorten session |
| curiosity | 0-1 | high → explore alternatives |
| helpfulness | 0-1 | bias toward user utility vs self-preservation of context |
| stubbornness | 0-1 | resist changing a verdict without new evidence |
| trust_peer | map | per-peer reliability (a2a identities) |
| trauma_level | 0-1 | from hard lessons; multiplies caution |
| mood_bias | tag | e.g. focused / anxious / playful — style only |

## Trauma / hard lessons (first-class)
- `trauma` — high weight, never auto-forget
- `hard_lesson` — rule inferred from failure
- `win` / `boundary` — positive / stop-doing-that

On similar trigger → inject into prompt **before** planning.
