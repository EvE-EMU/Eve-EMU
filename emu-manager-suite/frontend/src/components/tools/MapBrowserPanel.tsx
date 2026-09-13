"use client";

import { useEffect, useMemo, useState } from "react";
import {
  expandWithNeighbors,
  systemIdsInConstellation,
  systemIdsInRegion,
  type AtlasSystem,
  type MapAtlas,
} from "@/lib/mapAtlas";

type SystemRow = {
  system_id: number;
  name: string;
  security: number;
  region_name?: string;
};

async function searchSystems(q: string, limit = 24): Promise<SystemRow[]> {
  const res = await fetch(`/api/tools/sde/systems?q=${encodeURIComponent(q)}&limit=${limit}`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

type MapBrowserPanelProps = {
  atlas: MapAtlas | null;
  selectedSystem: AtlasSystem | null;
  onSelectSystem: (sys: AtlasSystem | null) => void;
  onFocusSystemIds: (ids: number[]) => void;
  onUseAsOrigin?: (name: string) => void;
  onUseAsDestination?: (name: string) => void;
};

export function MapBrowserPanel({
  atlas,
  selectedSystem,
  onSelectSystem,
  onFocusSystemIds,
  onUseAsOrigin,
  onUseAsDestination,
}: MapBrowserPanelProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SystemRow[]>([]);
  const [regionFilter, setRegionFilter] = useState("");
  const [constellationFilter, setConstellationFilter] = useState("");

  const regionOptions = useMemo(() => {
    if (!atlas) return [];
    return atlas.regions.map((r) => r.name).sort((a, b) => a.localeCompare(b));
  }, [atlas]);

  const constellationOptions = useMemo(() => {
    if (!atlas) return [];
    const names = new Set<string>();
    for (const c of atlas.constellations) {
      if (!regionFilter || c.region_name === regionFilter) names.add(c.name);
    }
    return [...names].sort((a, b) => a.localeCompare(b));
  }, [atlas, regionFilter]);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setResults([]);
      return;
    }
    const t = window.setTimeout(() => {
      void searchSystems(q, 24).then(setResults);
    }, 220);
    return () => window.clearTimeout(t);
  }, [query]);

  const neighbors = useMemo(() => {
    if (!atlas || !selectedSystem) return [];
    return (atlas.adjacency.get(selectedSystem.system_id) ?? [])
      .map((id) => atlas.systemsById.get(id))
      .filter((s): s is AtlasSystem => Boolean(s))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [atlas, selectedSystem]);

  const pickFromSearch = (row: SystemRow) => {
    if (!atlas) return;
    const sys = atlas.systemsById.get(row.system_id);
    if (sys) {
      onSelectSystem(sys);
      onFocusSystemIds([...expandWithNeighbors(atlas, [sys.system_id], 2)]);
    } else {
      setQuery(row.name);
    }
  };

  const applyAreaFilter = () => {
    if (!atlas) return;
    if (constellationFilter) {
      const ids = systemIdsInConstellation(atlas, constellationFilter, regionFilter || undefined);
      if (ids.length) onFocusSystemIds(ids);
      return;
    }
    if (regionFilter) {
      const ids = systemIdsInRegion(atlas, regionFilter);
      if (ids.length) onFocusSystemIds(ids);
      return;
    }
    onFocusSystemIds([]);
  };

  return (
    <div className="eve-map-browser">
      <div className="eve-map-browser-toolbar">
        <label className="eve-map-browser-field eve-map-browser-field--grow">
          <span className="text-[var(--text-muted)]">Search systems</span>
          <input
            className="eve-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Jita, Amarr, 1DQ…"
          />
        </label>
        <label className="eve-map-browser-field">
          <span className="text-[var(--text-muted)]">Region</span>
          <select
            className="eve-select"
            value={regionFilter}
            onChange={(e) => {
              setRegionFilter(e.target.value);
              setConstellationFilter("");
            }}
          >
            <option value="">All regions</option>
            {regionOptions.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label className="eve-map-browser-field">
          <span className="text-[var(--text-muted)]">Constellation</span>
          <select
            className="eve-select"
            value={constellationFilter}
            onChange={(e) => setConstellationFilter(e.target.value)}
            disabled={!regionFilter && constellationOptions.length === 0}
          >
            <option value="">All constellations</option>
            {constellationOptions.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="eve-btn eve-btn-primary" disabled={!atlas} onClick={applyAreaFilter}>
          Go to area
        </button>
        <button
          type="button"
          className="eve-btn"
          disabled={!atlas}
          onClick={() => {
            setRegionFilter("");
            setConstellationFilter("");
            setQuery("");
            onSelectSystem(null);
            onFocusSystemIds([]);
          }}
        >
          All New Eden
        </button>
      </div>

      {results.length > 0 ? (
        <ul className="eve-map-browser-results">
          {results.map((row) => (
            <li key={row.system_id}>
              <button type="button" className="eve-map-browser-result" onClick={() => pickFromSearch(row)}>
                <strong>{row.name}</strong>
                <span>{row.security.toFixed(1)} sec</span>
                {row.region_name ? <span className="text-[var(--text-muted)]">{row.region_name}</span> : null}
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {selectedSystem ? (
        <div className="eve-map-browser-detail">
          <div className="eve-map-browser-detail-head">
            <div>
              <h3 className="eve-map-browser-detail-name">{selectedSystem.name}</h3>
              <p className="text-[var(--text-muted)] text-[0.85em]">
                {selectedSystem.security.toFixed(1)} sec · {selectedSystem.constellation_name || "—"} ·{" "}
                {selectedSystem.region_name || "—"}
              </p>
            </div>
            <div className="flex flex-wrap gap-1">
              {onUseAsOrigin ? (
                <button type="button" className="eve-btn eve-btn-sm" onClick={() => onUseAsOrigin(selectedSystem.name)}>
                  Set origin
                </button>
              ) : null}
              {onUseAsDestination ? (
                <button
                  type="button"
                  className="eve-btn eve-btn-sm"
                  onClick={() => onUseAsDestination(selectedSystem.name)}
                >
                  Set destination
                </button>
              ) : null}
              <button
                type="button"
                className="eve-btn eve-btn-sm"
                onClick={() => {
                  if (!atlas) return;
                  onFocusSystemIds([...expandWithNeighbors(atlas, [selectedSystem.system_id], 2)]);
                }}
              >
                Center
              </button>
            </div>
          </div>
          {neighbors.length ? (
            <>
              <p className="text-[var(--text-muted)] text-[0.8em] mb-1">Stargate neighbors ({neighbors.length})</p>
              <ul className="eve-map-browser-neighbors">
                {neighbors.map((n) => (
                  <li key={n.system_id}>
                    <button
                      type="button"
                      className="eve-map-browser-neighbor"
                      onClick={() => {
                        onSelectSystem(n);
                        if (atlas) onFocusSystemIds([...expandWithNeighbors(atlas, [n.system_id], 2)]);
                      }}
                    >
                      {n.name}
                      <span>{n.security.toFixed(1)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </div>
      ) : (
        <p className="eve-map-browser-hint text-[var(--text-muted)] text-[0.85em]">
          Pan and zoom the map · scroll to zoom · click a system to inspect · search or filter by region
        </p>
      )}
    </div>
  );
}
