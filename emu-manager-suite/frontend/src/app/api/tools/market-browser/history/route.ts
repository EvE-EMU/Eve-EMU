import { NextRequest, NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.toString();
  const res = await fetch(`${EMUMS_API_URL}/tools/commerce/market-browser/history?${q}`, {
    headers: { "X-EMUMS-Key": EMUMS_API_KEY },
    cache: "no-store",
  });
  const data = await res.text();
  return new NextResponse(data, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
