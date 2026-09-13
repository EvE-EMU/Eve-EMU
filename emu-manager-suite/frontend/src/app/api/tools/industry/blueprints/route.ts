import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function GET(req: NextRequest) {
  const res = await emumsAuthedBackendFetch("/tools/operations/blueprints", req);
  return emumsJsonResponse(res);
}
