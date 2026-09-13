"use client";

import { useMemo, useState, type MouseEvent } from "react";
import { EveTypeIcon } from "@/components/ui/EveTypeIcon";
import { useCharSheetInspect } from "@/components/tools/CharSheetInspectContext";

export type AssetTreeNode = {
  item_id: number;
  type_id: number;
  type_name: string;
  custom_name?: string;
  quantity: number;
  flag?: string;
  flag_label?: string;
  kind: "ship" | "container" | "item";
  category_name?: string;
  children?: AssetTreeNode[];
};

export type AssetLocation = {
  location_id: number;
  location_name: string;
  solar_system_id?: number | null;
  distance_ly?: number | null;
  item_count: number;
  ships: AssetTreeNode[];
  containers: AssetTreeNode[];
  items: AssetTreeNode[];
};

type SearchMode = "all" | "location" | "item" | "id" | "distance";

function nodeKey(node: AssetTreeNode, prefix: string) {
  return `${prefix}-${node.item_id || node.type_id}-${node.type_name}`;
}

function nodeMatches(node: AssetTreeNode, q: string, idQ: number | null): boolean {
  const hay = `${node.type_name} ${node.custom_name || ""} ${node.type_id}`.toLowerCase();
  if (idQ != null && node.type_id === idQ) return true;
  if (!q) return true;
  return hay.includes(q);
}

function filterTree(node: AssetTreeNode, q: string, idQ: number | null): AssetTreeNode | null {
  const kids = (node.children || [])
    .map((c) => filterTree(c, q, idQ))
    .filter((c): c is AssetTreeNode => c != null);
  const selfMatch = nodeMatches(node, q, idQ);
  if (selfMatch || kids.length) {
    return { ...node, children: kids.length ? kids : node.children && !q && idQ == null ? node.children : kids };
  }
  return null;
}

function AssetTreeRow({
  node,
  depth,
  idPrefix,
  locationName,
}: {
  node: AssetTreeNode;
  depth: number;
  idPrefix: string;
  locationName: string;
}) {
  const inspect = useCharSheetInspect();
  const hasChildren = (node.children?.length ?? 0) > 0;
  const expandable = hasChildren && (node.kind === "ship" || node.kind === "container");
  const [open, setOpen] = useState(false);
  const key = nodeKey(node, idPrefix);

  const toggle = (e: MouseEvent) => {
    e.stopPropagation();
    if (expandable) setOpen((v) => !v);
  };

  const onRowClick = () => {
    if (!inspect) return;
    if (node.kind === "ship") {
      inspect.openShipFitting(node, locationName);
      return;
    }
    inspect.openItemInfo(node.type_id, node.type_name);
  };

  return (
    <>
      <tr
        className={`eve-asset-row eve-asset-row--${node.kind}${expandable ? " eve-asset-row--expandable" : ""}${open ? " open" : ""} eve-asset-row--inspect`}
        onClick={onRowClick}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onRowClick();
          }
        }}
        tabIndex={0}
        role="button"
      >
        <td className="w-6" style={{ paddingLeft: `${depth * 12}px` }} onClick={toggle}>
          {expandable ? (
            <span className={`eve-char-sheet-chevron ${open ? "open" : ""}`} aria-hidden />
          ) : (
            <span className="eve-char-sheet-chevron-spacer" />
          )}
        </td>
        <td className="w-6">
          <EveTypeIcon
            typeId={node.type_id}
            size={18}
            preferRender={node.kind === "ship"}
            categoryName={node.category_name}
          />
        </td>
        <td>
          {node.type_name}
          {node.kind === "ship" ? <span className="eve-asset-kind-tag">Ship</span> : null}
          {node.kind === "container" ? <span className="eve-asset-kind-tag">Container</span> : null}
          {node.flag_label ? <span className="eve-asset-flag-tag">{node.flag_label}</span> : null}
        </td>
        <td className="text-right tabular-nums text-[var(--text-muted)]">{node.type_id}</td>
        <td className="text-right tabular-nums">{node.quantity.toLocaleString()}</td>
      </tr>
      {expandable && open
        ? node.children!.map((child) => (
            <AssetTreeRow
              key={nodeKey(child, key)}
              node={child}
              depth={depth + 1}
              idPrefix={key}
              locationName={locationName}
            />
          ))
        : null}
    </>
  );
}

