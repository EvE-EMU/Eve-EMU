import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function GET() {
  return emumsJsonResponse(await emumsBackendFetch("/identity/service-sync/config"));
}

export async function PATCH(req: NextRequest) {
  return emumsJsonResponse(
    await emumsAuthedBackendFetch("/identity/service-sync/config", req, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: await req.text(),
    })
  );
}

