import { emumsBackendFetch, emumsJsonResponse } from "@/lib/bff";

type Ctx = { params: Promise<{ mapId: string }> };

export async function POST(req: Request, ctx: Ctx) {
  const { mapId } = await ctx.params;
  const body = await req.text();
  return emumsJsonResponse(
    await emumsBackendFetch(`/map/wh/maps/${mapId}/connections`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    })
  );
}
