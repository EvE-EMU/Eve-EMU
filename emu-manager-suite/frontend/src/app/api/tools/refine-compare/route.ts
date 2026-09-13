import { NextRequest, NextResponse } from "next/server";

const EMUMS_API_URL = process.env.EMUMS_API_URL || "http://emums-api:8020";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const res = await fetch(`${EMUMS_API_URL}/tools/commerce/refine-compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
