import demo from "./demo.json";
import { isOwner, type Session } from "./session";

export type Snapshot = typeof demo & { thoughts?: Record<string, unknown>[]; pushed_at?: number };
export const VENICE_URL = "https://venice.ai/chat?ref=9wgrvZ";

export type Loaded = { data: Snapshot; live: boolean; owner: boolean; error?: string; ageSec?: number };

async function ownerSnapshot(): Promise<Loaded | null> {
  if (!process.env.BLOB_READ_WRITE_TOKEN) return null;
  try {
    const { get } = await import("@vercel/blob");
    const r = await get("owner/fleet.json", { access: "private", useCache: false });
    if (!r || !r.stream) return null;
    const text = await new Response(r.stream).text();
    const data = JSON.parse(text) as Snapshot;
    const ageSec = data.pushed_at ? Math.round((Date.now() - data.pushed_at) / 1000) : undefined;
    return { data, live: ageSec !== undefined && ageSec < 400, owner: true, ageSec };
  } catch (e) {
    return { data: demo as Snapshot, live: false, owner: true, error: `fleet snapshot unavailable (${(e as Error).message})` };
  }
}

export async function getSnapshot(session?: Session | null): Promise<Loaded> {
  if (isOwner(session ?? null)) {
    const o = await ownerSnapshot();
    if (o) return o;
  }
  const url = process.env.MB_API_URL;
  if (!url) return { data: demo as Snapshot, live: false, owner: false };
  try {
    const r = await fetch(`${url.replace(/\/$/, "")}/api/snapshot`, {
      headers: { Authorization: `Bearer ${process.env.MB_API_KEY ?? ""}` },
      cache: "no-store",
      signal: AbortSignal.timeout(6000),
    });
    if (!r.ok) throw new Error(`brain API ${r.status}`);
    return { data: (await r.json()) as Snapshot, live: true, owner: false };
  } catch (e) {
    return { data: demo as Snapshot, live: false, owner: false, error: (e as Error).message };
  }
}

export function stripeConfigured(): boolean {
  return Boolean((process.env.STRIPE_SECRET_KEY && process.env.STRIPE_PRICE_PRO) || process.env.STRIPE_PAYMENT_LINK);
}

export function authOptions() {
  return { google: Boolean(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET), email: Boolean(process.env.RESEND_API_KEY && process.env.EMAIL_FROM) };
}
