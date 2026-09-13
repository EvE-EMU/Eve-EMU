import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function POST(req: NextRequest) {
  const res = await emumsAuthedBackendFetch("/tools/operations/industry/sync", req, {
    method: "POST",
  });
  return emumsJsonResponse(res);
}
