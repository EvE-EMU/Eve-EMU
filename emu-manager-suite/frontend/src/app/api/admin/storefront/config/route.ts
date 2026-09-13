import { emumsBackendFetch, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const res = await emumsBackendFetch("/admin/storefront/config");
  return emumsTextJsonResponse(res);
}

export async function PATCH(req: Request) {
  const res = await emumsBackendFetch("/admin/storefront/config", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: await req.text(),
  });
  return emumsTextJsonResponse(res);
}
