import { NextRequest, NextResponse } from "next/server";
import { emumsAuthedBackendFetch, emumsTextJsonResponse } from "@/lib/bff";

export async function PATCH(req: NextRequest) {
  const payload = await req.text();
  const res = await emumsAuthedBackendFetch("/notifications/read", req, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: payload,
  });
  return emumsTextJsonResponse(res);
}
