import { emumsAuthedBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function GET(req: Request) {
  const q = new URL(req.url).searchParams.get("q") ?? "";
  return emumsJsonResponse(
    await emumsAuthedBackendFetch(`/audit/assets/search?q=${encodeURIComponent(q)}`, req)
  );
}
