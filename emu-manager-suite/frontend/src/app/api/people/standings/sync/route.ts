import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function POST(req: NextRequest) {
  return emumsJsonResponse(
    await emumsAuthedBackendFetch("/people/standings/sync", req, { method: "POST" })
  );
}
