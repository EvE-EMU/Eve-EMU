import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const q = url.searchParams.toString();
  const path = q ? `/srp/preview?${q}` : "/srp/preview";
  const res = await emumsAuthedBackendFetch(path, req);
  return emumsTextJsonResponse(res);
}
