import { NextRequest, NextResponse } from "next/server";
import { siteUrl } from "@/lib/session";

export async function GET(req: NextRequest) {
  const id = process.env.GOOGLE_CLIENT_ID;
  if (!id) return NextResponse.redirect(new URL("/login?e=google", req.url));
  const state = crypto.randomUUID();
  const u = new URL("https://accounts.google.com/o/oauth2/v2/auth");
  u.search = new URLSearchParams({
    client_id: id,
    redirect_uri: `${siteUrl(req.url)}/api/auth/google/callback`,
    response_type: "code",
    scope: "openid email profile",
    state,
    prompt: "select_account",
  }).toString();
  const res = NextResponse.redirect(u);
  res.cookies.set("mb_oauth_state", state, { httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 600 });
  return res;
}
