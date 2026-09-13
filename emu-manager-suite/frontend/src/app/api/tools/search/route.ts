import { NextRequest, NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q") ?? "";
  const res = await fetch(`${EMUMS_API_URL}/tools/search?q=${encodeURIComponent(q)}`, {
    headers: { "X-EMUMS-Key": EMUMS_API_KEY },
    cache: "no-store",
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
