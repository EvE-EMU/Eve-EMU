import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function DELETE(
  req: NextRequest,
  ctx: { params: Promise<{ tagId: string }> }
) {
  const { tagId } = await ctx.params;
  return emumsJsonResponse(
    await emumsAuthedBackendFetch(`/audit/intel/tags/${tagId}`, req, { method: "DELETE" })
  );
}
