import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

type Ctx = { params: Promise<{ characterId: string }> };

export async function GET(req: Request, ctx: Ctx) {
  const { characterId } = await ctx.params;
  return emumsJsonResponse(await emumsAuthedBackendFetch(`/audit/characters/${characterId}`, req));
}
