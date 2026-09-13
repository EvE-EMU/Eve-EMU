import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string }> };

export async function PATCH(req: NextRequest, { params }: Params) {
  const { id } = await params;
  const body = await req.text();
  const res = await emumsAuthedBackendFetch(`/webhook-notifications/rules/${id}`, req, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body,
  });
  return emumsJsonResponse(res);
}

export async function DELETE(req: NextRequest, { params }: Params) {
  const { id } = await params;
  const res = await emumsAuthedBackendFetch(`/webhook-notifications/rules/${id}`, req, {
    method: "DELETE",
  });
  return emumsJsonResponse(res);
}
