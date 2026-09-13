import { NextRequest, NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q") || "";
  const limit = req.nextUrl.searchParams.get("limit") || "40";
  const res = await fetch(
    `${EMUMS_API_URL}/tools/intelligence/sde/systems?q=${encodeURIComponent(q)}&limit=${encodeURIComponent(limit)}`,
    { headers: { "X-EMUMS-Key": EMUMS_API_KEY }, cache: "no-store" }
  );
  const data = await res.text();
  return new NextResponse(data, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
