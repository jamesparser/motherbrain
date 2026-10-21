import { NextRequest, NextResponse } from "next/server";
import crypto from "node:crypto";

export const runtime = "nodejs";

function verify(payload: string, header: string | null, secret: string): boolean {
  if (!header) return false;
  const parts = Object.fromEntries(header.split(",").map((kv) => kv.split("=") as [string, string]));
  const t = parts.t;
  const sigs = header.split(",").filter((p) => p.startsWith("v1=")).map((p) => p.slice(3));
  if (!t || !sigs.length || Math.abs(Date.now() / 1000 - Number(t)) > 300) return false;
  const expected = crypto.createHmac("sha256", secret).update(`${t}.${payload}`).digest("hex");
  return sigs.some((s) => s.length === expected.length && crypto.timingSafeEqual(Buffer.from(s), Buffer.from(expected)));
}

async function setTier(tier: "free" | "pro", source: string) {
  const url = process.env.MB_API_URL;
  if (!url || !process.env.MB_ADMIN_KEY) return;
  await fetch(`${url.replace(/\/$/, "")}/api/tier`, {
    method: "POST",
    headers: { Authorization: `Bearer ${process.env.MB_ADMIN_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({ tier, source }),
  });
}

export async function POST(req: NextRequest) {
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  const payload = await req.text();
  if (!secret || !verify(payload, req.headers.get("stripe-signature"), secret)) {
    return NextResponse.json({ error: "bad signature" }, { status: 400 });
  }
  const event = JSON.parse(payload);
  switch (event.type) {
    case "checkout.session.completed":
      await setTier("pro", `stripe:${event.data.object.id}`);
      break;
    case "customer.subscription.deleted":
      await setTier("free", `stripe:${event.data.object.id}`);
      break;
  }
  return NextResponse.json({ received: true });
}
