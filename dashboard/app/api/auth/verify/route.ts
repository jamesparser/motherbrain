import { NextRequest, NextResponse } from "next/server";
import { COOKIE, COOKIE_OPTS, createSession, unseal } from "@/lib/session";

export async function GET(req: NextRequest) {
  const t = await unseal<{ email: string; purpose: string; exp: number }>(req.nextUrl.searchParams.get("t"));
  if (!t || t.purpose !== "login") return NextResponse.redirect(new URL("/login?e=link", req.url), 303);
  const res = NextResponse.redirect(new URL("/", req.url), 303);
  res.cookies.set(COOKIE, await createSession(t.email, false, "email"), COOKIE_OPTS);
  return res;
}
