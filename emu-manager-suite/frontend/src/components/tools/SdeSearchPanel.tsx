"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { SdeType } from "@/lib/api";
import { EveTypeIcon } from "@/components/ui/EveTypeIcon";

export type SkillFilter = "all" | "can_use" | "missing";

export type CharacterSkillsPayload = {
  characters: {
    character_id: number;
    character_name: string;
    is_main?: boolean;
    skills: { skill_type_id: number; trained_level: number; skill_name?: string }[];
  }[];
  best_skills: Record<string, number>;
};

type SkillCheckMap = Record<number, { can_use: boolean; missing: { name: string }[] }>;

export function SdeSearchPanel({
  types,
  selectedTypeId,
  onSelect,
  category = "All",
  group = "",
  skillFilter = "all",
  compareSelection = [],
  onToggleCompare,
  query: controlledQuery,
  onQueryChange,
  hideSearchBar = false,
}: {
  types: SdeType[];
  selectedTypeId?: number | null;
  onSelect?: (row: SdeType) => void;
  category?: string;
  group?: string;
  skillFilter?: SkillFilter;
  compareSelection?: number[];
  onToggleCompare?: (typeId: number) => void;
  query?: string;
  onQueryChange?: (query: string) => void;
  hideSearchBar?: boolean;
}) {
  const [internalQ, setInternalQ] = useState("");
  const q = controlledQuery ?? internalQ;
  const setQ = onQueryChange ?? setInternalQ;
  const [rows, setRows] = useState(types);
  const [loading, setLoading] = useState(false);
  const [skillChecks, setSkillChecks] = useState<SkillCheckMap>({});

  useEffect(() => {
    setRows(types);
  }, [types]);

  const search = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ q, limit: "500" });
      if (category !== "All") params.set("category", category);
      if (group) params.set("group", group);
      const data = await (await fetch(`/api/tools/sde?${params}`)).json();
      setRows(data);
    } finally {
      setLoading(false);
    }
  }, [q, category, group]);

  useEffect(() => {
    if (hideSearchBar) {
      void search();
    }
  }, [hideSearchBar, search]);

  const refreshSkillChecks = useCallback(async (typeRows: SdeType[]) => {
    if (skillFilter === "all" || !typeRows.length) {
      setSkillChecks({});
      return;
    }
    const ids = typeRows.slice(0, 100).map((r) => r.type_id);
    const res = await fetch("/api/tools/sde/skill-check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type_ids: ids }),
    });
    if (res.ok) {
      setSkillChecks(await res.json());
    }
  }, [skillFilter]);

  useEffect(() => {
    void refreshSkillChecks(rows);
  }, [rows, refreshSkillChecks]);

  const visibleRows = useMemo(() => {
    if (skillFilter === "all") return rows;
    return rows.filter((row) => {
      const check = skillChecks[row.type_id];
      if (!check) return true;
      return skillFilter === "can_use" ? check.can_use : !check.can_use;
    });
  }, [rows, skillChecks, skillFilter]);

  return (
    <div className="flex flex-col gap-2 h-full min-h-0">
      {!hideSearchBar ? (
        <div className="flex gap-2">
          <input
            className="eve-input flex-1"
            placeholder="Search items, groups…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
          />
          <button type="button" className="eve-btn" onClick={search} disabled={loading}>
            Search
          </button>
        </div>
      ) : null}
      <div className="overflow-auto flex-1 min-h-0">
        <table className="eve-table text-[10px]">
          <thead>
            <tr>
              {onToggleCompare ? <th className="w-10 text-left" title="Select for comparison">Compare</th> : null}
              <th />
              <th>Name</th>
              <th>Type ID</th>
              <th>Group</th>
              {skillFilter !== "all" ? <th>Skills</th> : null}
              <th>Vol m³</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => {
              const check = skillChecks[row.type_id];
              return (
                <tr
                  key={row.type_id}
                  className={
                    selectedTypeId === row.type_id
                      ? "eve-row-selected"
                      : onSelect
                        ? "cursor-pointer hover:bg-[var(--panel-elevated)]"
                        : undefined
                  }
                  onClick={() => onSelect?.(row)}
                >
                  {onToggleCompare ? (
                    <td onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={compareSelection.includes(row.type_id)}
                        onChange={() => onToggleCompare(row.type_id)}
                        aria-label={`Compare ${row.name}`}
                      />
                    </td>
                  ) : null}
                  <td>
                    <EveTypeIcon
                      typeId={row.type_id}
                      size={28}
                      categoryName={row.category_name}
                      groupName={row.group_name}
                    />
                  </td>
                  <td>{row.name}</td>
                  <td>{row.type_id}</td>
                  <td>{row.group_name}</td>
                  {skillFilter !== "all" ? (
                    <td>
                      {check ? (
                        <span className={check.can_use ? "text-[var(--ok)]" : "text-[var(--danger)]"}>
                          {check.can_use ? "OK" : "Missing"}
                        </span>
                      ) : (
                        "…"
                      )}
                    </td>
                  ) : null}
                  <td>{row.volume_m3}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
