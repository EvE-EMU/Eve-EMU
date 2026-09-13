import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const res = await emumsAuthedBackendFetch("/audit/roster/rebuild-interactions", req, {
    method: "POST",
  });
  return emumsJsonResponse(res);
}
