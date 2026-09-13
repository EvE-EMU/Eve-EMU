import { emumsBackendFetch, emumsJsonResponse } from "@/lib/bff";

type Ctx = { params: Promise<{ connectionId: string }> };

export async function PATCH(req: Request, ctx: Ctx) {
  const { connectionId } = await ctx.params;
  const body = await req.text();
  return emumsJsonResponse(
    await emumsBackendFetch(`/map/wh/connections/${connectionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body,
    })
  );
}
