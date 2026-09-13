import { emumsBackendFetch, emumsJsonResponse } from "@/lib/bff";

type Ctx = { params: Promise<{ mapId: string }> };

export async function GET(_req: Request, ctx: Ctx) {
  const { mapId } = await ctx.params;
  return emumsJsonResponse(await emumsBackendFetch(`/map/wh/maps/${mapId}`));
}

export async function POST(req: Request, ctx: Ctx) {
  const { mapId } = await ctx.params;
  const path = req.url.includes("/systems")
    ? `/map/wh/maps/${mapId}/systems`
    : `/map/wh/maps/${mapId}/connections`;
  const body = await req.text();
  return emumsJsonResponse(
    await emumsBackendFetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    })
  );
}
