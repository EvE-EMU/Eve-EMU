/** Client helpers for unified Knowledge & SDE integration. */

export type WikiArticle = {
  found: boolean;
  title: string;
  display_title?: string;
  pageid?: number;
  html: string;
  type_id?: number | null;
  links?: { title: string; type_id?: number | null }[];
  sections?: { level: string; line: string; anchor: string }[];
  external_url?: string;
};

export type KnowledgeSearchHit = {
  title: string;
  pageid: number;
  snippet: string;
  type_id?: number | null;
  category?: string;
  external_url: string;
};

export type KnowledgeScope = "all" | "sde" | "wiki";
export type WikiCategoryFilter = "all" | "guides" | "types" | "corporations" | "alliances" | "sde";

export type KnowledgeSearchResult = {
  query: string;
  scope?: KnowledgeScope;
  wiki_category?: WikiCategoryFilter;
  sde: import("@/lib/api").SdeType[];
  wiki: KnowledgeSearchHit[];
};

export async function searchKnowledge(
  q: string,
  limit = 20,
  scope: KnowledgeScope = "all",
  wikiCategory: WikiCategoryFilter = "all"
): Promise<KnowledgeSearchResult> {
  const params = new URLSearchParams({
    q,
    limit: String(limit),
    scope,
    wiki_category: wikiCategory,
  });
  const res = await fetch(`/api/knowledge/search?${params}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Knowledge search failed");
  return res.json();
}

export async function fetchWikiPage(title: string): Promise<WikiArticle> {
  const res = await fetch(`/api/knowledge/wiki/page?title=${encodeURIComponent(title)}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Wiki page not found");
  return res.json();
}

export async function fetchWikiForType(typeId: number): Promise<WikiArticle> {
  const res = await fetch(`/api/knowledge/wiki/types/${typeId}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Wiki article unavailable");
  return res.json();
}
