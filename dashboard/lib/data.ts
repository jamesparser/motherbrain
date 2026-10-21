import demo from "./demo.json";

export type Snapshot = typeof demo;
export const VENICE_URL = "https://venice.ai/chat?ref=9wgrvZ";

export async function getSnapshot(): Promise<{ data: Snapshot; live: boolean; error?: string }> {
  const url = process.env.MB_API_URL;
  if (!url) return { data: demo as Snapshot, live: false };
  try {
    const r = await fetch(`${url.replace(/\/$/, "")}/api/snapshot`, {
      headers: { Authorization: `Bearer ${process.env.MB_API_KEY ?? ""}` },
      cache: "no-store",
      signal: AbortSignal.timeout(6000),
    });
    if (!r.ok) throw new Error(`brain API ${r.status}`);
    return { data: (await r.json()) as Snapshot, live: true };
  } catch (e) {
    return { data: demo as Snapshot, live: false, error: (e as Error).message };
  }
}

export function stripeConfigured(): boolean {
  return Boolean((process.env.STRIPE_SECRET_KEY && process.env.STRIPE_PRICE_PRO) || process.env.STRIPE_PAYMENT_LINK);
}
