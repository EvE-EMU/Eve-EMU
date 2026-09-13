import { NextRequest, NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

function apiHeaders(): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-EMUMS-Key": EMUMS_API_KEY,
  };
}

export async function GET(req: NextRequest) {
  const all = req.nextUrl.searchParams.get("all");
  const path =
    all === "1"
      ? `${EMUMS_API_URL}/ui/desktop-backgrounds`
      : `${EMUMS_API_URL}/ui/desktop-backgrounds?active_only=true`;

  const res = await fetch(path, {
    headers: all === "1" ? apiHeaders() : { "Content-Type": "application/json" },
    cache: "no-store",
  });

  const body = await res.text();
  return new NextResponse(body, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}

export async function POST(req: NextRequest) {
  const payload = await req.text();
  const res = await fetch(`${EMUMS_API_URL}/ui/desktop-backgrounds`, {
    method: "POST",
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
