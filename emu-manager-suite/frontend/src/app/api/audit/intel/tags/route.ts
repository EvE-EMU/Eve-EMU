import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  return emumsJsonResponse(await emumsAuthedBackendFetch("/audit/intel/tags", req));
}

export async function POST(req: NextRequest) {
  return emumsJsonResponse(
    await emumsAuthedBackendFetch("/audit/intel/tags", req, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: await req.text(),
    })
  );
}
