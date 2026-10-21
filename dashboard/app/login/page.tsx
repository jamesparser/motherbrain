export default async function Login({ searchParams }: { searchParams: Promise<{ e?: string }> }) {
  const { e } = await searchParams;
  const demo = !process.env.DASHBOARD_PASSWORD;
  return (
    <main className="login">
      <form className="box" method="post" action="/api/login">
        <img src="/motherbrain.png" alt="Motherbrain" />
        <h1 style={{ margin: "16px 0 4px" }}>Motherbrain</h1>
        <p className="muted" style={{ marginTop: 0 }}>One brain. Every agent.</p>
        {e && <div className="notice warn">{e === "password" ? "Wrong password." : "Enter a valid email."}</div>}
        <input name="email" type="email" placeholder="you@company.com" required autoComplete="email" />
        {!demo && <input name="password" type="password" placeholder="Password" required autoComplete="current-password" />}
        <button className="btn primary" style={{ width: "100%", justifyContent: "center", marginTop: 8 }}>
          {demo ? "Enter demo" : "Log in"}
        </button>
        {demo && <p className="muted" style={{ fontSize: 12 }}>Demo mode: no password set on this deployment.</p>}
      </form>
    </main>
  );
}
