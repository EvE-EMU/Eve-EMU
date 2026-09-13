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
  const res = await fetch(`${EMUMS_API_URL}/ui/desktop-backgrounds/${id}`, {
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

export async function DELETE(_req: NextRequest, context: RouteContext) {
  const { id } = await context.params;
  const res = await fetch(`${EMUMS_API_URL}/ui/desktop-backgrounds/${id}`, {
    method: "DELETE",
    headers: apiHeaders(),
    cache: "no-store",
  });

  if (res.status === 204) {
    return new NextResponse(null, { status: 204 });
  }

  const body = await res.text();
  return new NextResponse(body, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
