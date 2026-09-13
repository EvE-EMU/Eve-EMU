import { NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

export async function GET() {
  const res = await fetch(`${EMUMS_API_URL}/tools/intelligence/map/atlas`, {
    headers: { "X-EMUMS-Key": EMUMS_API_KEY },
    next: { revalidate: 3600 },
  });
  const body = await res.text();
    return new NextResponse(body, {
    status: res.status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "public, max-age=300, stale-while-revalidate=600",
    },
  });
}
