import { NextRequest, NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const res = await fetch(`${EMUMS_API_URL}/tools/administration/hr/leaves`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-EMUMS-Key": EMUMS_API_KEY,
    },
    body: JSON.stringify(body),
  });
  const data = await res.text();
  return new NextResponse(data, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
