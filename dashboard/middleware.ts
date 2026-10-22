import { NextRequest, NextResponse } from "next/server";
import { COOKIE, readSession } from "./lib/session";

export async function middleware(req: NextRequest) {
  const s = await readSession(req.cookies.get(COOKIE)?.value);
  if (!s) {
    if (req.nextUrl.pathname.startsWith("/api/")) {
      return NextResponse.json({ error: "unauthorized" }, { status: 401 });
    }
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

// Everything except login, the Stripe webhook, and static assets needs a session.
export const config = {
  matcher: ["/((?!login|api/login|api/auth/|api/owner/ingest|api/stripe/webhook|_next/|favicon|motherbrain.png).*)"],
};
