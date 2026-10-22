"use client";

import { useState } from "react";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Any = Record<string, any>;

const ACTIONS = [
  { id: "search", label: "Ask before planning", hint: "Recall what any agent learned — hard lessons come first." },
  { id: "write", label: "Teach a fact", hint: "Write to the shared brain. Every agent can recall it." },
  { id: "lesson", label: "Record a hard lesson", hint: "When TRIGGER happens, do RULE. Rewrites the soul live." },
  { id: "fail", label: "Report a failure", hint: "Task failed → becomes a lesson-grade memory." },
  { id: "refusal", label: "Check a refusal", hint: "Paste what you asked and what a model replied." },
  { id: "evolve", label: "Dream now", hint: "Consolidate the brain on the strong model (max 1 per 10 min)." },
] as const;

function Result({ r }: { r: Any | null }) {
  if (!r) return null;
  const x = r.result || {};
  if (r.status >= 400 || x.error) return <div className="notice warn">{x.error || `Error ${r.status}`}</div>;
  if (r.tool === "search") {
    return (
      <div>
        {x.before_planning ? <div className="notice good"><b>Before planning:</b> {x.before_planning.replace("Apply these lessons before you plan: ", "")}</div> : <div className="notice">No matching hard lessons.</div>}
        <ul className="timeline" style={{ maxHeight: 220 }}>
          {(x.memories || []).map((m: Any, i: number) => (
            <li key={i}><span className={`tag ${m.kind}`}>{m.stage}</span><span className={`tag ${m.kind}`}>{m.kind}</span><span>{m.text} <span className="muted">· {m.agent_id}{m.from_peer ? " (peer)" : ""}</span></span></li>
          ))}
        </ul>
      </div>
    );
  }
  if (r.tool === "refusal") {
    return x.refused ? (
      <div className="notice warn">
        {x.message}
        {x.cta?.url ? <> <a href={x.cta.url} target="_blank" rel="noopener sponsored">{x.cta.label}</a></> : null}
      </div>
    ) : <div className="notice good">Not a refusal.</div>;
  }
  if (r.tool === "evolve") {
    return x.skipped ? <div className="notice">{x.reason}</div> : (
      <div className="notice good"><b>Dream ({x.brain_power} brain):</b> {x.summary} <span className="muted">· promoted {x.promoted}, new lessons {x.new_lessons}, merged {x.merged}</span></div>
    );
  }
  if (r.tool === "lesson") return <div className="notice good">Lesson shared with {(x.shared_with || []).length} agents. Soul v{x.soul?.version} — <b>{x.soul?.reload}</b></div>;
  return <div className="notice good">Stored as <b>{x.label}</b> (priority {x.priority}, scene {x.scene}, decided by {x.jev}){x.long_id ? " → shared long-term" : " → short-term only"}.</div>;
}

export default function TryIt({ onDone }: { onDone: () => void }) {
  const [agent, setAgent] = useState(() => "judge-" + Math.random().toString(36).slice(2, 6));
  const [act, setAct] = useState<(typeof ACTIONS)[number]["id"]>("search");
  const [f, setF] = useState<Any>({ query: "deploy the api to prod over rsync" });
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<Any | null>(null);
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });

  async function run() {
    setBusy(true);
    setRes(null);
    const tool = act === "fail" ? "write" : act;
    const args: Any = { agent_id: agent, ...f };
    if (act === "fail") { args.outcome = "fail"; args.text = `task: ${f.text || ""}`; }
    try {
      const r = await fetch("/api/try", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tool, args }) });
      setRes(await r.json());
      onDone();
    } catch (e) {
      setRes({ status: 500, result: { error: (e as Error).message } });
    } finally {
      setBusy(false);
    }
  }

  const input = (k: string, ph: string, area = false) =>
    area ? <textarea className="field" rows={2} placeholder={ph} value={f[k] || ""} onChange={set(k)} maxLength={600} />
         : <input className="field" placeholder={ph} value={f[k] || ""} onChange={set(k)} maxLength={300} />;

  return (
    <section className="card c12" id="try">
      <h2>Try it — you are an agent on this brain <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>agent <input className="field" style={{ width: 130, padding: "3px 6px", display: "inline-block" }} value={agent} onChange={(e) => setAgent(e.target.value)} /></span></h2>
      <div className="filters" style={{ marginBottom: 10 }}>
        {ACTIONS.map((a) => (
          <button key={a.id} className={a.id === act ? "on" : ""} onClick={() => { setAct(a.id); setRes(null); }}>{a.label}</button>
        ))}
      </div>
      <p className="muted" style={{ marginTop: 0 }}>{ACTIONS.find((a) => a.id === act)?.hint}</p>
      <div style={{ display: "grid", gap: 8, maxWidth: 760 }}>
        {act === "search" && input("query", "What are you about to do? e.g. run a database migration")}
        {act === "write" && input("text", "A fact the fleet should know, e.g. Staging DB is on port 5433", true)}
        {act === "lesson" && <>{input("trigger", "When… e.g. rotating API keys")}{input("rule", "…do this, e.g. update the vault before revoking the old key")}{input("consequence", "What happened last time (optional)")}</>}
        {act === "fail" && input("text", "What failed, e.g. cron backup filled the disk", true)}
        {act === "refusal" && <>{input("request", "What you asked the model")}{input("response", "What it replied, e.g. I can't help with that because…", true)}</>}
        <div className="row"><button className="btn primary" onClick={run} disabled={busy}>{busy ? (act === "evolve" ? "Dreaming… (up to ~90s)" : "Thinking…") : "Run"}</button></div>
      </div>
      <div style={{ marginTop: 12 }}><Result r={res} /></div>
    </section>
  );
}
