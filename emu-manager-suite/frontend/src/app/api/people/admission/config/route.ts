import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function GET(req: NextRequest) {
  return emumsJsonResponse(await emumsAuthedBackendFetch("/people/admission/config", req));
}

export async function PATCH(req: NextRequest) {
  return emumsJsonResponse(
    await emumsAuthedBackendFetch("/people/admission/config", req, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: await req.text(),
    })
  );
}
