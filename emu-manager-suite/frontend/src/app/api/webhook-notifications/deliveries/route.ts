import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const qs = req.nextUrl.searchParams.toString();
  const path = qs ? `/webhook-notifications/deliveries?${qs}` : "/webhook-notifications/deliveries";
  const res = await emumsAuthedBackendFetch(path, req);
  return emumsTextJsonResponse(res);
}
