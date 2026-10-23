"use client";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Any = Record<string, any>;

const LABEL: Record<string, string> = {
  shell: "doing", pin: "noting", remember: "remembering", send: "saying", message_in: "heard", query: "recalling",
  websearch: "searching", "read-file": "reading", "write-file": "writing", "append-file": "writing", episodes: "recalling",
  metta: "reasoning", "mb-recall": "asking the brain", "mb-lesson": "learning", note: "note",
  thinking: "thinking", planning: "planning", doing: "doing", saying: "saying", error: "error", recalling: "recalling", learning: "learning",
};
const TAG: Record<string, string> = { error: "trauma", learning: "lesson", recalling: "dream", planning: "fact", saying: "ok", pin: "lesson", remember: "lesson", send: "ok", message_in: "fact", shell: "memory", websearch: "dream", query: "dream" };

export default function Thoughts({ items, ageSec }: { items: Any[]; ageSec?: number }) {
  return (
    <section className="card c12" id="thoughts">
      <h2>
        What the agents are thinking — live
        <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>
          {items.length ? (ageSec !== undefined ? `streamed from your agents · synced ${ageSec}s ago` : "streamed live from the agents on this brain") : "waiting for activity"}
        </span>
      </h2>
      <ul className="timeline" style={{ maxHeight: 420 }}>
        {items.length === 0 && <li className="muted">No activity yet. When your Omega acts, notes or speaks, it shows up here.</li>}
        {items.map((t, i) => (
          <li key={i}>
            <span className="when">{String(t.at || "").slice(11, 19) || new Date(t.ts * 1000).toLocaleTimeString()}</span>
            <span className={`tag ${TAG[t.kind] || "memory"}`}>{LABEL[t.kind] || t.kind}</span>
            <span className={t.kind === "shell" ? "mono" : ""} style={t.kind === "shell" ? { fontSize: 12 } : undefined}>
              {t.text}<span className="muted"> · {t.agent_id}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
