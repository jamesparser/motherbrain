import { NextRequest, NextResponse } from "next/server";
import { seal, siteUrl } from "@/lib/session";

// Magic link: signed, 15-minute token emailed via Resend. No password stored anywhere.
export async function POST(req: NextRequest) {
  const form = await req.formData();
  const email = String(form.get("email") || "").trim().toLowerCase();
  const back = (q: string) => NextResponse.redirect(new URL(`/login?${q}`, req.url), 303);
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return back("e=email");
  const key = process.env.RESEND_API_KEY;
  const from = process.env.EMAIL_FROM;
  if (!key || !from) return back("e=mailer");
  const token = await seal({ email, purpose: "login", n: crypto.randomUUID(), exp: Date.now() + 15 * 60_000 });
  const link = `${siteUrl(req.url)}/api/auth/verify?t=${encodeURIComponent(token)}`;
  const r = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      from,
      to: [email],
      subject: "Your Motherbrain sign-in link",
      text: `Sign in to Motherbrain:\n\n${link}\n\nThis link expires in 15 minutes. If you didn't ask for it, ignore this email.`,
      html: `<p>Sign in to <b>Motherbrain</b>:</p><p><a href="${link}">Open my dashboard</a></p><p style="color:#888">Expires in 15 minutes. If you didn't ask for it, ignore this email.</p>`,
    }),
  });
  return back(r.ok ? `sent=1` : "e=mailer");
}
