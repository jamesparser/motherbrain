import { NextRequest, NextResponse } from "next/server";
import { COOKIE, COOKIE_OPTS, createSession, siteUrl } from "@/lib/session";

export async function GET(req: NextRequest) {
  const back = (e: string) => NextResponse.redirect(new URL(`/login?e=${e}`, req.url), 303);
  const q = req.nextUrl.searchParams;
  const state = req.cookies.get("mb_oauth_state")?.value;
  if (!q.get("code") || !state || q.get("state") !== state) return back("google");
  const r = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      code: q.get("code")!,
      client_id: process.env.GOOGLE_CLIENT_ID || "",
      client_secret: process.env.GOOGLE_CLIENT_SECRET || "",
      redirect_uri: `${siteUrl(req.url)}/api/auth/google/callback`,
      grant_type: "authorization_code",
    }),
  });
  const tok = await r.json().catch(() => ({}));
  if (!r.ok || !tok.id_token) return back("google");
  // id_token came straight from Google's token endpoint over TLS with our client secret: read its claims.
  let claims: Record<string, unknown> = {};
  try {
    claims = JSON.parse(Buffer.from(String(tok.id_token).split(".")[1], "base64url").toString());
  } catch {
    return back("google");
  }
  const okIss = claims.iss === "https://accounts.google.com" || claims.iss === "accounts.google.com";
  if (!okIss || claims.aud !== process.env.GOOGLE_CLIENT_ID || claims.email_verified !== true || !claims.email) return back("google");
  const res = NextResponse.redirect(new URL("/", req.url), 303);
  res.cookies.set(COOKIE, await createSession(String(claims.email), false, "google", String(claims.name || "")), COOKIE_OPTS);
  res.cookies.delete("mb_oauth_state");
  return res;
}
