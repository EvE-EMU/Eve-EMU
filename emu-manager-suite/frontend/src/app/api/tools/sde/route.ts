import { NextRequest, NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q") || "";
  const category = req.nextUrl.searchParams.get("category") || "";
  const group = req.nextUrl.searchParams.get("group") || "";
  const limit = req.nextUrl.searchParams.get("limit") || "200";
  const params = new URLSearchParams({ q, limit });
  if (category) params.set("category", category);
  if (group) params.set("group", group);
  const res = await fetch(`${EMUMS_API_URL}/tools/intelligence/sde/search?${params}`, {
    headers: { "X-EMUMS-Key": EMUMS_API_KEY },
    cache: "no-store",
  });
  const data = await res.text();
  return new NextResponse(data, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
