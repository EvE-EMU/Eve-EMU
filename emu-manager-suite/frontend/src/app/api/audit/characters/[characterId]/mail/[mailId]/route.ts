import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

type Ctx = { params: Promise<{ characterId: string; mailId: string }> };

export async function GET(req: Request, ctx: Ctx) {
  const { characterId, mailId } = await ctx.params;
  return emumsJsonResponse(
    await emumsAuthedBackendFetch(`/audit/characters/${characterId}/mail/${mailId}`, req)
  );
}
