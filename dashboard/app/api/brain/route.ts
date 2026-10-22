import { NextRequest, NextResponse } from "next/server";
import { getSnapshot } from "@/lib/data";
import { COOKIE, readSession } from "@/lib/session";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const s = await readSession(req.cookies.get(COOKIE)?.value);
  return NextResponse.json(await getSnapshot(s));
}
