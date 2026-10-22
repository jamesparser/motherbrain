import { NextRequest, NextResponse } from "next/server";

// Judge playground: a few whitelisted tools against the demo brain, using the rate-limited public key.
const ALLOWED = new Set(["join", "search", "write", "lesson", "refusal", "evolve"]);
const clip = (v: unknown, n = 600) => (typeof v === "string" ? v.slice(0, n) : v);

export async function POST(req: NextRequest) {
  const url = process.env.MB_API_URL;
  const key = process.env.MB_PUBLIC_KEY || process.env.MB_API_KEY;
  if (!url || !key) return NextResponse.json({ error: "Playground needs MB_API_URL and MB_PUBLIC_KEY." }, { status: 503 });
  const body = await req.json().catch(() => ({}));
  const tool = String(body.tool || "");
  if (!ALLOWED.has(tool)) return NextResponse.json({ error: "tool not allowed" }, { status: 400 });
  const a = (body.args || {}) as Record<string, unknown>;
  const agent = "judge-" + String(a.agent_id || "anon").replace(/[^a-zA-Z0-9_-]/g, "").replace(/^judge-/, "").slice(0, 24);
  const args: Record<string, unknown> = { agent_id: agent };
  for (const k of ["query", "text", "trigger", "rule", "consequence", "request", "response", "outcome", "kind", "mode"]) {
    if (a[k] !== undefined && a[k] !== "") args[k] = clip(a[k]);
  }
  if (tool === "join") args.kind = "judge";
  if (tool === "lesson") args.kind = ["trauma", "hard_lesson", "win", "boundary"].includes(String(a.kind)) ? a.kind : "hard_lesson";
  if (tool === "search") args.mode = "proactive";
  if (tool === "write" && !["ok", "fail"].includes(String(a.outcome))) delete args.outcome;
  const r = await fetch(`${url.replace(/\/$/, "")}/api/tools/${tool}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json", "X-Forwarded-For": req.headers.get("x-forwarded-for") || "" },
    body: JSON.stringify(args),
    signal: AbortSignal.timeout(tool === "evolve" ? 120_000 : 20_000),
  }).catch((e: Error) => ({ ok: false, status: 502, json: async () => ({ error: e.message }) }) as unknown as Response);
  const j = await r.json().catch(() => ({ error: `brain returned ${r.status}` }));
  return NextResponse.json({ agent, tool, status: r.status, result: j }, { status: r.ok ? 200 : r.status });
}

export const maxDuration = 120;
