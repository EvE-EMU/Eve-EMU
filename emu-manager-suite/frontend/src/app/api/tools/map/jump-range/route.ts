import { NextRequest, NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const res = await fetch(`${EMUMS_API_URL}/tools/intelligence/map/jump-range`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-EMUMS-Key": EMUMS_API_KEY },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
