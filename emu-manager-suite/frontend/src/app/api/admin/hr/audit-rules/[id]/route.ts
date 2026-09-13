import { emumsBackendFetch, emumsJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string }> };

export async function PATCH(req: Request, { params }: Params) {
  const { id } = await params;
  const body = await req.text();
  return emumsJsonResponse(
    await emumsBackendFetch(`/admin/hr/audit-rules/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body,
    })
  );
}

export async function DELETE(_req: Request, { params }: Params) {
  const { id } = await params;
  return emumsJsonResponse(
    await emumsBackendFetch(`/admin/hr/audit-rules/${id}`, { method: "DELETE" })
  );
}
