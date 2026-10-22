import { authOptions } from "@/lib/data";

const ERR: Record<string, string> = {
  password: "Wrong password.",
  email: "Enter a valid email.",
  google: "Google sign-in didn't complete. Try again.",
  mailer: "Couldn't send the sign-in email right now.",
  link: "That sign-in link is invalid or expired. Request a new one.",
};

export default async function Login({ searchParams }: { searchParams: Promise<{ e?: string; sent?: string }> }) {
  const { e, sent } = await searchParams;
  const opts = authOptions();
  const demoNeedsPassword = Boolean(process.env.DASHBOARD_PASSWORD);
  return (
    <main className="login">
      <div className="box">
        <img src="/motherbrain.png" alt="Motherbrain" />
        <h1 style={{ margin: "16px 0 4px" }}>Motherbrain</h1>
        <p className="muted" style={{ marginTop: 0 }}>One brain. Every agent.</p>
        {e && <div className="notice warn">{ERR[e] || "Sign-in failed."}</div>}
        {sent && <div className="notice good">Check your inbox for a sign-in link (valid 15 minutes).</div>}

        {opts.google && (
          <a className="btn" href="/api/auth/google" style={{ width: "100%", justifyContent: "center", marginBottom: 8 }}>
            <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>
            Continue with Google
          </a>
        )}
        {opts.email && (
          <form method="post" action="/api/auth/email">
            <input name="email" type="email" placeholder="you@company.com" required autoComplete="email" />
            <button className="btn" style={{ width: "100%", justifyContent: "center", marginTop: 4 }}>Email me a sign-in link</button>
          </form>
        )}
        {(opts.google || opts.email) && (
          <p className="muted" style={{ fontSize: 12, margin: "14px 0 6px" }}>— or look around the shared demo brain —</p>
        )}
        <form method="post" action="/api/login">
          <input name="email" type="email" placeholder={opts.google || opts.email ? "any email (demo)" : "you@company.com"} required />
          {demoNeedsPassword && <input name="password" type="password" placeholder="Password" required autoComplete="current-password" />}
          <button className="btn primary" style={{ width: "100%", justifyContent: "center", marginTop: 8 }}>Enter demo</button>
        </form>
        <p className="muted" style={{ fontSize: 12 }}>Demo login shows the public judge brain. Your own brain needs Google or an email link.</p>
      </div>
    </main>
  );
}
