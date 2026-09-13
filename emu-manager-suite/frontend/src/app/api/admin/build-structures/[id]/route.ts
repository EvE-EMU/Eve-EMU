import { NextRequest } from "next/server";
import { emumsBackendFetch, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function PATCH(req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const res = await emumsBackendFetch(`/admin/build-structures/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: await req.text(),
  });
  return emumsTextJsonResponse(res);
}

export async function DELETE(_req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const res = await emumsBackendFetch(`/admin/build-structures/${id}`, { method: "DELETE" });
  return emumsTextJsonResponse(res);
}
