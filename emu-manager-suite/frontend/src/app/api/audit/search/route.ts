import { NextRequest, NextResponse } from "next/server";
import { emumsAuthedBackendFetch, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.toString();
  const path = q ? `/audit/search?${q}` : "/audit/search";
  const res = await emumsAuthedBackendFetch(path, req);
  return emumsTextJsonResponse(res);
}
