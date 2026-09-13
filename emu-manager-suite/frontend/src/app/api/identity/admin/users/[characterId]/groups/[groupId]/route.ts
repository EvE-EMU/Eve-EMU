import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function POST(req: NextRequest, ctx: { params: Promise<{ characterId: string; groupId: string }> }) {
  const { characterId, groupId } = await ctx.params;
  return emumsJsonResponse(
    await emumsAuthedBackendFetch(`/identity/admin/users/${characterId}/groups/${groupId}`, req, { method: "POST" })
  );
}

export async function DELETE(req: NextRequest, ctx: { params: Promise<{ characterId: string; groupId: string }> }) {
  const { characterId, groupId } = await ctx.params;
  return emumsJsonResponse(
    await emumsAuthedBackendFetch(`/identity/admin/users/${characterId}/groups/${groupId}`, req, { method: "DELETE" })
  );
}
