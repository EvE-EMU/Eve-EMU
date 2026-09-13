import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const res = await emumsAuthedBackendFetch("/audit/roster/pi/sync", req, { method: "POST" });
  return emumsTextJsonResponse(res);
}
