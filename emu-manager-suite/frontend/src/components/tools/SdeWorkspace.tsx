"use client";

import { useCallback, useEffect, useState } from "react";
import { EveWindow } from "@/components/ui";
import { DesktopSurface, useWindowManager } from "@/components/WindowManager";
import { StatusStrip } from "@/components/ui";
import { SdeSearchPanel, type CharacterSkillsPayload, type SkillFilter } from "./SdeSearchPanel";
import { SdeItemDetailPanel } from "./SdeItemDetailPanel";
import { SdeComparePanel } from "./SdeComparePanel";
import { KnowledgeSearchResults, WikiArticlePanel } from "./WikiPanels";
import type { KnowledgeScope, KnowledgeSearchResult, WikiCategoryFilter } from "@/lib/knowledge";
import { searchKnowledge } from "@/lib/knowledge";

const SCOPE_OPTIONS: { id: KnowledgeScope; label: string }[] = [
  { id: "all", label: "All" },
  { id: "sde", label: "SDE" },
  { id: "wiki", label: "Wiki" },
];

const WIKI_CATEGORY_OPTIONS: { id: WikiCategoryFilter; label: string }[] = [
  { id: "all", label: "All wiki" },
  { id: "guides", label: "Guides" },
  { id: "types", label: "SDE Types" },
  { id: "corporations", label: "Corporations" },
  { id: "alliances", label: "Alliances" },
  { id: "sde", label: "SDE other" },
];

