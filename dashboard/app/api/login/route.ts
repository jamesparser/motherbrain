import { NextRequest, NextResponse } from "next/server";
import { COOKIE, COOKIE_OPTS, createSession } from "@/lib/session";

// Demo login (judges): any email, unverified → always the public demo brain, never an owner brain.
export async function POST(req: NextRequest) {
  const form = await req.formData();
  const email = String(form.get("email") || "").trim().toLowerCase();
  const password = String(form.get("password") || "");
  const required = process.env.DASHBOARD_PASSWORD;
  const back = (q: string) => NextResponse.redirect(new URL(`/login?e=${q}`, req.url), 303);
  if (!email || !email.includes("@")) return back("email");
  if (required && password !== required) return back("password");
  const res = NextResponse.redirect(new URL("/", req.url), 303);
  res.cookies.set(COOKIE, await createSession(email, true, "demo"), COOKIE_OPTS);
  return res;
}
