import { NextRequest } from "next/server";
import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function GET(req: NextRequest) {
  const qs = new URL(req.url).searchParams.toString();
  return emumsJsonResponse(
    await emumsAuthedBackendFetch(`/people/calendar${qs ? `?${qs}` : ""}`, req)
  );
}
