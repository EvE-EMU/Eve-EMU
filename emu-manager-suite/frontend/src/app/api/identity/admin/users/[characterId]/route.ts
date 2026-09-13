import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function GET(req: NextRequest, ctx: { params: Promise<{ characterId: string }> }) {
  const { characterId } = await ctx.params;
  return emumsJsonResponse(await emumsAuthedBackendFetch(`/identity/admin/users/${characterId}`, req));
}
