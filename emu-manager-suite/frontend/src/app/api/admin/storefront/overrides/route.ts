import { NextRequest } from "next/server";
import { emumsBackendFetch, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const res = await emumsBackendFetch("/admin/storefront/overrides");
  return emumsTextJsonResponse(res);
}

export async function POST(req: NextRequest) {
  const res = await emumsBackendFetch("/admin/storefront/overrides", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await req.text(),
  });
  return emumsTextJsonResponse(res);
}
