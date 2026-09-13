import { emumsBackendFetch, emumsJsonResponse } from "@/lib/bff";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const q = url.searchParams.get("q") ?? "";
  const limit = url.searchParams.get("limit") ?? "20";
  const scope = url.searchParams.get("scope") ?? "all";
  const wikiCategory = url.searchParams.get("wiki_category") ?? "all";
  const params = new URLSearchParams({
    q,
    limit,
    scope,
    wiki_category: wikiCategory,
  });
  return emumsJsonResponse(await emumsBackendFetch(`/knowledge/search?${params}`));
}
