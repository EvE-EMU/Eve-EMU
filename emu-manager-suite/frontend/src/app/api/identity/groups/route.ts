import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function GET() {
  return emumsJsonResponse(await emumsBackendFetch("/identity/groups"));
}

export async function POST(req: NextRequest) {
  return emumsJsonResponse(
    await emumsAuthedBackendFetch("/identity/groups", req, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: await req.text(),
    })
  );
}

