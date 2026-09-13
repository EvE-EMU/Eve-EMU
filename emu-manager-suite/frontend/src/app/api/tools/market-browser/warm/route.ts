import { NextRequest, NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

export async function POST(req: NextRequest) {
  const q = req.nextUrl.searchParams.toString();
  const res = await fetch(`${EMUMS_API_URL}/tools/commerce/market-browser/warm?${q}`, {
    method: "POST",
    headers: { "X-API-Key": EMUMS_API_KEY },
    cache: "no-store",
  });
  const body = await res.text();
  return new NextResponse(body, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}
