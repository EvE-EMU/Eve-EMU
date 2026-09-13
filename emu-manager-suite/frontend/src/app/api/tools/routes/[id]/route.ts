import { NextRequest, NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

export async function DELETE(req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const characterId = req.nextUrl.searchParams.get("character_id");
  const qs = characterId ? `?character_id=${encodeURIComponent(characterId)}` : "";
  const res = await fetch(`${EMUMS_API_URL}/tools/intelligence/routes/${id}${qs}`, {
    method: "DELETE",
    headers: { "X-EMUMS-Key": EMUMS_API_KEY },
    cache: "no-store",
  });
  return NextResponse.json(await res.json(), { status: res.status });
}
