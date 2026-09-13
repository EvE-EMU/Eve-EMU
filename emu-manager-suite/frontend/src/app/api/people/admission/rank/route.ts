import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function GET(req: NextRequest) {
  return emumsJsonResponse(await emumsAuthedBackendFetch("/people/admission/rank", req));
}
