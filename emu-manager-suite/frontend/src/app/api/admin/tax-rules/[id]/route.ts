import { emumsBackendFetch, emumsJsonResponse } from "@/lib/bff";

type Ctx = { params: Promise<{ id: string }> };

export async function PATCH(req: Request, ctx: Ctx) {
  const { id } = await ctx.params;
  const body = await req.text();
  return emumsJsonResponse(
    await emumsBackendFetch(`/admin/tax-rules/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body,
    })
  );
}
