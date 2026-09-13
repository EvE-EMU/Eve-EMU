import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsTextJsonResponse } from "@/lib/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = await req.text();
  const res = await emumsAuthedBackendFetch("/srp/submit", req, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
  return emumsTextJsonResponse(res);
}
