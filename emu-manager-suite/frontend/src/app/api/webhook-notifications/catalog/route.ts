import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const res = await emumsAuthedBackendFetch("/webhook-notifications/catalog", req);
  return emumsTextJsonResponse(res);
}
