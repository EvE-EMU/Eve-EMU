import { emumsBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function GET() {
  return emumsJsonResponse(await emumsBackendFetch("/identity/states"));
}
