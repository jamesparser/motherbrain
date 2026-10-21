"use client";

import { useEffect, useMemo, useState } from "react";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Any = Record<string, any>;
const VENICE_URL = "https://venice.ai/chat?ref=9wgrvZ";

const fmtTime = (ts: number) => new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
const fmtDate = (ts: number) => new Date(ts * 1000).toLocaleDateString([], { month: "short", day: "numeric" });
const label = (s: string) => s.replace(/_/g, " ");

function describe(e: Any): { tag: string; text: string } {
  switch (e.type) {
    case "memory":
      return { tag: e.kind || "memory", text: e.text };
    case "lesson_written":
      return { tag: e.kind, text: `When ${e.trigger} → ${e.rule}${e.consequence ? ` (last time: ${e.consequence})` : ""}` };
    case "lesson_applied":
      return { tag: "lesson_applied", text: `Recalled ${e.author}'s ${label(e.kind)} before planning: “${e.trigger}”` };
    case "dream":
      return { tag: "dream", text: e.summary };
    case "join":
      return { tag: "join", text: `${e.agent_id} joined the brain${e.kind ? ` (${e.kind})` : ""}` };
    case "refusal":
      return { tag: "refusal", text: `Model declined (${e.category}) · ${e.model ?? "unknown model"}` };
    case "task_outcome":
      return { tag: e.ok ? "ok" : "trauma", text: `${e.ok ? "Succeeded" : "Failed"}: ${e.text}` };
    case "mood":
      return { tag: "mood", text: Object.entries(e.changed || {}).map(([k, v]) => `${label(k)} → ${typeof v === "number" ? v.toFixed(2) : v}`).join(", ") };
    default:
      return { tag: e.type, text: JSON.stringify(e) };
  }
}

const FILTERS: Record<string, (e: Any) => boolean> = {
  all: () => true,
  facts: (e) => e.type === "memory" && e.kind === "fact",
  lessons: (e) => e.type === "lesson_written" || e.type === "lesson_applied" || (e.type === "memory" && e.kind === "lesson"),
  trauma: (e) => (e.type === "lesson_written" && e.kind === "trauma") || (e.type === "task_outcome" && !e.ok) || (e.type === "memory" && e.kind === "trauma"),
  dreams: (e) => e.type === "dream",
  refusals: (e) => e.type === "refusal",
};

