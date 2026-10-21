import { NextRequest, NextResponse } from "next/server";
import { COOKIE, readSession } from "@/lib/session";

// Stripe Checkout for Pro: $5 / agent / month. Hosted keys stay server-side — no BYOK.
export async function POST(req: NextRequest) {
  const key = process.env.STRIPE_SECRET_KEY;
  const price = process.env.STRIPE_PRICE_PRO;
  if (!key || !price) {
    return NextResponse.json({ error: "Stripe is not configured yet (set STRIPE_SECRET_KEY and STRIPE_PRICE_PRO)." }, { status: 503 });
  }
  const session = await readSession(req.cookies.get(COOKIE)?.value);
  const body = await req.json().catch(() => ({}));
  const agents = Math.max(1, Math.min(100, Number(body.agents) || 1));
  const brain = String(body.brain || "default").slice(0, 64);
  const site = process.env.NEXT_PUBLIC_SITE_URL || new URL(req.url).origin;
  const params = new URLSearchParams({
    mode: "subscription",
    "line_items[0][price]": price,
    "line_items[0][quantity]": String(agents),
    "line_items[0][adjustable_quantity][enabled]": "true",
    "line_items[0][adjustable_quantity][minimum]": "1",
    "line_items[0][adjustable_quantity][maximum]": "100",
    success_url: `${site}/?upgraded=1`,
    cancel_url: `${site}/?canceled=1`,
    "metadata[brain_id]": brain,
    "subscription_data[metadata][brain_id]": brain,
    allow_promotion_codes: "true",
  });
  if (session?.email) params.set("customer_email", session.email);
  const r = await fetch("https://api.stripe.com/v1/checkout/sessions", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/x-www-form-urlencoded" },
    body: params,
  });
  const j = await r.json();
  if (!r.ok) return NextResponse.json({ error: j?.error?.message || "Stripe error" }, { status: 502 });
  return NextResponse.json({ url: j.url });
}
