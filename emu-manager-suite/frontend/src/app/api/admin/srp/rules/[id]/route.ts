import { NextRequest } from "next/server";
import { emumsBackendFetch, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ id: string }> };

export async function PATCH(req: NextRequest, ctx: Ctx) {
  const { id } = await ctx.params;
  const body = await req.text();
  const res = await emumsBackendFetch(`/admin/srp/rules/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body,
  });
  return emumsTextJsonResponse(res);
}

export async function DELETE(_req: NextRequest, ctx: Ctx) {
  const { id } = await ctx.params;
  const res = await emumsBackendFetch(`/admin/srp/rules/${id}`, { method: "DELETE" });
  return emumsTextJsonResponse(res);
}
