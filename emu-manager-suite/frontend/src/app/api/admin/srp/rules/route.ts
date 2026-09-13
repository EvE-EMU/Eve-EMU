import { NextRequest } from "next/server";
import { emumsBackendFetch, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const res = await emumsBackendFetch("/admin/srp/rules");
  return emumsTextJsonResponse(res);
}

export async function POST(req: NextRequest) {
  const body = await req.text();
  const res = await emumsBackendFetch("/admin/srp/rules", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
  return emumsTextJsonResponse(res);
}
