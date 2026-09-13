"use client";

import { useEffect, useMemo, useState } from "react";
import { EveRadarChart } from "@/components/EveRadarChart";
import { EveTypeIcon } from "@/components/ui/EveTypeIcon";
import { SectionHead } from "@/components/ui";
import type { AssetTreeNode } from "@/components/tools/CharacterSheetAssets";
import { isShipCategory, shipRadarFromAttributes } from "@/lib/shipRadarStats";

type TypeDetail = {
  type_id: number;
  name: string;
  category_name: string;
  group_name: string;
  attributes: { attribute_id: number; name: string; value: number }[];
};

function FittingRow({ node, depth = 0 }: { node: AssetTreeNode; depth?: number }) {
  return (
    <>
      <tr className="eve-asset-fit-row">
        <td style={{ paddingLeft: `${depth * 12}px` }}>
          <EveTypeIcon typeId={node.type_id} size={20} preferRender categoryName={node.category_name} />
        </td>
        <td>
          {node.type_name}
          {node.custom_name ? <span className="text-[var(--text-muted)]"> — {node.custom_name}</span> : null}
        </td>
        <td className="text-[var(--text-muted)]">{node.flag_label || node.flag || "—"}</td>
        <td className="text-right tabular-nums">{node.quantity.toLocaleString()}</td>
      </tr>
      {(node.children || []).map((child) => (
        <FittingRow key={`${child.item_id}-${child.type_id}`} node={child} depth={depth + 1} />
      ))}
    </>
  );
}

export function AssetShipFittingPanel({
  ship,
  locationName,
}: {
  ship: AssetTreeNode | null;
  locationName?: string;
}) {
  const [detail, setDetail] = useState<TypeDetail | null>(null);

  useEffect(() => {
    if (!ship?.type_id) {
      setDetail(null);
      return;
    }
    fetch(`/api/tools/sde/types/${ship.type_id}`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setDetail(data as TypeDetail | null))
      .catch(() => setDetail(null));
  }, [ship?.type_id]);

  const radar = useMemo(() => {
    if (!detail) return [];
    return shipRadarFromAttributes(detail.attributes || []);
  }, [detail]);

  if (!ship) {
    return <p className="text-[11px] text-[var(--text-muted)] p-2">Select a ship in Assets to view its fitting.</p>;
  }

  const modules = ship.children || [];
  const showRadar = isShipCategory(detail?.category_name, detail?.group_name) && radar.length >= 3;

  return (
    <div className="eve-ship-fitting-panel p-2 text-[11px]">
      <div className="flex items-start gap-3 mb-3">
        <EveTypeIcon typeId={ship.type_id} size={40} preferRender categoryName={ship.category_name} />
        <div className="flex-1 min-w-0">
          <div className="font-medium">{ship.custom_name || ship.type_name}</div>
          {ship.custom_name ? <div className="text-[var(--text-muted)]">{ship.type_name}</div> : null}
          {locationName ? <div className="text-[10px] text-[var(--text-muted)]">{locationName}</div> : null}
        </div>
        {showRadar ? (
          <div className="w-[180px] shrink-0">
            <EveRadarChart data={radar} title="Hull stats" compact />
          </div>
        ) : null}
      </div>
      {modules.length ? (
        <>
          <SectionHead>Fitted modules</SectionHead>
          <table className="eve-table w-full text-[10px]">
            <thead>
              <tr>
                <th className="w-8" />
                <th>Module / item</th>
                <th>Slot</th>
                <th className="text-right w-12">Qty</th>
              </tr>
            </thead>
            <tbody>
              {modules.map((mod) => (
                <FittingRow key={`${mod.item_id}-${mod.type_id}`} node={mod} />
              ))}
            </tbody>
          </table>
        </>
      ) : (
        <p className="text-[var(--text-muted)]">No fitted modules in synced asset data (empty hull or expand in hangar).</p>
      )}
    </div>
  );
}
