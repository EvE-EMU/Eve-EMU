import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

type Ctx = { params: Promise<{ characterId: string }> };

export async function POST(req: Request, ctx: Ctx) {
  const { characterId } = await ctx.params;
  return emumsJsonResponse(
    await emumsAuthedBackendFetch(`/audit/sync/${characterId}`, req, { method: "POST" })
  );
}
