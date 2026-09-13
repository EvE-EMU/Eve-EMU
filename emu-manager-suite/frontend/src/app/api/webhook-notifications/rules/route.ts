import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const res = await emumsAuthedBackendFetch("/webhook-notifications/rules", req);
  return emumsTextJsonResponse(res);
}

export async function POST(req: NextRequest) {
  const body = await req.text();
  const res = await emumsAuthedBackendFetch("/webhook-notifications/rules", req, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
  return emumsJsonResponse(res);
}
