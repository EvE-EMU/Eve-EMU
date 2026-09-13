import { NextResponse } from "next/server";
import { EMUMS_API_URL, EMUMS_API_KEY } from "@/lib/bff";

export async function GET(_req: Request, ctx: { params: Promise<{ token: string }> }) {
  const { token } = await ctx.params;
  const res = await fetch(
    `${EMUMS_API_URL}/tools/commerce/buyback/${encodeURIComponent(token)}`,
    {
      headers: { "X-EMUMS-Key": EMUMS_API_KEY },
      cache: "no-store",
    }
  );
  return NextResponse.json(await res.json(), { status: res.status });
}
