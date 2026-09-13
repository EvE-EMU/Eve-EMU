import { NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

export async function GET() {
  const res = await fetch(`${EMUMS_API_URL}/tools/commerce/buyback/locations`, {
    headers: { "X-EMUMS-Key": EMUMS_API_KEY },
    cache: "no-store",
  });
  return NextResponse.json(await res.json(), { status: res.status });
}
