"use client";

import Link from "next/link";
import { EveRadarChart } from "@/components/EveRadarChart";
import { useMarketBrowser } from "@/components/tools/MarketBrowserContext";
import { isShipCategory, shipRadarFromAttributes } from "@/lib/shipRadarStats";
import { useEffect, useMemo, useState } from "react";
import { SectionHead, StatusStrip } from "@/components/ui";
import { EveTypeIcon } from "@/components/ui/EveTypeIcon";
import { Tooltip } from "@/components/Tooltip";
import type { CharacterSkillsPayload } from "./SdeSearchPanel";
import { WikiArticleContent } from "./WikiPanels";
import { fetchWikiForType, type WikiArticle } from "@/lib/knowledge";

export type SdeTypeDetail = {
  type_id: number;
  name: string;
  group_name: string;
  category_name: string;
  description: string;
  published: boolean;
  mass: number;
  volume_m3: number;
  capacity: number;
  base_price: number;
  attributes: { attribute_id: number; name: string; value: number; description: string }[];
  requirements: { kind: string; type_id: number | null; name: string; level: number | null }[];
  industry: {
    activity: string;
    blueprint_type_id: number;
    blueprint_name: string;
    product_quantity: number;
    materials: { type_id: number; name: string; quantity: number }[];
  }[];
  storefront_listing: {
    id: number;
    type_id: number;
    type_name: string;
    quantity: number;
    price_public_isk: number;
    suggested_price_isk: number;
  } | null;
  skill_meta?: { rank: number; primary_attribute: string; secondary_attribute: string } | null;
  skill_check?: { can_use: boolean; missing: { type_id: number; name: string; required_level: number; trained_level: number }[] };
};

type Tab = "description" | "attributes" | "industry" | "requirements" | "wiki";

