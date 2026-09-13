import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function GET(req: NextRequest) {
  const res = await emumsAuthedBackendFetch("/tools/suite/structure-board", req);
  return emumsJsonResponse(res);
}
