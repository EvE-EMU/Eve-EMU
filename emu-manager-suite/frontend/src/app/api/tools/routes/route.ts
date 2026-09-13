import { NextRequest, NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

export async function GET(req: NextRequest) {
  const characterId = req.nextUrl.searchParams.get("character_id");
  const qs = characterId ? `?character_id=${encodeURIComponent(characterId)}` : "";
  const res = await fetch(`${EMUMS_API_URL}/tools/intelligence/routes${qs}`, {
    headers: { "X-EMUMS-Key": EMUMS_API_KEY },
    cache: "no-store",
  });
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const res = await fetch(`${EMUMS_API_URL}/tools/intelligence/routes`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-EMUMS-Key": EMUMS_API_KEY },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  return NextResponse.json(await res.json(), { status: res.status });
}