function fmtNum(v: number) {
  if (Math.abs(v) >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (Number.isInteger(v)) return String(v);
  return v.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function charsWithSkill(characters: CharacterSkillsPayload["characters"], skillTypeId: number, level: number) {
  const names: string[] = [];
  for (const ch of characters) {
    for (const s of ch.skills) {
      if (s.skill_type_id === skillTypeId && s.trained_level >= level) {
        names.push(ch.character_name);
        break;
      }
    }
  }
  return names;
}

function TypeLink({
  typeId,
  name,
  onSelectType,
  className,
}: {
  typeId: number;
  name: string;
  onSelectType?: (typeId: number) => void;
  className?: string;
}) {
  if (!onSelectType) {
    return <span className={className}>{name}</span>;
  }
  return (
    <button
      type="button"
      className={`eve-sde-type-link ${className || ""}`}
      onClick={() => onSelectType(typeId)}
    >
      {name}
    </button>
  );
}

function SkillRequirementRow({
  req,
  characters,
  skillCheck,
  onSelectType,
}: {
  req: SdeTypeDetail["requirements"][0];
  characters: CharacterSkillsPayload["characters"];
  skillCheck?: SdeTypeDetail["skill_check"];
  onSelectType?: (typeId: number) => void;
}) {
  const level = req.level ?? 1;
  const skillId = req.type_id;
  const isSkill = req.kind === "skill" || (skillId != null && skillId > 0);

  if (!isSkill || !skillId) {
    return (
      <li>
        {req.name}
        {req.level != null ? ` — Level ${req.level}` : ""}
      </li>
    );
  }

  const qualified = charsWithSkill(characters, skillId, level);
  const missingEntry = skillCheck?.missing.find((m) => m.type_id === skillId);
  const rosterMet = qualified.length > 0;
  const met = rosterMet || (skillCheck ? !missingEntry : false);

  const hint = rosterMet
    ? `Trained on: ${qualified.join(", ")}`
    : missingEntry
      ? `Best trained level ${missingEntry.trained_level} (need ${missingEntry.required_level})`
      : met
        ? "Met across your linked characters."
        : "None of your linked characters meet this level.";

  return (
    <li className="flex items-center gap-1 flex-wrap">
      <Tooltip label={req.name} hint={hint} side="right">
        <TypeLink typeId={skillId} name={req.name} onSelectType={onSelectType} />
      </Tooltip>
      {req.level != null ? <span className="text-[var(--text-muted)]">— Level {req.level}</span> : null}
      {met ? (
        <span className="text-[var(--ok)] text-[10px]">
          ({rosterMet ? `${qualified.length} char${qualified.length === 1 ? "" : "s"}` : "met"})
        </span>
      ) : (
        <span className="text-[var(--danger)] text-[10px]">(missing)</span>
      )}
    </li>
  );
}

export function SdeItemDetailPanel({
  typeId,
  characters = [],
  onSelectType,
  onCompareGroup,
  onOpenWiki,
  onOpenMarket,
}: {
  typeId: number | null;
  characters?: CharacterSkillsPayload["characters"];
  onSelectType?: (typeId: number) => void;
  onCompareGroup?: (groupName: string, typeIds: number[]) => void;
  onOpenWiki?: (typeId: number, name?: string) => void;
  onOpenMarket?: (typeId: number, typeName: string) => void;
}) {
  const marketBrowser = useMarketBrowser();
  const [tab, setTab] = useState<Tab>("description");
  const [detail, setDetail] = useState<SdeTypeDetail | null>(null);
  const [wikiArticle, setWikiArticle] = useState<WikiArticle | null>(null);
  const [wikiLoading, setWikiLoading] = useState(false);
  const [wikiError, setWikiError] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [rosterCharacters, setRosterCharacters] = useState<CharacterSkillsPayload["characters"]>(
    () => characters ?? []
  );

  useEffect(() => {
    if (characters && characters.length > 0) {
      setRosterCharacters(characters);
      return;
    }
    fetch("/api/tools/sde/character-skills", { cache: "no-store", credentials: "same-origin" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data: CharacterSkillsPayload | null) => {
        setRosterCharacters(data?.characters ?? []);
      })
      .catch(() => setRosterCharacters([]));
  }, [characters]);

  useEffect(() => {
    if (!typeId) {
      setDetail(null);
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    fetch(`/api/tools/sde/types/${typeId}?include_skill_check=true`, { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) throw new Error("Type not found");
        return res.json() as Promise<SdeTypeDetail>;
      })
      .then((data) => {
        setDetail(data);
        setTab("description");
      })
      .catch(() => {
        setDetail(null);
        setError("Failed to load type details.");
      })
      .finally(() => setLoading(false));
  }, [typeId]);

  useEffect(() => {
    if (!typeId) return;
    marketBrowser?.warmMarketHistory(typeId);
  }, [typeId, marketBrowser]);

  useEffect(() => {
    if (!typeId || tab !== "wiki") {
      setWikiArticle(null);
      setWikiError("");
      return;
    }
    setWikiLoading(true);
    setWikiError("");
    fetchWikiForType(typeId)
      .then(setWikiArticle)
      .catch(() => {
        setWikiArticle(null);
        setWikiError("Wiki article unavailable.");
      })
      .finally(() => setWikiLoading(false));
  }, [typeId, tab]);

  const skillRows = useMemo(
    () => (detail?.requirements || []).filter((r) => r.kind === "skill" || (r.type_id != null && r.type_id > 0)),
    [detail]
  );

  const shipRadar = useMemo(() => {
    if (!detail) return [];
    if (!isShipCategory(detail.category_name, detail.group_name)) return [];
    return shipRadarFromAttributes(detail.attributes || []);
  }, [detail]);

  if (!typeId) {
    return (
      <>
        <SectionHead>Type Inspector</SectionHead>
        <p className="text-[var(--text-muted)] text-[11px]">
          Select a type from the browser. Skill requirements are clickable; hover to see which characters qualify.
        </p>
      </>
    );
  }

  if (loading) {
    return <StatusStrip>Loading type {typeId}…</StatusStrip>;
  }

  if (error || !detail) {
    return <p className="text-[var(--danger)] text-[11px]">{error || "Type not found."}</p>;
  }

  const storefrontHref = `/industrial?tool=ip-storefront&type_id=${detail.type_id}`;

  const handleOpenMarket = () => {
    if (onOpenMarket) {
      onOpenMarket(detail.type_id, detail.name);
      return;
    }
    marketBrowser?.openMarketBrowser(detail.type_id, detail.name);
  };

  const handleCompareGroup = async () => {
    if (!detail.group_name || !onCompareGroup) return;
    const res = await fetch(
      `/api/tools/sde/group?group=${encodeURIComponent(detail.group_name)}&limit=40`
    );
    if (!res.ok) return;
    const rows = (await res.json()) as { type_id: number }[];
    const ids = rows.map((r) => r.type_id);
    if (!ids.includes(detail.type_id)) ids.unshift(detail.type_id);
    onCompareGroup(detail.group_name, ids.slice(0, 8));
  };

  return (
    <div className="eve-sde-detail flex flex-col h-full min-h-0">
      <div className="eve-sde-detail-header flex gap-2 items-start mb-2">
        <EveTypeIcon
          typeId={detail.type_id}
          size={48}
          className="shrink-0"
          categoryName={detail.category_name}
          groupName={detail.group_name}
        />
        <div className="min-w-0 flex-1">
          <div className="font-semibold text-[12px] leading-tight truncate" title={detail.name}>
            {detail.name}
          </div>
          <div className="text-[10px] text-[var(--text-muted)]">
            {detail.group_name}
            {detail.category_name ? ` · ${detail.category_name}` : ""}
          </div>
          <div className="text-[10px] text-[var(--text-muted)]">Type ID {detail.type_id}</div>
        </div>
      </div>

      {detail.skill_check ? (
        <div
          className={`text-[10px] mb-2 px-2 py-1 border ${
            detail.skill_check.can_use
              ? "border-[var(--ok)] text-[var(--ok)]"
              : "border-[var(--danger)] text-[var(--danger)]"
          }`}
        >
          {detail.skill_check.can_use
            ? "Your characters meet all skill requirements."
            : `Missing ${detail.skill_check.missing.length} skill requirement(s) across your roster.`}
        </div>
      ) : null}

      {detail.skill_meta && (detail.skill_meta.rank || detail.skill_meta.primary_attribute) ? (
        <div className="text-[10px] text-[var(--text-muted)] mb-2">
          Rank {detail.skill_meta.rank || "?"}
          {detail.skill_meta.primary_attribute
            ? ` · ${detail.skill_meta.primary_attribute} / ${detail.skill_meta.secondary_attribute}`
            : ""}
        </div>
      ) : null}

      <div className="eve-sde-detail-stats grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px] mb-2">
        <span>Volume</span>
        <span className="num">{fmtNum(detail.volume_m3)} m³</span>
        {detail.mass > 0 ? (
          <>
            <span>Mass</span>
            <span className="num">{fmtNum(detail.mass)} kg</span>
          </>
        ) : null}
        {detail.base_price > 0 ? (
          <>
            <span>Base price</span>
            <span className="num">{fmtNum(detail.base_price)} ISK</span>
          </>
        ) : null}
      </div>

      {shipRadar.length >= 3 ? (
        <div className="mb-2 border border-[var(--border)] bg-[var(--panel-inset)] p-1">
          <EveRadarChart data={shipRadar} title="Combat profile" compact />
        </div>
      ) : null}

      <div className="eve-sde-detail-tabs flex gap-1 mb-2 flex-wrap">
        {(
          [
            ["description", "Description"],
            ["attributes", "Attributes"],
            ["industry", "Industry"],
            ["requirements", "Requirements"],
            ["wiki", "Wiki"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`eve-btn text-[10px] py-0.5 px-2 ${tab === id ? "eve-btn-primary" : ""}`}
            onClick={() => setTab(id)}
          >
            {label}
            {id === "requirements" && skillRows.length ? ` (${skillRows.length})` : ""}
          </button>
        ))}
      </div>

      <div className="eve-sde-detail-body flex-1 overflow-auto text-[11px] min-h-0">
        {tab === "description" ? (
          detail.description ? (
            <p className="whitespace-pre-wrap leading-relaxed">{detail.description}</p>
          ) : (
            <p className="text-[var(--text-muted)]">No description available.</p>
          )
        ) : null}

        {tab === "attributes" ? (
          detail.attributes.length ? (
            <table className="eve-table text-[10px]">
              <thead>
                <tr>
                  <th>Attribute</th>
                  <th>Value</th>
                </tr>
              </thead>
              <tbody>
                {detail.attributes.map((a) => (
                  <tr key={a.attribute_id}>
                    <td title={a.description || undefined}>{a.name}</td>
                    <td className="num">{fmtNum(a.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-[var(--text-muted)]">No published attributes.</p>
          )
        ) : null}

        {tab === "industry" ? (
          detail.industry.length ? (
            <div className="space-y-3">
              {detail.industry.map((recipe) => (
                <div key={`${recipe.blueprint_type_id}-${recipe.activity}`} className="border border-[var(--border)] p-2">
                  <div className="font-semibold text-[10px] mb-1">
                    {recipe.activity} —{" "}
                    <TypeLink
                      typeId={recipe.blueprint_type_id}
                      name={recipe.blueprint_name}
                      onSelectType={onSelectType}
                    />
                  </div>
                  <div className="text-[10px] text-[var(--text-muted)] mb-1">
                    Output qty: {recipe.product_quantity}
                  </div>
                  <table className="eve-table text-[10px]">
                    <thead>
                      <tr>
                        <th>Material</th>
                        <th>Qty</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recipe.materials.map((m) => (
                        <tr key={m.type_id}>
                          <td>
                            <TypeLink typeId={m.type_id} name={m.name} onSelectType={onSelectType} />
                          </td>
                          <td className="num">{m.quantity.toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-[var(--text-muted)]">This item is not manufactured from a known blueprint.</p>
          )
        ) : null}

        {tab === "requirements" ? (
          detail.requirements.length ? (
            <ul className="space-y-1">
              {detail.requirements.map((r) => (
                <SkillRequirementRow
                  key={`${r.kind}-${r.type_id ?? r.name}`}
                  req={r}
                  characters={rosterCharacters}
                  skillCheck={detail.skill_check}
                  onSelectType={onSelectType}
                />
              ))}
            </ul>
          ) : (
            <p className="text-[var(--text-muted)]">No skill or fitting requirements listed.</p>
          )
        ) : null}

        {tab === "wiki" ? (
          <WikiArticleContent
            article={wikiArticle}
            loading={wikiLoading}
            error={wikiError}
            onOpenType={onSelectType}
            onOpenWiki={
              onOpenWiki
                ? (title) => {
                    const m = title.match(/Types\/(\d+)/);
                    if (m) onOpenWiki(Number(m[1]));
                  }
                : undefined
            }
          />
        ) : null}
      </div>

      <div className="eve-sde-detail-actions flex flex-wrap gap-2 mt-2 pt-2 border-t border-[var(--border)]">
        {onCompareGroup && detail.group_name ? (
          <button type="button" className="eve-btn eve-btn-primary text-[10px]" onClick={() => void handleCompareGroup()}>
            Compare {detail.group_name}
          </button>
        ) : null}
        {onOpenWiki ? (
          <button type="button" className="eve-btn text-[10px]" onClick={() => onOpenWiki(detail.type_id, detail.name)}>
            Open wiki
          </button>
        ) : null}
        <button
          type="button"
          className="eve-btn eve-btn-primary text-[10px] flex-1 min-w-[120px]"
          onClick={handleOpenMarket}
        >
          View Market Details
        </button>
        {detail.storefront_listing ? (
          <Link href={storefrontHref} className="eve-btn text-[10px] flex-1 text-center">
            Order Now
          </Link>
        ) : (
          <button type="button" className="eve-btn text-[10px] flex-1 opacity-50" disabled title="Not listed on storefront">
            Order Now
          </button>
        )}
      </div>
    </div>
  );
}
