import { cookies } from "next/headers";
import Dashboard from "@/components/Dashboard";
import { getSnapshot, stripeConfigured } from "@/lib/data";
import { COOKIE, readSession } from "@/lib/session";

export const dynamic = "force-dynamic";

export default async function Home({ searchParams }: { searchParams: Promise<{ upgraded?: string; canceled?: string }> }) {
  const [{ data, live, error }, session, sp] = await Promise.all([
    getSnapshot(),
    cookies().then((c) => readSession(c.get(COOKIE)?.value)),
    searchParams,
  ]);
  return (
    <Dashboard
      initial={data}
      live={live}
      error={error}
      email={session?.email ?? ""}
      stripe={stripeConfigured()}
      flash={sp.upgraded ? "upgraded" : sp.canceled ? "canceled" : undefined}
    />
  );
}
