import { NextRequest, NextResponse } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const res = await emumsAuthedBackendFetch("/audit/roster/overview", req);
  return emumsTextJsonResponse(res);
}

export async function POST(req: NextRequest) {
  const res = await emumsAuthedBackendFetch("/audit/roster/sync", req, { method: "POST" });
  return emumsJsonResponse(res);
}
