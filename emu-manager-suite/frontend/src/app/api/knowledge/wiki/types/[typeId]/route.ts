import { emumsBackendFetch, emumsJsonResponse } from "@/lib/bff";

type Ctx = { params: Promise<{ typeId: string }> };

export async function GET(_req: Request, ctx: Ctx) {
  const { typeId } = await ctx.params;
  return emumsJsonResponse(await emumsBackendFetch(`/knowledge/wiki/types/${typeId}`));
}
