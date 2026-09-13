import { emumsBackendFetch, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ characterId: string }> };

export async function GET(_req: Request, ctx: Ctx) {
  const { characterId } = await ctx.params;
  const res = await emumsBackendFetch(
    `/tools/intelligence/killboard/pilot/${encodeURIComponent(characterId)}?scope=alliance`
  );
  return emumsTextJsonResponse(res);
}
