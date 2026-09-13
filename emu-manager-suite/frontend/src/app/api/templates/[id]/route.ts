import { NextRequest, NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

function apiHeaders(): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-EMUMS-Key": EMUMS_API_KEY,
  };
}

type RouteContext = { params: Promise<{ id: string }> };

export async function PATCH(req: NextRequest, context: RouteContext) {
  const { id } = await context.params;
  const payload = await req.text();
  const res = await fetch(`${EMUMS_API_URL}/templates/${id}`, {
    method: "PATCH",
    headers: apiHeaders(),
    body: payload,
    cache: "no-store",
  });

  const body = await res.text();
  return new NextResponse(body, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