export default function Dashboard(props: {
  initial: Any; live: boolean; error?: string; email: string; stripe: boolean; flash?: "upgraded" | "canceled";
}) {
  const [d, setD] = useState<Any>(props.initial);
  const [live, setLive] = useState(props.live);
  const [filter, setFilter] = useState("all");
  const [agents, setAgents] = useState(Math.max(1, props.initial.members?.length || 1));
  const [busy, setBusy] = useState(false);
  const [checkoutErr, setCheckoutErr] = useState<string | null>(null);

  useEffect(() => {
    if (!props.live) return;
    const t = setInterval(async () => {
      try {
        const r = await fetch("/api/brain", { cache: "no-store" });
        if (r.ok) {
          const j = await r.json();
          setD(j.data);
          setLive(j.live);
        }
      } catch {}
    }, 10_000);
    return () => clearInterval(t);
  }, [props.live]);

  const tl = useMemo(() => (d.timeline as Any[]).filter(FILTERS[filter]), [d, filter]);
  const ba = (d.before_after as Any[]).filter((b) => b.fails_before > 0 || b.applied > 0).slice(0, 4);
  const maxRef = Math.max(1, ...(d.refusals_by_day as Any[]).map((r) => r.count));
  const tier = d.brain.tier as string;
  const power = (s: string) => d.router?.[s]?.power ?? "mini";

  async function upgrade() {
    setBusy(true);
    setCheckoutErr(null);
    try {
      const r = await fetch("/api/checkout", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ agents, brain: d.brain.id }) });
      const j = await r.json();
      if (j.url) window.location.href = j.url;
      else setCheckoutErr(j.error || "Checkout failed");
    } catch (e) {
      setCheckoutErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="wrap">
      <header className="top">
        <div className="brand">
          <img src="/motherbrain.png" alt="" />
          Motherbrain
          <span className={`badge ${tier === "free" ? "" : "red"}`}>{tier}</span>
          <span className={`badge ${live ? "green" : ""}`}>{live ? "live" : "demo data"}</span>
        </div>
        <form method="post" action="/api/logout" className="row">
          <span className="muted" style={{ fontSize: 12 }}>{props.email}</span>
          <button className="btn ghost">Log out</button>
        </form>
      </header>

      {props.flash === "upgraded" && <div className="notice good">Pro is active. Long-term and dream now run on the stronger brain.</div>}
      {props.flash === "canceled" && <div className="notice">Checkout canceled. You are still on {tier}.</div>}
      {props.error && <div className="notice warn">Brain API unreachable ({props.error}). Showing demo data.</div>}

      <section className="hero">
        <div className="art"><img src="/motherbrain.png" alt="Motherbrain — red brain in a jar" /></div>
        <div>
          <h1>One brain.<br /><span>Every agent.</span></h1>
          <p className="lede">
            Persistent memory for Omega agents: short-term, long-term identity, hard lessons, and dream-state
            consolidation. {d.members.length} agents share <b>{d.brain.name}</b>, so when one learns, the fleet learns.
          </p>
          <div className="row">
            {tier === "free" ? (
              <button className="btn primary" onClick={upgrade} disabled={busy || !props.stripe} title={props.stripe ? "" : "Stripe not configured on this deployment"}>
                {busy ? "Opening checkout…" : `Upgrade to Pro · $${5 * agents}/mo`}
              </button>
            ) : (
              <span className="badge red">Pro active</span>
            )}
            <a className="btn" href="#connect">Connect an agent (MCP)</a>
          </div>
          {checkoutErr && <p className="muted" style={{ color: "#ff6b7a" }}>{checkoutErr}</p>}
          <div className="stats">
            <div className="stat"><b>{d.members.length}</b><small>agents</small></div>
            <div className="stat"><b>{d.counts.long}</b><small>long-term</small></div>
            <div className="stat"><b>{d.counts.lessons}</b><small>lessons</small></div>
            <div className="stat"><b>{d.counts.refusals}</b><small>refusals</small></div>
          </div>
        </div>
      </section>

      <section className="stages" aria-label="Memory stages">
        <div className="stage"><h3>Short-term</h3><div className="n">{d.counts.short}</div><div className="pw">now · last turns per agent · {power("short")} brain</div></div>
        <div className="stage"><h3>Long-term</h3><div className="n">{d.counts.long}</div><div className="pw">facts, lessons, identity · shared · {power("long")} brain</div></div>
        <div className="stage dream"><h3>Dream</h3><div className="n">{d.counts.dream}</div><div className="pw">consolidate &amp; evolve · {power("dream")} brain</div></div>
      </section>

      {ba.length > 0 && (
        <section className="card" style={{ marginBottom: 16 }}>
          <h2>Failed once → lesson written → didn’t fail again</h2>
          <div className="ba">
            {ba.map((b) => (
              <div className="baitem" key={b.lesson_id}>
                <div className="step bad"><b>{b.fails_before}</b>failed before</div>
                <div className="arrow">→</div>
                <div className="step mid"><b>{b.applied}×</b>{label(b.kind)} recalled</div>
                <div className="arrow">→</div>
                <div className="step good"><b>{b.fails_after}</b>fails since{b.ok_after ? ` · ${b.ok_after} ok` : ""}</div>
                <div className="rule">
                  <b>{b.author}</b> learned: when <i>{b.trigger}</i> → {b.rule}
                  {b.ok_after_agents?.length ? <> · applied by <b>{b.ok_after_agents.join(", ")}</b></> : null}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <div className="grid">
        <section className="card c7">
          <h2>Live mood <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>tone only · never blocks tools</span></h2>
          <div className="bias">{d.mood.mood_bias}<small>brain-wide</small></div>
          <div className="chips">
            {(d.chips as Any[]).map((c) => (
              <div className="chip" key={c.field}>
                <span>{label(c.field)} · {Math.round(c.value * 100)}</span>
                <i><em style={{ width: `${Math.round(c.value * 100)}%` }} /></i>
              </div>
            ))}
          </div>
          <ul className="tone">{(d.tone as string[]).map((t) => <li key={t}>{t}</li>)}</ul>
        </section>

        <section className="card c5">
          <h2>Members <span className="badge">{d.members.length}</span></h2>
          <ul className="members">
            {(d.members as Any[]).map((m) => (
              <li key={m.agent_id}>
                <div className="who"><span className="dot" /><b className="mono">{m.agent_id}</b><span className="muted">{m.kind}</span></div>
                <span className="muted" style={{ fontSize: 12 }}>{m.writes} writes</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="card c7">
          <h2>
            Memory timeline
            <span className="filters">
              {Object.keys(FILTERS).map((f) => (
                <button key={f} className={f === filter ? "on" : ""} onClick={() => setFilter(f)}>{f}</button>
              ))}
            </span>
          </h2>
          <ul className="timeline">
            {tl.length === 0 && <li className="muted">Nothing here yet.</li>}
            {tl.map((e, i) => {
              const x = describe(e);
              return (
                <li key={i}>
                  <span className="when">{fmtDate(e.ts)} {fmtTime(e.ts)}</span>
                  <span className={`tag ${x.tag}`}>{label(x.tag)}</span>
                  <span>{x.text}{e.agent_id && e.type !== "join" ? <span className="muted"> · {e.agent_id}</span> : null}</span>
                </li>
              );
            })}
          </ul>
        </section>

        <section className="card c5">
          <h2>Soul · motherbrain.md <span className="badge">re-read, no reboot</span></h2>
          <pre className="soul">{d.soul}</pre>
        </section>

        <section className="card c8">
          <h2>Refusal ledger <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>request hash only · never retried</span></h2>
          <div className="tablewrap">
            <table>
              <thead><tr><th>Date</th><th>Time</th><th>Request</th><th>Trigger</th><th>Model</th><th>Agent</th><th>Outcome</th></tr></thead>
              <tbody>
                {(d.refusals as Any[]).map((r) => (
                  <tr key={r.id}>
                    <td>{fmtDate(r.ts)}</td>
                    <td>{fmtTime(r.ts)}</td>
                    <td className="mono">{r.request_hash.slice(0, 10)}</td>
                    <td>{r.trigger}</td>
                    <td className="mono">{r.model ?? "—"}</td>
                    <td className="mono">{r.agent_id ?? "—"}</td>
                    <td><span className="tag refusal">{r.outcome}</span></td>
                  </tr>
                ))}
                {d.refusals.length === 0 && <tr><td colSpan={7} className="muted">No refusals logged.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>

        <section className="card c4">
          <h2>Refusals per day</h2>
          <div className="chart" role="img" aria-label="Refusals per day">
            {(d.refusals_by_day as Any[]).map((r) => (
              <div className="bar" key={r.day} title={`${r.day}: ${r.count}`}>
                <b>{r.count}</b>
                <div style={{ height: `${(r.count / maxRef) * 100}%` }} />
                <small>{r.day.slice(5)}</small>
              </div>
            ))}
          </div>
          <div className="card cta" style={{ marginTop: 14, padding: 14 }}>
            <b>Model said no?</b>
            <p className="muted" style={{ margin: "6px 0 10px", fontSize: 13 }}>
              Motherbrain logs it and moves on. For a less-filtered chat, try Venice.
            </p>
            <a className="btn primary" href={VENICE_URL} target="_blank" rel="noopener sponsored">Open Venice</a>
            <p className="muted" style={{ fontSize: 11, margin: "8px 0 0" }}>Referral link.</p>
          </div>
        </section>

        <section className="card c12" id="pricing">
          <h2>Plans</h2>
          <div className="price">
            <div className={`tier ${tier === "free" ? "hot" : ""}`}>
              <b>Motherbrain Mini</b>
              <div className="amt">$0</div>
              <ul><li>Short-term, long-term and dream on the fast mini brain</li><li>MCP server + skills included</li><li>Unlimited agents on one shared brain</li></ul>
              <span className="badge">{tier === "free" ? "current" : "included"}</span>
            </div>
            <div className={`tier ${tier === "pro" ? "hot" : ""}`}>
              <b>Pro</b>
              <div className="amt">$5<small> / agent / mo</small></div>
              <ul><li>Stronger brain for long-term writes and dreams</li><li>Hosted — keys stay server-side</li><li>Falls back to mini, never dead-ends</li></ul>
              {tier === "pro" ? <span className="badge red">current</span> : (
                <div className="row">
                  <input aria-label="Agents" type="number" min={1} max={100} value={agents} onChange={(e) => setAgents(Math.max(1, Math.min(100, Number(e.target.value) || 1)))}
                    style={{ width: 64, padding: 8, borderRadius: 8, border: "1px solid var(--line)", background: "#0b0b10", color: "var(--text)" }} />
                  <button className="btn primary" onClick={upgrade} disabled={busy || !props.stripe}>Upgrade</button>
                </div>
              )}
              {!props.stripe && <span className="muted" style={{ fontSize: 11 }}>Stripe test keys not set on this deployment.</span>}
            </div>
            <div className="tier">
              <b>Ultra</b>
              <div className="amt">$10<small> / user</small></div>
              <ul><li>Strongest dream state</li><li>Deeper consolidation and conflict reconciliation</li></ul>
              <span className="badge">coming soon</span>
            </div>
          </div>
        </section>

        <section className="card c12" id="connect">
          <h2>Connect an agent</h2>
          <p className="muted" style={{ marginTop: 0 }}>Every agent that connects joins the same brain. Call <code>mb_join</code> once, then <code>mb_search</code> before planning.</p>
          <pre className="soul">{`{
  "mcpServers": {
    "motherbrain": {
      "command": "motherbrain",
      "args": ["mcp"],
      "env": { "MB_BRAIN": "${d.brain.id}", "MB_AGENT_ID": "my-agent", "MB_CUDOS_API_KEY": "…" }
    }
  }
}

# or over HTTP (VPS):  https://<your-vps>/mcp   ·  Authorization: Bearer <MB_API_KEY>`}</pre>
        </section>
      </div>

      <footer>
        Motherbrain · Node0 Data Systems · built on Tencent Hy-Memory (Apache-2.0) · cognitive architecture, not a consciousness score.
      </footer>
    </div>
  );
}
