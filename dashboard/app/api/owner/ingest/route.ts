import { NextRequest, NextResponse } from "next/server";
import { put } from "@vercel/blob";
import { gunzipSync } from "node:zlib";
import crypto from "node:crypto";

export const runtime = "nodejs";

// The private fleet brain pushes its snapshot here (outbound from the VPS). Stored as a PRIVATE blob,
// readable only by the server for owner sessions.
export async function POST(req: NextRequest) {
  const want = process.env.MB_PUSH_SECRET || "";
  const got = (req.headers.get("authorization") || "").replace(/^Bearer\s+/, "");
  if (!want || got.length !== want.length || !crypto.timingSafeEqual(Buffer.from(got), Buffer.from(want))) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  let raw: Buffer = Buffer.from(await req.arrayBuffer());
  if (raw.length > 4_000_000) return NextResponse.json({ error: "too large" }, { status: 413 });
  if (req.headers.get("content-encoding") === "gzip" || (raw[0] === 0x1f && raw[1] === 0x8b)) raw = Buffer.from(gunzipSync(raw));
  let snap: Record<string, unknown>;
  try {
    snap = JSON.parse(raw.toString("utf8"));
  } catch {
    return NextResponse.json({ error: "bad json" }, { status: 400 });
  }
  if (!snap.brain || !snap.counts) return NextResponse.json({ error: "not a snapshot" }, { status: 400 });
  snap.pushed_at = Date.now();
  await put("owner/fleet.json", JSON.stringify(snap), {
    access: "private", addRandomSuffix: false, allowOverwrite: true, contentType: "application/json",
  });
  return NextResponse.json({ ok: true });
}
