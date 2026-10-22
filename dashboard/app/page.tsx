import { cookies } from "next/headers";
import Dashboard from "@/components/Dashboard";
import { getSnapshot, stripeConfigured } from "@/lib/data";
import { COOKIE, readSession } from "@/lib/session";

export const dynamic = "force-dynamic";

export default async function Home({ searchParams }: { searchParams: Promise<{ upgraded?: string; canceled?: string }> }) {
  const session = await cookies().then((c) => readSession(c.get(COOKIE)?.value));
  const [{ data, live, error, owner, ageSec }, sp] = await Promise.all([getSnapshot(session), searchParams]);
  const demoBrain = !owner;
  return (
    <Dashboard
      initial={data}
      live={live}
      owner={owner}
      ageSec={ageSec}
      error={error}
      email={session?.email ?? ""}
      verified={Boolean(session?.verified)}
      stripe={stripeConfigured()}
      flash={sp.upgraded ? "upgraded" : sp.canceled ? "canceled" : undefined}
      mcpUrl={demoBrain && live && process.env.MB_API_URL ? `${process.env.MB_API_URL.replace(/\/$/, "")}/mcp` : undefined}
      publicKey={demoBrain && live ? process.env.MB_PUBLIC_KEY : undefined}
    />
  );
}