function LocationSection({ location }: { location: AssetLocation }) {
  const [open, setOpen] = useState(true);
  const rows = useMemo(
    () => [...location.ships, ...location.containers, ...location.items],
    [location]
  );

  return (
    <section className="eve-char-sheet-asset-location">
      <button
        type="button"
        className="eve-char-sheet-asset-location-head"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className={`eve-char-sheet-chevron ${open ? "open" : ""}`} aria-hidden />
        <span className="eve-char-sheet-asset-location-name">{location.location_name}</span>
        {location.distance_ly != null ? (
          <span className="eve-asset-dist-tag">{location.distance_ly.toFixed(1)} ly</span>
        ) : null}
        <span className="text-[var(--text-muted)]">
          ({location.item_count.toLocaleString()} items)
        </span>
      </button>
      {open ? (
        <table className="eve-table w-full text-[10px]">
          <thead>
            <tr>
              <th className="w-6" />
              <th className="w-6" />
              <th>Item</th>
              <th className="text-right w-14">Type ID</th>
              <th className="text-right w-16">Qty</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? (
              rows.map((node) => (
                <AssetTreeRow
                  key={nodeKey(node, String(location.location_id))}
                  node={node}
                  depth={0}
                  idPrefix={String(location.location_id)}
                  locationName={location.location_name}
                />
              ))
            ) : (
              <tr>
                <td colSpan={5} className="text-[var(--text-muted)]">
                  No items at this location.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}

export function CharacterSheetAssets({ locations }: { locations: AssetLocation[] }) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("all");
  const [maxDistance, setMaxDistance] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const idQ = /^\d+$/.test(q) ? Number(q) : null;
    const maxLy = maxDistance.trim() ? Number(maxDistance) : null;

    return locations
      .filter((loc) => {
        if (mode === "distance" && maxLy != null && Number.isFinite(maxLy)) {
          if (loc.distance_ly == null || loc.distance_ly > maxLy) return false;
        }
        if (mode === "location" && q) {
          return loc.location_name.toLowerCase().includes(q);
        }
        if (mode === "distance" && q && !/^\d/.test(q)) {
          return loc.location_name.toLowerCase().includes(q);
        }
        return true;
      })
      .map((loc) => {
        if (mode === "item" || mode === "id" || (mode === "all" && (q || idQ != null))) {
          const itemQ = mode === "id" || idQ != null ? "" : q;
          const typeIdQ = mode === "id" || idQ != null ? idQ : null;
          const ships = loc.ships.map((n) => filterTree(n, itemQ, typeIdQ)).filter(Boolean) as AssetTreeNode[];
          const containers = loc.containers
            .map((n) => filterTree(n, itemQ, typeIdQ))
            .filter(Boolean) as AssetTreeNode[];
          const items = loc.items.map((n) => filterTree(n, itemQ, typeIdQ)).filter(Boolean) as AssetTreeNode[];
          if (!ships.length && !containers.length && !items.length) return null;
          return { ...loc, ships, containers, items };
        }
        return loc;
      })
      .filter((loc): loc is AssetLocation => loc != null);
  }, [locations, query, mode, maxDistance]);

  if (!locations.length) {
    return <p className="text-[var(--text-muted)]">No assets synced yet.</p>;
  }

  return (
    <div className="eve-char-sheet-assets space-y-3">
      <div className="eve-char-sheet-assets-toolbar">
        <input
          className="eve-input flex-1"
          placeholder={
            mode === "location"
              ? "Search location name…"
              : mode === "item"
                ? "Search item name…"
                : mode === "id"
                  ? "Type ID…"
                  : mode === "distance"
                    ? "Optional location filter…"
                    : "Search location, item, or type ID…"
          }
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          className="eve-input"
          value={mode}
          onChange={(e) => setMode(e.target.value as SearchMode)}
          aria-label="Search mode"
        >
          <option value="all">All</option>
          <option value="location">Location</option>
          <option value="item">Item</option>
          <option value="id">Type ID</option>
          <option value="distance">Distance</option>
        </select>
        {mode === "distance" ? (
          <input
            className="eve-input w-24"
            placeholder="Max ly"
            value={maxDistance}
            onChange={(e) => setMaxDistance(e.target.value)}
            aria-label="Maximum distance in light years"
          />
        ) : null}
      </div>

      {filtered.length ? (
        filtered.map((loc) => <LocationSection key={loc.location_id} location={loc} />)
      ) : (
        <p className="text-[var(--text-muted)]">No assets match your search.</p>
      )}
    </div>
  );
}
