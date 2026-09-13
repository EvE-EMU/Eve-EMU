import { NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

export async function GET() {
  const res = await fetch(`${EMUMS_API_URL}/tools/intelligence/sde/categories`, {
    headers: { "X-EMUMS-Key": EMUMS_API_KEY },
    next: { revalidate: 3600 },
  });
  const data = await res.text();
  return new NextResponse(data, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
