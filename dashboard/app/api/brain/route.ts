import { NextResponse } from "next/server";
import { getSnapshot } from "@/lib/data";

export const dynamic = "force-dynamic";

export async function GET() {
  const { data, live, error } = await getSnapshot();
  return NextResponse.json({ data, live, error });
}
