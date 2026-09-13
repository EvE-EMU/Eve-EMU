import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const qs = req.nextUrl.searchParams.toString();
  const path = qs ? `/audit/roster/spy-meter?${qs}` : "/audit/roster/spy-meter";
  return emumsTextJsonResponse(await emumsAuthedBackendFetch(path, req));
}
