import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function POST(req: NextRequest) {
  return emumsJsonResponse(
    await emumsAuthedBackendFetch("/people/onboarding/complete", req, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: await req.text(),
    })
  );
}
