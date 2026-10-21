import { NextRequest, NextResponse } from "next/server";
import { COOKIE, createSession } from "@/lib/session";

export async function POST(req: NextRequest) {
  const form = await req.formData();
  const email = String(form.get("email") || "").trim().toLowerCase();
  const password = String(form.get("password") || "");
  const required = process.env.DASHBOARD_PASSWORD;
  const back = (q: string) => NextResponse.redirect(new URL(`/login?e=${q}`, req.url), 303);
  if (!email || !email.includes("@")) return back("email");
  if (required && password !== required) return back("password");
  const res = NextResponse.redirect(new URL("/", req.url), 303);
  res.cookies.set(COOKIE, await createSession(email, !required), {
    httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 7 * 86400,
  });
  return res;
}
