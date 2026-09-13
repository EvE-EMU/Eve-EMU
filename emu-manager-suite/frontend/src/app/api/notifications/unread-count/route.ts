import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const res = await emumsAuthedBackendFetch("/notifications/unread-count", req);
  return emumsTextJsonResponse(res);
}