export function SdeWorkspace({
  initialTypes,
  categories: initialCategories,
  embedded,
}: {
  initialTypes: import("@/lib/api").SdeType[];
  categories: string[];
  embedded?: boolean;
}) {
  const { openWindow, focusWindow } = useWindowManager();
  const [selectedTypeId, setSelectedTypeId] = useState<number | null>(null);
  const [selectedName, setSelectedName] = useState<string>("Type Inspector");
  const [types, setTypes] = useState(initialTypes);
  const [cat, setCat] = useState("All");
  const [skillFilter, setSkillFilter] = useState<SkillFilter>("all");
  const [compareIds, setCompareIds] = useState<number[]>([]);
  const [compareTitle, setCompareTitle] = useState("Compare");
  const [charSkills, setCharSkills] = useState<CharacterSkillsPayload | null>(null);
  const [wikiTitle, setWikiTitle] = useState<string | null>(null);
  const [wikiWindowTitle, setWikiWindowTitle] = useState("Wiki article");
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState<KnowledgeScope>("sde");
  const [wikiCategory, setWikiCategory] = useState<WikiCategoryFilter>("all");
  const [knowledgeResults, setKnowledgeResults] = useState<KnowledgeSearchResult | null>(null);
  const [knowledgeLoading, setKnowledgeLoading] = useState(false);
  const categories = ["All", ...initialCategories];

  const knowledgeMode = query.trim().length > 0 || scope === "wiki";
  const showSdeBrowse = !knowledgeMode && (scope === "all" || scope === "sde");
  const showWikiCategories = scope === "all" || scope === "wiki";

  useEffect(() => {
    fetch("/api/tools/sde/character-skills", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setCharSkills(data))
      .catch(() => setCharSkills(null));
  }, []);

  const loadCategory = useCallback(async (category: string) => {
    const params = new URLSearchParams({ q: "", limit: "500" });
    if (category !== "All") params.set("category", category);
    const data = await (await fetch(`/api/tools/sde?${params}`)).json();
    setTypes(data);
  }, []);

  useEffect(() => {
    void loadCategory(cat);
  }, [cat, loadCategory]);

  useEffect(() => {
    if (!query.trim()) {
      setKnowledgeResults(null);
      return;
    }
    const handle = setTimeout(() => {
      setKnowledgeLoading(true);
      searchKnowledge(query, 24, scope, wikiCategory)
        .then(setKnowledgeResults)
        .catch(() => setKnowledgeResults({ query, sde: [], wiki: [] }))
        .finally(() => setKnowledgeLoading(false));
    }, 220);
    return () => clearTimeout(handle);
  }, [query, scope, wikiCategory]);

  const selectType = useCallback(
    (row: import("@/lib/api").SdeType) => {
      setSelectedTypeId(row.type_id);
      setSelectedName(row.name);
      openWindow("sde-detail");
      focusWindow("sde-detail");
    },
    [openWindow, focusWindow]
  );

  const selectTypeById = useCallback(
    (typeId: number) => {
      setSelectedTypeId(typeId);
      openWindow("sde-detail");
      focusWindow("sde-detail");
      fetch(`/api/tools/sde/types/${typeId}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data?.name) setSelectedName(data.name);
        })
        .catch(() => undefined);
    },
    [openWindow, focusWindow]
  );

  const toggleCompare = useCallback((typeId: number) => {
    setCompareIds((prev) => {
      if (prev.includes(typeId)) return prev.filter((id) => id !== typeId);
      if (prev.length >= 8) return prev;
      return [...prev, typeId];
    });
  }, []);

  const openCompare = useCallback(
    (title: string, ids: number[]) => {
      setCompareIds(ids);
      setCompareTitle(title);
      openWindow("sde-compare");
      focusWindow("sde-compare");
    },
    [openWindow, focusWindow]
  );

  const handleCompareGroup = useCallback(
    (groupName: string, typeIds: number[]) => {
      openCompare(`Compare — ${groupName}`, typeIds);
    },
    [openCompare]
  );

  const openWiki = useCallback(
    (title: string, label?: string) => {
      setWikiTitle(title);
      setWikiWindowTitle(label || title.replace(/^SDE\//, ""));
      openWindow("wiki-article");
      focusWindow("wiki-article");
    },
    [openWindow, focusWindow]
  );

  const openWikiForType = useCallback(
    (typeId: number, name?: string) => {
      void selectTypeById(typeId);
      openWiki(`SDE/Types/${typeId}`, name || `Type ${typeId}`);
    },
    [openWiki, selectTypeById]
  );

  const charCount = charSkills?.characters?.length ?? 0;

  return (
    <DesktopSurface embedded={embedded} className="min-h-0 flex-1">
      <EveWindow id="sde-browser" title="Knowledge & SDE browser" defaultX={24} defaultY={24} defaultWidth={720} defaultHeight={520}>
        <StatusStrip>
          Unified knowledge engine — SDE types and coalition wiki in one place
          {charCount ? ` (${charCount} character${charCount === 1 ? "" : "s"} linked)` : ""}
        </StatusStrip>
        <div className="flex gap-2 mb-2">
          <input
            className="eve-input flex-1"
            placeholder="Search SDE types, wiki guides, corps, alliances…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap gap-1 mb-2 items-center">
          <span className="text-[10px] text-[var(--text-muted)] mr-1">Source</span>
          {SCOPE_OPTIONS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              className={`eve-btn text-[10px] ${scope === id ? "eve-btn-primary" : ""}`}
              onClick={() => setScope(id)}
            >
              {label}
            </button>
          ))}
        </div>
        {showWikiCategories ? (
          <div className="flex flex-wrap gap-1 mb-2 items-center">
            <span className="text-[10px] text-[var(--text-muted)] mr-1">Wiki</span>
            {WIKI_CATEGORY_OPTIONS.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                className={`eve-btn text-[10px] ${wikiCategory === id ? "eve-btn-primary" : ""}`}
                onClick={() => setWikiCategory(id)}
              >
                {label}
              </button>
            ))}
          </div>
        ) : null}
        {showSdeBrowse ? (
          <>
            <div className="flex flex-wrap gap-1 mb-2 items-center">
              <span className="text-[10px] text-[var(--text-muted)] mr-1">SDE category</span>
              {categories.map((c) => (
                <button
                  key={c}
                  type="button"
                  className={`eve-btn text-[10px] ${cat === c ? "eve-btn-primary" : ""}`}
                  onClick={() => setCat(c)}
                >
                  {c}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-1 mb-2 items-center eve-sde-toolbar">
              <span className="text-[10px] text-[var(--text-muted)] mr-1">Compare</span>
              <button
                type="button"
                className="eve-btn eve-btn-primary text-[10px]"
                disabled={compareIds.length < 2}
                title={compareIds.length < 2 ? "Select two or more types using the checkboxes in the table" : undefined}
                onClick={() => openCompare(`Compare (${compareIds.length})`, compareIds)}
              >
                Open comparison{compareIds.length >= 2 ? ` (${compareIds.length})` : ""}
              </button>
              {compareIds.length > 0 ? (
                <button type="button" className="eve-btn text-[10px]" onClick={() => setCompareIds([])}>
                  Clear
                </button>
              ) : (
                <span className="text-[10px] text-[var(--text-muted)]">Use checkboxes in the list below</span>
              )}
            </div>
            <div className="flex flex-wrap gap-1 mb-2 items-center">
              <span className="text-[10px] text-[var(--text-muted)] mr-1">Skills</span>
              {(
                [
                  ["all", "All"],
                  ["can_use", "Can use"],
                  ["missing", "Missing skills"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  className={`eve-btn text-[10px] ${skillFilter === id ? "eve-btn-primary" : ""}`}
                  onClick={() => setSkillFilter(id)}
                >
                  {label}
                </button>
              ))}
            </div>
          </>
        ) : null}
        <div className="flex flex-col flex-1 min-h-0 h-[calc(100%-8rem)]">
          {knowledgeMode ? (
            <KnowledgeSearchResults
              results={knowledgeResults}
              scope={scope}
              loading={knowledgeLoading}
              onSelectWiki={openWiki}
              onSelectType={openWikiForType}
            />
          ) : (
            <SdeSearchPanel
              types={types}
              selectedTypeId={selectedTypeId}
              onSelect={selectType}
              category={cat}
              skillFilter={skillFilter}
              compareSelection={compareIds}
              onToggleCompare={toggleCompare}
              query={query}
              onQueryChange={setQuery}
              hideSearchBar
            />
          )}
        </div>
      </EveWindow>
      <EveWindow
        id="sde-detail"
        title={selectedTypeId ? selectedName : "Type Inspector"}
        defaultX={760}
        defaultY={24}
        defaultWidth={420}
        defaultHeight={520}
      >
        <SdeItemDetailPanel
          typeId={selectedTypeId}
          characters={charSkills?.characters ?? []}
          onSelectType={selectTypeById}
          onCompareGroup={handleCompareGroup}
          onOpenWiki={openWikiForType}
        />
      </EveWindow>
      <EveWindow
        id="wiki-article"
        title={wikiTitle ? wikiWindowTitle : "Wiki article"}
        defaultX={760}
        defaultY={560}
        defaultWidth={420}
        defaultHeight={360}
      >
        <WikiArticlePanel title={wikiTitle} onOpenWiki={openWiki} onOpenType={openWikiForType} />
      </EveWindow>
      <EveWindow
        id="sde-compare"
        title={compareTitle}
        defaultX={24}
        defaultY={560}
        defaultWidth={900}
        defaultHeight={360}
      >
        <SdeComparePanel typeIds={compareIds} onSelectType={selectTypeById} />
      </EveWindow>
    </DesktopSurface>
  );
}
