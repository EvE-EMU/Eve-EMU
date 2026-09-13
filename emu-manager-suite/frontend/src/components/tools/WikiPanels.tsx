"use client";

import { useCallback, useEffect, useState } from "react";
import { SectionHead, StatusStrip } from "@/components/ui";
import type { KnowledgeSearchResult, KnowledgeScope, WikiArticle, WikiCategoryFilter } from "@/lib/knowledge";
import { fetchWikiPage } from "@/lib/knowledge";

const WIKI_CATEGORY_LABELS: Record<WikiCategoryFilter, string> = {
  all: "All wiki",
  guides: "Guides",
  types: "SDE Types",
  corporations: "Corporations",
  alliances: "Alliances",
  sde: "SDE other",
};

export function KnowledgeSearchResults({
  results,
  scope,
  loading,
  onSelectWiki,
  onSelectType,
}: {
  results: KnowledgeSearchResult | null;
  scope: KnowledgeScope;
  loading?: boolean;
  onSelectWiki: (title: string, label?: string) => void;
  onSelectType: (typeId: number, name?: string) => void;
}) {
  const showWiki = scope === "all" || scope === "wiki";
  const showSde = scope === "all" || scope === "sde";

  if (loading) {
    return <StatusStrip>Searching knowledge base…</StatusStrip>;
  }

  if (!results?.query.trim()) {
    return (
      <p className="text-[var(--text-muted)] text-[11px]">
        Enter a search term to find wiki guides and SDE records.
      </p>
    );
  }

  const wikiHits = results.wiki ?? [];
  const sdeHits = results.sde ?? [];

  return (
    <div className="overflow-auto flex-1 min-h-0 space-y-3">
      {showWiki ? (
        <section>
          <SectionHead>Wiki articles</SectionHead>
          {wikiHits.length ? (
            <ul className="space-y-1 text-[10px]">
              {wikiHits.map((hit) => (
                <li key={hit.title}>
                  <button
                    type="button"
                    className="eve-wiki-result-link"
                    onClick={() => {
                      if (hit.type_id) {
                        onSelectType(hit.type_id, hit.title.split("/").pop());
                      }
                      onSelectWiki(hit.title, hit.title.split("/").pop());
                    }}
                  >
                    {hit.title.replace(/^SDE\//, "")}
                  </button>
                  <span className="text-[var(--text-muted)] ml-1">
                    {WIKI_CATEGORY_LABELS[(hit.category as WikiCategoryFilter) ?? "guides"] ?? hit.category}
                  </span>
                  {hit.snippet ? <p className="text-[var(--text-muted)] ml-1">{hit.snippet}</p> : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[var(--text-muted)] text-[10px]">No wiki matches.</p>
          )}
        </section>
      ) : null}
      {showSde ? (
        <section>
          <SectionHead>SDE types</SectionHead>
          {sdeHits.length ? (
            <table className="eve-table text-[10px]">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Group</th>
                  <th>ID</th>
                </tr>
              </thead>
              <tbody>
                {sdeHits.map((row) => (
                  <tr
                    key={row.type_id}
                    className="cursor-pointer hover:bg-[var(--panel-elevated)]"
                    onClick={() => onSelectType(row.type_id, row.name)}
                  >
                    <td>{row.name}</td>
                    <td className="text-[var(--text-muted)]">{row.group_name}</td>
                    <td>{row.type_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-[var(--text-muted)] text-[10px]">No SDE matches.</p>
          )}
        </section>
      ) : null}
    </div>
  );
}

export function WikiArticleContent({
  article,
  loading,
  error,
  onOpenWiki,
  onOpenType,
}: {
  article: WikiArticle | null;
  loading?: boolean;
  error?: string;
  onOpenWiki?: (title: string) => void;
  onOpenType?: (typeId: number) => void;
}) {
  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const target = (e.target as HTMLElement).closest("[data-type-id],[data-wiki-title]") as HTMLElement | null;
      if (!target) return;
      e.preventDefault();
      const typeId = target.getAttribute("data-type-id");
      const wikiTitle = target.getAttribute("data-wiki-title");
      if (typeId && onOpenType) {
        onOpenType(Number(typeId));
        return;
      }
      if (wikiTitle && onOpenWiki) {
        onOpenWiki(wikiTitle);
      }
    },
    [onOpenType, onOpenWiki]
  );

  if (loading) {
    return <StatusStrip>Loading wiki article…</StatusStrip>;
  }
  if (error) {
    return <p className="text-[var(--danger)] text-[11px]">{error}</p>;
  }
  if (!article?.found) {
    return (
      <p className="text-[var(--text-muted)] text-[11px]">
        No wiki article found for this topic.
        {article?.external_url ? (
          <>
            {" "}
            <a href={article.external_url} className="text-[var(--link)]" target="_blank" rel="noreferrer">
              Open on wiki
            </a>
          </>
        ) : null}
      </p>
    );
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      <SectionHead>{article.display_title || article.title}</SectionHead>
      <div
        className="eve-wiki-content eve-sde-detail-body flex-1 overflow-auto min-h-0"
        onClick={handleClick}
        dangerouslySetInnerHTML={{ __html: article.html }}
      />
      {article.external_url ? (
        <div className="mt-2 pt-2 border-t border-[var(--border)]">
          <a href={article.external_url} className="eve-btn-sm text-[var(--link)]" target="_blank" rel="noreferrer">
            Open full article on wiki
          </a>
        </div>
      ) : null}
    </div>
  );
}

export function WikiArticlePanel({
  title,
  onOpenWiki,
  onOpenType,
}: {
  title: string | null;
  onOpenWiki?: (title: string) => void;
  onOpenType?: (typeId: number) => void;
}) {
  const [article, setArticle] = useState<WikiArticle | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!title) {
      setArticle(null);
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    fetchWikiPage(title)
      .then(setArticle)
      .catch(() => {
        setArticle(null);
        setError("Failed to load wiki article.");
      })
      .finally(() => setLoading(false));
  }, [title]);

  if (!title) {
    return (
      <>
        <SectionHead>Wiki article</SectionHead>
        <p className="text-[var(--text-muted)] text-[11px]">
          Search the coalition wiki or select a type to view operational notes and SDE-linked guides.
        </p>
      </>
    );
  }

  return (
    <WikiArticleContent
      article={article}
      loading={loading}
      error={error}
      onOpenWiki={onOpenWiki}
      onOpenType={onOpenType}
    />
  );
}
