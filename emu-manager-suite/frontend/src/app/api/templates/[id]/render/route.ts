import { NextRequest, NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

type RouteContext = { params: Promise<{ id: string }> };

export async function POST(req: NextRequest, context: RouteContext) {
  const { id } = await context.params;
  const payload = await req.text();
  const res = await fetch(`${EMUMS_API_URL}/templates/${id}/render`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-EMUMS-Key": EMUMS_API_KEY,
    },
    body: payload,
    cache: "no-store",
  });

  const body = await res.text();
  return new NextResponse(body, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
