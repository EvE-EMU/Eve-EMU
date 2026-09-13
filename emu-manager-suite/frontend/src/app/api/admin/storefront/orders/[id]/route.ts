import { NextRequest } from "next/server";
import { emumsBackendFetch, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function PATCH(req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const res = await emumsBackendFetch(`/admin/storefront/orders/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: await req.text(),
  });
  return emumsTextJsonResponse(res);
}
