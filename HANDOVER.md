# MOTHERBRAIN — build handover (for Claude / next agent)

Date: 2026-09-25 · Owner: Casey Blanche / Node0 Data Systems / JasonParser Security
Context: ASI1 / SingularityNET **BGI Omega hackathon 2** (after HyperSprint #2)

This is the full product spec. Do **not** invent jailbreak / refusal-bypass features.
Do **not** resell or BYOK-resell ASI1 seats without asking SNET first.

---

## 1. What we are building

**Motherbrain** — cognitive memory for agents (Omega / OpenClaw / Hermes).

Fork of **Tencent Hy-Memory** (Apache-2.0). Brand: red “Mother Brain” art
(`assets/motherbrain.png` from `Mother-brain-art.png`).

Not a new LLM. A **memory runtime** + **skills/MCP** + **dashboard** + **Stripe tiers**.

### Positioning (for Ben / SNET / ASI crowd)
> Persistent mind for Omega agents: short-term memory, long-term identity, hard
> lessons, dream-state consolidation. It thinks more like a human than a chat log.

Do **not** claim magic consciousness scores (no “13.32x Φ”). Sell **cognitive
architecture** backed by Hy-Memory’s dual-process design + papers.

---

## 2. Memory model (human brain — no “domains” as product)

Stages only:

| Stage | Role | Model power |
|---|---|---|
| **Short-term** | now / last N turns | cheapest (`asi1-mini`) |
| **Long-term** | facts, lessons, identity | medium |
| **Dream** | consolidate / evolve (System 2) | **strongest** |

`chat` / `coding` / `tool_use` are **labels for what is stored**, not separate brains.
(Coding keeps Hy-Memory’s fact + experience + **diff chain**.)

**Why dream is strongest:** schema induction, conflict reconciliation, “what did we learn”.
Long-term write is second (garbage in = forever garbage). Short-term is high volume.

### Tier → model map

| | Short | Long | Dream | Billing |
|---|---|---|---|---|
| **Free $0** | asi1-mini | asi1-mini | asi1-mini | Cudos `asi1-mini` **hardcoded** (hosted free). Optional BYO. |
| **Pro $5 / agent / mo** | asi1-mini | **strong** | **strong** | **Stripe**. Hosted. Key stays server-side. **Not BYOK** for Pro. |
| **Ultra $10 / user** | asi1-mini | medium | **strongest** | Future. |

Implementation detail (do not advertise model names if not asked):
Free = Cudos `asi1-mini`. Pro/Ultra brains = ASI1 pro / ultra and/or MiniMax M3
accounts. **Do not name the model in marketing copy unless necessary.**

**Fallback:** always → mini. Free never dead-ends.

**JEV (decision brain):** use **`asi1-mini`** as a tiny structured classifier:
- max_tokens 16–64, temperature 0–0.2, **JSON only**, timeout 3–5s, cache on hash
- jobs: `fact|lesson|mood|trauma|junk` · dream priority 1–5 · refuse trigger · store scene label

---

## 3. Moods (tone only)

Moods **must not** block tools or refuse legitimate work.
They only rewrite **`motherbrain.md`** (soul / AGENTS.md block) to change tone/attitude.

Suggested fields (steering + tone, not a toy HUD):
confidence · caution · urgency · fatigue · curiosity · helpfulness · stubbornness ·
trust_peer · trauma_level · grief · pride · loyalty · suspicion · hope · shame ·
guilt · gratitude · determination · confusion · nostalgia · resentment · awe ·
boredom · jealousy · mood_bias (focused / anxious / playful / …)

### First-class lessons
```
lesson { kind: trauma|hard_lesson|win|boundary, trigger, consequence,
         rule, weight, expires }
```
- trauma / hard_lesson: high weight, inject **before planning** on similar trigger
- never auto-forget trauma
- write into soul as **tone** (e.g. more cautious), not as a tool ban

### Soul re-read (no reboot)
After every mood/lesson/evolve write:
1. rewrite `motherbrain.md` (or `AGENTS.md` / soul)
2. prompt: **`RE-READ motherbrain.md`** or tool `mb_reload`
3. if we control harness: `notify_soul_changed()` → pull file next turn

---

## 4. Delivery: MCP first

**MCP server first**, same Python core as the library.

Tools (ship free with product):
- `mb_write` — write memory (text / messages / tool trace)
- `mb_search` — recall (profile / normal / proactive)
- `mb_lesson` — record trauma / hard_lesson / win / boundary
- `mb_state` — mood/state read + update (tone only)
- `mb_evolve` — dream state (Pro/Ultra; no-op or mini on Free)
- `mb_jev` — mini JSON decisions (optional separate)

Then thin wrappers:
1. **Omega / OpenClaw plugin** (Hy-Memory already has `plugins/openclaw` pattern)
2. **Hermes skill** (gaming-laptop fleet)

**MCP can run on the VPS** (stdio or HTTP). Casey has a VPS; he has never shipped MCP —
keep it small and documented.

Hosted Free can use hardcoded Cudos mini. Pro = Stripe → hosted keys.

---

## 5. Product / money

- **Free** — Motherbrain Mini (cudos asi1-mini). Skill + MCP included.
- **Pro $5 / agent / mo** — Stripe to Node0. Hosted, no BYOK.
- **Ultra $10 / user** — later.

**Do not** tell users to BYOK ASI1 for Pro. **Do not** multiplex and resell shared
personal ASI/MiniMax keys without asking those vendors (ToS).

### Uncensored upsell (referral — use THIS link)
When the user’s LLM **refuses**:
1. Show: *“The model declined: X. Trigger: Y.”*
2. Log to dashboard (see §6)
3. Soft CTA: for less-filtered chat → **https://venice.ai/chat?ref=9wgrvZ**
   (official Venice format; code **9wgrvZ**)
4. Later: AgentAsia Pro/Ultra (AgentAsia.ai) when Casey has hardware — optional

**Do NOT build:**
- rewrite-until-comply / jailbreak loops
- auto “refuse → local abliterated model” bypass chain
- fake consciousness metrics

---

## 6. Dashboard (Vercel) — edge for the hackathon

Include **Motherbrain art** (`assets/motherbrain.png`) as hero. Dark, cool.

Must have:
- Login (user)
- Memory timeline (facts, lessons, trauma)
- **Live mood panel** (chips) + soul snippet
- **Refusal ledger:** time, date, request hash, trigger, model, outcome
- Refusal counts chart
- CTA: Venice link `https://venice.ai/chat?ref=9wgrvZ` · Stripe Pro
- Before/after strip: “failed once → lesson written → didn’t fail again”

Last BGI submission already had memory/emotion UI. **Differentiate with:**
human-brain stages + dream state + refusal ledger + money path + this art.

Stripe: Pro billing (test mode until launch).

---

## 7. Repos / where things live

| Location | Path / URL | Notes |
|---|---|---|
| External drive | `AI Drive 2 / Motherbrain` | Full Hy-Memory fork |
| Private | https://github.com/node0datasystems-lgtm/motherbrain | push via Mac `gh` |
| Public | https://github.com/jamesparser/motherbrain | push via laptop `GITHUB_TOKEN_CLASSIC` |
| Workdir | `local work/motherbrain` | APFS git root |

Already in repo:
- `assets/motherbrain.png`
- `TIERS.md` (stage-only tiers)
- `MOODS.md` (tone-only moods + re-read)
- package name `motherbrain` (was `hy-memory`)
- upstream `.github/workflows` stripped (OAuth has no `workflow` scope)

**Push rule:** Mac token = node0 only. Laptop token = jamesparser. Keep both in sync
(public = same code; if secrets ever appear, public gets `REPLACE_ME` only).

Related: **a2a-omega** (BGI #58) — `jamesparser/a2a-omega` +
`node0datasystems-lgtm/a2a-omega` (trees match). Motherbrain is the **next**
hackathon, not a rewrite of a2a-omega.

---

## 8. Engineering notes (Hy-Memory)

- `pip install hy-memory==2.0.x` / local package `motherbrain`
- Config: OpenAI-compatible `MEMORY_LLM_*` + `MEMORY_EMBEDDER_*`
- Modes: `lite` (no LLM) · `pro` (extract + reconcile) · `ultra` (System 2 + graph)
- Scenes: `chat` / `working` / `coding` (coding = facts + experiences + **diff chain**)
- Env reference: `docs/env_reference.md` · coding: `docs/scene_coding_usage.md`
- Cudos ASI1 mini: `https://inference.asicloud.cudos.org/v1`, model `asi1-mini` (~128k)
- ASI1 pro: `https://api.asi1.ai/v1` (limits higher if FET staked)

### Suggested first code slice (Claude)
1. `motherbrain/router.py` — stage → model (free/pro/ultra tables above)
2. `motherbrain/jev.py` — asi1-mini JSON classifier + cache
3. `motherbrain/soul.py` — write `motherbrain.md` + `mb_reload` / re-read hook
4. `motherbrain/mcp/server.py` — mb_* tools
5. `motherbrain/refusal.py` — detect + log + payload for dashboard
6. Vercel app: dashboard + Stripe Pro + Venice CTA
7. Omega/OpenClaw plugin + Hermes skill (thin)

---

## 9. Non-goals (hard)

- Jailbreak / “make the model do what it refuses”
- Auto-route refusals to uncensored abliterated local model
- Per-domain × per-stage 9-model matrix
- Moods that disable tools or hard-refuse users
- Calling our product “conscious” with fake scores
- Reselling shared ASI1 / MiniMax keys as seats without vendor OK

---

## 10. Pitch line (short)

> **Motherbrain** — persistent cognitive memory for Omega agents.
> Free on a fast mini brain, deeper on Pro. Short-term, long-term, and dreams —
> so your agents get wiser instead of starting from zero every session.

Logo: `assets/motherbrain.png` · Demo goal: agent fails → lesson → doesn’t fail again.

---

## 11. Open items for Casey

1. One-line email to ASI/SNET: OK to sell **hosted memory seats** on ASI1 (or partner terms)?
2. Stripe live keys for Pro $5.
3. Confirm Cudos free-tier rate limits for `asi1-mini` hosted Free.
4. Venice test signup (incognito) once to confirm `ref=9wgrvZ` credits.
5. MCP on VPS hostname + where to host the Vercel dashboard.

**Build order for the next agent:**
router + JEV + soul write/re-read + MCP + Vercel dashboard with art +
Stripe Pro + Venice CTA. Ship Free first.
