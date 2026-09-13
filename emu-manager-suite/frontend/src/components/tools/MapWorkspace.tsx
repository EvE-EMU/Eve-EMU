"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { EveWindow } from "@/components/ui";
import { DesktopSurface } from "@/components/WindowManager";
import { KpiStrip, KpiTile, SectionHead, StatusStrip } from "@/components/ui";
import { RouteActivityTable, type SystemActivityRow } from "./RouteActivityTable";
import { EveMapCanvas } from "./EveMapCanvas";
import { MapBrowserPanel } from "./MapBrowserPanel";
import { type MapEdge, type MapWaypoint } from "./RouteMapVisual";
import { loadMapAtlas, type AtlasSystem, type MapAtlas } from "@/lib/mapAtlas";
import type { RouteBookmark } from "@/lib/api";

type JumpShip = {
  slug: string;
  name: string;
  category: string;
  base_range_ly: number;
  fuel_per_ly: number;
  fuel_type: string;
  is_jump_freighter?: boolean;
};

type MapStatus = {
  systems_total: number;
  systems_with_coords: number;
  systems_with_layout?: number;
  stargate_links: number;
  full_sde_loaded: boolean;
  jump_drive_ready: boolean;
  layout_ready?: boolean;
};

type SystemRow = {
  system_id: number;
  name: string;
  security: number;
  region_name?: string;
  x?: number;
  y?: number;
};

type DockLocation = {
  id: string;
  kind: "npc_station" | "structure";
  system_id: number;
  system_name: string;
  label: string;
};

type DockLocationsResponse = {
  authenticated: boolean;
  character_id: number | null;
  character_name: string | null;
  corporation_id: number | null;
  alliance_id: number | null;
  npc_stations: DockLocation[];
  structures: DockLocation[];
  note: string | null;
};

type AuthMe = {
  authenticated: boolean;
  character_id: number | null;
  character_name: string | null;
  corporation_name?: string;
  alliance_name?: string;
};

async function searchSystems(q: string, limit = 40): Promise<SystemRow[]> {
  const res = await fetch(`/api/tools/sde/systems?q=${encodeURIComponent(q)}&limit=${limit}`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export function MapWorkspace({
  systems,
  bookmarks: initialBookmarks,
  jumpShips,
  mapStatus,
  defaultMode = "browse",
  embedded,
}: {
  systems: SystemRow[];
  bookmarks: RouteBookmark[];
  jumpShips: JumpShip[];
  mapStatus?: MapStatus | null;
  defaultMode?: "stargate" | "jump" | "browse";
  embedded?: boolean;
}) {
  const searchParams = useSearchParams();
  const [systemOptions, setSystemOptions] = useState<SystemRow[]>(systems);
  const [bookmarks, setBookmarks] = useState<RouteBookmark[]>(initialBookmarks);
  const [authMe, setAuthMe] = useState<AuthMe | null>(null);
  const [dockData, setDockData] = useState<DockLocationsResponse | null>(null);
  const [mode, setMode] = useState<"stargate" | "jump" | "browse">(defaultMode);
  const [originQ, setOriginQ] = useState("Jita");
  const [destQ, setDestQ] = useState("3-FKCZ");
  const [avoidLow, setAvoidLow] = useState(false);
  const [stargateRange, setStargateRange] = useState(5);
  const [shipSlug, setShipSlug] = useState(jumpShips[0]?.slug ?? "nomad");
  const [calibration, setCalibration] = useState(4);
  const [conservation, setConservation] = useState(4);
  const [jumpFreighters, setJumpFreighters] = useState(4);
  const [waypointIds, setWaypointIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveVisibility, setSaveVisibility] = useState<"personal" | "corp" | "alliance" | "link">("personal");
  const [lastShareUrl, setLastShareUrl] = useState<string | null>(null);
  const [destSystemId, setDestSystemId] = useState<number | undefined>();
  const [activity, setActivity] = useState<{
    systems: SystemActivityRow[];
    partial?: boolean;
    hours_available?: number;
  } | null>(null);
  const [atlas, setAtlas] = useState<MapAtlas | null>(null);
  const [atlasLoading, setAtlasLoading] = useState(true);
  const [browseSelected, setBrowseSelected] = useState<AtlasSystem | null>(null);
  const [mapFocusRequest, setMapFocusRequest] = useState<{ ids: number[]; nonce: number } | undefined>({
    ids: [],
    nonce: 0,
  });

  const [routeResult, setRouteResult] = useState<{
    jumps: number;
    route: string[];
    systems: { system_id: number; name: string; security: number; x?: number; y?: number }[];
    edges?: MapEdge[];
    error?: string;
    message?: string;
  } | null>(null);

  const [jumpResult, setJumpResult] = useState<{
    jumps: number;
    total_distance_ly: number;
    total_fuel: number;
    fuel_type: string;
    effective_range_ly: number;
    direct_distance_ly?: number;
    legs: { from_system_id: number; to_system_id: number; distance_ly: number; fuel: number; from_name: string; to_name: string }[];
    systems: { system_id: number; name: string; security: number; x?: number; y?: number; distance_ly?: number }[];
    waypoint_string?: string;
    midpoint_systems?: string[];
    error?: string;
    message?: string;
  } | null>(null);

  const [rangeResult, setRangeResult] = useState<{
    systems: { system_id: number; name: string; security: number; distance_ly?: number }[];
    effective_range_ly?: number;
  } | null>(null);

  const refreshBookmarks = useCallback(async (characterId?: number | null) => {
    const qs = characterId ? `?character_id=${characterId}` : "";
    const res = await fetch(`/api/tools/routes${qs}`, { cache: "no-store" });
    if (res.ok) setBookmarks(await res.json());
  }, []);

  const refreshDockLocations = useCallback(async (characterId?: number | null) => {
    const qs = characterId ? `?character_id=${characterId}` : "";
    const res = await fetch(`/api/tools/map/dock-locations${qs}`, { cache: "no-store" });
    if (res.ok) setDockData(await res.json());
  }, []);

  useEffect(() => {
    void (async () => {
      const meRes = await fetch("/api/auth/me", { cache: "no-store" });
      const me: AuthMe = meRes.ok ? await meRes.json() : { authenticated: false, character_id: null, character_name: null };
      setAuthMe(me);
      await Promise.all([refreshDockLocations(me.character_id), refreshBookmarks(me.character_id)]);
    })();
  }, [refreshBookmarks, refreshDockLocations]);

  useEffect(() => {
    void (async () => {
      setAtlasLoading(true);
      try {
        setAtlas(await loadMapAtlas());
      } finally {
        setAtlasLoading(false);
      }
    })();
  }, []);

  const findSystem = useCallback(
    (q: string) => {
      const needle = q.trim().toLowerCase();
      return (
        systemOptions.find((s) => s.name.toLowerCase() === needle) ??
        systemOptions.find((s) => s.name.toLowerCase().includes(needle))
      );
    },
    [systemOptions]
  );

  const resolveSystem = useCallback(async (q: string) => {
    const local = findSystem(q);
    if (local) return local;
    const rows = await searchSystems(q, 10);
    if (rows.length) {
      setSystemOptions((prev) => {
        const ids = new Set(prev.map((p) => p.system_id));
        return [...prev, ...rows.filter((r) => !ids.has(r.system_id))];
      });
    }
    const needle = q.trim().toLowerCase();
    return rows.find((s) => s.name.toLowerCase() === needle) ?? rows.find((s) => s.name.toLowerCase().includes(needle));
  }, [findSystem]);

  useEffect(() => {
    void searchSystems("", 60).then(setSystemOptions);
  }, []);

  useEffect(() => {
    const q = originQ.trim();
    if (q.length < 2) return;
    const t = window.setTimeout(() => {
      void searchSystems(q, 20).then((rows) => {
        if (!rows.length) return;
        setSystemOptions((prev) => {
          const ids = new Set(prev.map((p) => p.system_id));
          return [...prev, ...rows.filter((r) => !ids.has(r.system_id))];
        });
      });
    }, 250);
    return () => window.clearTimeout(t);
  }, [originQ, destQ]);

  const allDocks: DockLocation[] = useMemo(
    () => [...(dockData?.npc_stations ?? []), ...(dockData?.structures ?? [])],
    [dockData]
  );

  const toggleWaypoint = (systemId: number) => {
    setWaypointIds((prev) => (prev.includes(systemId) ? prev.filter((id) => id !== systemId) : [...prev, systemId]));
  };

  const planStargateRoute = async () => {
    const o = await resolveSystem(originQ);
    const d = await resolveSystem(destQ);
    if (!o || !d) return;
    setDestSystemId(d.system_id);
    setLoading(true);
    setJumpResult(null);
    try {
      const res = await fetch("/api/tools/map/route", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          origin_system_id: o.system_id,
          destination_system_id: d.system_id,
          avoid_low_sec: avoidLow,
          waypoint_system_ids: waypointIds,
        }),
      });
      setRouteResult(await res.json());
    } finally {
      setLoading(false);
    }
  };

  const planJumpRoute = async () => {
    const o = await resolveSystem(originQ);
    const d = await resolveSystem(destQ);
    if (!o || !d) return;
    setDestSystemId(d.system_id);
    const ship = jumpShips.find((s) => s.slug === shipSlug);
    setLoading(true);
    setRouteResult(null);
    try {
      const res = await fetch("/api/map/jump-route", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          origin: o.name,
          destination: d.name,
          ship_slug: shipSlug,
          jump_drive_calibration: calibration,
          jump_fuel_conservation: conservation,
          jump_freighters: ship?.is_jump_freighter ? jumpFreighters : 0,
        }),
      });
      setJumpResult(await res.json());
    } finally {
      setLoading(false);
    }
  };

  const applyBookmark = useCallback(async (b: RouteBookmark) => {
    setOriginQ(b.origin_system);
    setDestQ(b.destination_system);
    setWaypointIds(b.waypoint_system_ids ?? []);
    setMode(b.route_mode === "jump" ? "jump" : "stargate");
    const payload = b.payload ?? {};
    if (typeof payload.avoid_low_sec === "boolean") setAvoidLow(payload.avoid_low_sec);
    if (typeof payload.ship_slug === "string") setShipSlug(payload.ship_slug);
    if (typeof payload.jump_drive_calibration === "number") setCalibration(payload.jump_drive_calibration);
    if (typeof payload.jump_fuel_conservation === "number") setConservation(payload.jump_fuel_conservation);
    if (b.share_url) setLastShareUrl(b.share_url);
    if (b.origin_system_id && b.destination_system_id) {
      setDestSystemId(b.destination_system_id);
      if (b.route_mode === "jump") {
        setLoading(true);
        try {
          const res = await fetch("/api/tools/map/jump-plan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              ship_slug: payload.ship_slug ?? shipSlug,
              origin_system_id: b.origin_system_id,
              destination_system_id: b.destination_system_id,
              jump_drive_calibration: payload.jump_drive_calibration ?? calibration,
              jump_fuel_conservation: payload.jump_fuel_conservation ?? conservation,
              jump_freighters: payload.jump_freighters ?? jumpFreighters,
            }),
          });
          setJumpResult(await res.json());
          setRouteResult(null);
        } finally {
          setLoading(false);
        }
      } else {
        setLoading(true);
        try {
          const res = await fetch("/api/tools/map/route", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              origin_system_id: b.origin_system_id,
              destination_system_id: b.destination_system_id,
              avoid_low_sec: payload.avoid_low_sec ?? avoidLow,
              waypoint_system_ids: b.waypoint_system_ids ?? [],
            }),
          });
          setRouteResult(await res.json());
          setJumpResult(null);
        } finally {
          setLoading(false);
        }
      }
    }
  }, [avoidLow, calibration, conservation, jumpFreighters, shipSlug]);

  useEffect(() => {
    const token = searchParams.get("route");
    if (!token) return;
    void (async () => {
      const res = await fetch(`/api/tools/routes/share/${encodeURIComponent(token)}`, { cache: "no-store" });
      if (res.ok) await applyBookmark(await res.json());
    })();
  }, [searchParams, applyBookmark]);

  const saveRoute = async () => {
    const o = await resolveSystem(originQ);
    const d = await resolveSystem(destQ);
    if (!o || !d) return;
    const active = mode === "jump" ? jumpResult : routeResult;
    if (!active || active.error) return;

    const payload =
      mode === "jump"
        ? {
            ship_slug: shipSlug,
            jump_drive_calibration: calibration,
            jump_fuel_conservation: conservation,
            jump_freighters: jumpFreighters,
            jump_result: jumpResult,
          }
        : { avoid_low_sec: avoidLow, waypoint_system_ids: waypointIds, route_result: routeResult };

    const res = await fetch("/api/tools/routes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: saveName.trim() || `${originQ} → ${destQ}`,
        origin_system: o.name,
        destination_system: d.name,
        origin_system_id: o.system_id,
        destination_system_id: d.system_id,
        jumps: mode === "jump" ? jumpResult?.jumps ?? 0 : routeResult?.jumps ?? 0,
        route_mode: mode,
        visibility: saveVisibility,
        security_max: avoidLow ? 0.5 : 1.0,
        route_names: mode === "jump" ? jumpResult?.systems?.map((s) => s.name) ?? [] : routeResult?.route ?? [],
        waypoint_system_ids: waypointIds,
        payload,
        owner_character_id: authMe?.character_id ?? dockData?.character_id ?? null,
        owner_character_name: authMe?.character_name ?? "",
        corporation_id: dockData?.corporation_id ?? null,
        alliance_id: dockData?.alliance_id ?? null,
      }),
    });
    if (res.ok) {
      const saved: RouteBookmark = await res.json();
      setLastShareUrl(saved.share_url);
      await refreshBookmarks(authMe?.character_id);
    }
  };

  const calcRange = async () => {
    const o = await resolveSystem(originQ);
    if (!o) return;
    setLoading(true);
    try {
      if (mode === "stargate") {
        const res = await fetch("/api/tools/map/jump-range", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ origin_system_id: o.system_id, jump_range: stargateRange }),
        });
        const data = await res.json();
        setRangeResult({
          systems: data.systems ?? [],
        });
      } else {
        const res = await fetch("/api/tools/map/jump-drive-range", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ship_slug: shipSlug,
            origin_system_id: o.system_id,
            jump_drive_calibration: calibration,
          }),
        });
        const data = await res.json();
        setRangeResult({
          effective_range_ly: data.effective_range_ly,
          systems: data.systems ?? [],
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const selectedShip = jumpShips.find((s) => s.slug === shipSlug);
  const origin = findSystem(originQ);

  const routeIds = useMemo(() => {
    if (jumpResult?.systems) return jumpResult.systems.map((s) => s.system_id);
    if (routeResult?.systems) return routeResult.systems.map((s) => s.system_id);
    return [];
  }, [jumpResult, routeResult]);

  const rangeSystemIds = useMemo(() => {
    if (!rangeResult?.systems?.length) return [];
    return rangeResult.systems.map((s) => s.system_id);
  }, [rangeResult]);

  const rangeDistancesLy = useMemo(() => {
    const map = new Map<number, number>();
    for (const s of rangeResult?.systems ?? []) {
      if (typeof s.distance_ly === "number") map.set(s.system_id, s.distance_ly);
    }
    return map;
  }, [rangeResult]);

  const activitySystemIds = useMemo(() => {
    if (jumpResult?.systems) return jumpResult.systems.map((s) => s.system_id);
    if (routeResult?.systems) return routeResult.systems.map((s) => s.system_id);
    return [];
  }, [jumpResult, routeResult]);

  const mapWaypoints: MapWaypoint[] = useMemo(
    () =>
      allDocks
        .filter((d) => d.system_id && waypointIds.includes(d.system_id))
        .map((d) => ({
          id: d.id,
          system_id: d.system_id,
          label: d.label,
          kind: d.kind,
        })),
    [allDocks, waypointIds]
  );

  useEffect(() => {
    if (!activitySystemIds.length) {
      setActivity(null);
      return;
    }
    void (async () => {
      const res = await fetch("/api/tools/map/activity", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ system_ids: activitySystemIds }),
      });
      if (res.ok) setActivity(await res.json());
    })();
  }, [activitySystemIds]);

  useEffect(() => {
    setRouteResult(null);
    setJumpResult(null);
    setRangeResult(null);
    setActivity(null);
    if (mode === "browse") {
      setBrowseSelected(null);
      setMapFocusRequest({ ids: [], nonce: Date.now() });
    } else {
      setMapFocusRequest(undefined);
    }
  }, [mode]);

  const canSave = Boolean(
    (mode === "stargate" && routeResult && !routeResult.error) || (mode === "jump" && jumpResult && !jumpResult.error)
  );

  return (
    <DesktopSurface embedded={embedded} className="min-h-0 flex-1">
      <EveWindow id="map-visual" title="Route Map" defaultX={16} defaultY={16} defaultWidth={720} defaultHeight={680}>
        <StatusStrip>
          {authMe?.authenticated ? (
            <>Pilot: {authMe.character_name} · </>
          ) : (
            <>Guest mode — NPC hubs only · </>
          )}
          {mapStatus?.layout_ready
            ? `${mapStatus.systems_with_layout?.toLocaleString() ?? mapStatus.systems_with_coords.toLocaleString()} systems (clustered atlas)`
            : mapStatus?.full_sde_loaded
              ? `${mapStatus.systems_with_coords.toLocaleString()} systems (full SDE)`
              : mapStatus?.jump_drive_ready
                ? `${mapStatus.systems_with_coords} systems with coords`
                : "Partial map — mount SDE for full coverage"}
        </StatusStrip>

        <div className="flex flex-wrap gap-1 mb-2">
          <button type="button" className={`eve-btn ${mode === "browse" ? "eve-btn-primary" : ""}`} onClick={() => setMode("browse")}>
            Map browser
          </button>
          <button type="button" className={`eve-btn ${mode === "stargate" ? "eve-btn-primary" : ""}`} onClick={() => setMode("stargate")}>
            Stargate route
          </button>
          <button type="button" className={`eve-btn ${mode === "jump" ? "eve-btn-primary" : ""}`} onClick={() => setMode("jump")}>
            Jump drive
          </button>
        </div>

        {mode === "browse" ? (
          <MapBrowserPanel
            atlas={atlas}
            selectedSystem={browseSelected}
            onSelectSystem={setBrowseSelected}
            onFocusSystemIds={(ids) => setMapFocusRequest({ ids, nonce: Date.now() })}
            onUseAsOrigin={(name) => {
              setOriginQ(name);
              setMode("stargate");
            }}
            onUseAsDestination={(name) => {
              setDestQ(name);
              setMode("stargate");
            }}
          />
        ) : null}

        <EveMapCanvas
          atlas={atlas}
          atlasLoading={atlasLoading}
          routeSystemIds={mode === "browse" ? [] : routeIds}
          rangeSystemIds={mode === "browse" ? [] : rangeSystemIds}
          jumpLegs={mode === "browse" ? [] : (jumpResult?.legs ?? [])}
          waypoints={mode === "browse" ? [] : mapWaypoints}
          jumpRangeLy={mode === "browse" ? undefined : (jumpResult?.effective_range_ly ?? rangeResult?.effective_range_ly)}
          rangeDistancesLy={mode === "browse" ? undefined : rangeDistancesLy}
          originSystemId={mode === "browse" ? undefined : origin?.system_id}
          destinationSystemId={mode === "browse" ? undefined : destSystemId}
          selectedSystemId={browseSelected?.system_id}
          focusRequest={mode === "browse" ? mapFocusRequest : undefined}
          browseMode={mode === "browse"}
          onSystemClick={mode === "browse" ? setBrowseSelected : undefined}
          mode={mode === "jump" ? "jump" : "stargate"}
          height={mode === "browse" ? 440 : 380}
        />

        {mode !== "browse" ? (
        <>
        <div className="grid grid-cols-2 gap-2 mt-2 mb-2">
          <label className="flex flex-col gap-0.5">
            <span className="text-[var(--text-muted)]">From</span>
            <input className="eve-input" list="system-list" value={originQ} onChange={(e) => setOriginQ(e.target.value)} />
          </label>
          <label className="flex flex-col gap-0.5">
            <span className="text-[var(--text-muted)]">To</span>
            <input className="eve-input" list="system-list" value={destQ} onChange={(e) => setDestQ(e.target.value)} />
          </label>
        </div>
        <datalist id="system-list">
          {systemOptions.map((s) => (
            <option key={s.system_id} value={s.name} />
          ))}
        </datalist>

        {mode === "stargate" ? (
          <>
            <label className="flex items-center gap-2 mb-2">
              <input type="checkbox" checked={avoidLow} onChange={(e) => setAvoidLow(e.target.checked)} />
              <span>Avoid low-sec (high-sec only)</span>
            </label>

            <SectionHead>Dock via (recalculate route)</SectionHead>
            <p className="text-[var(--text-muted)] text-[0.85em] mb-1">
              {dockData?.note ?? "Select docking locations to force the route through those systems."}
            </p>
            <div className="eve-route-dock-list mb-2">
              {allDocks.length === 0 ? (
                <p className="text-[var(--text-muted)]">Loading dock locations…</p>
              ) : (
                allDocks.map((d) => (
                  <label key={d.id} className="eve-route-dock-item">
                    <input
                      type="checkbox"
                      checked={waypointIds.includes(d.system_id)}
                      onChange={() => toggleWaypoint(d.system_id)}
                    />
                    <span>
                      <strong>{d.system_name}</strong> — {d.label}
                      <span className="text-[var(--text-muted)]"> ({d.kind === "structure" ? "structure" : "NPC"})</span>
                    </span>
                  </label>
                ))
              )}
            </div>

            <button type="button" className="eve-btn eve-btn-primary mr-2" disabled={loading} onClick={planStargateRoute}>
              {waypointIds.length ? "Recalculate via docks" : "Plan stargate route"}
            </button>
            <label className="inline-flex items-center gap-1 text-[var(--text-muted)]">
              Gate jumps
              <input className="eve-input w-14" type="number" min={1} max={20} value={stargateRange} onChange={(e) => setStargateRange(Number(e.target.value))} />
              <button type="button" className="eve-btn" disabled={loading} onClick={calcRange}>
                Show range
              </button>
            </label>
            {routeResult && !routeResult.error ? (
              <div className="mt-2">
                <KpiStrip>
                  <KpiTile label="Stargate jumps" value={String(routeResult.jumps)} tone="accent" />
                  {waypointIds.length ? <KpiTile label="Dock stops" value={String(waypointIds.length)} tone="ok" /> : null}
                </KpiStrip>
                <p className="mt-1">{routeResult.route.join(" → ")}</p>
                {activity?.systems?.length ? (
                  <RouteActivityTable
                    rows={activity.systems}
                    partial={activity.partial}
                    hoursAvailable={activity.hours_available}
                  />
                ) : null}
              </div>
            ) : routeResult?.error ? (
              <p className="text-[var(--danger)] mt-2">{routeResult.message ?? "No stargate route found"}</p>
            ) : null}
          </>
        ) : (
          <>
            <div className="flex flex-wrap gap-2 mb-2 items-end">
              <label className="text-[var(--text-muted)]">
                Ship
                <select className="eve-select ml-1" value={shipSlug} onChange={(e) => setShipSlug(e.target.value)}>
                  {jumpShips.map((s) => (
                    <option key={s.slug} value={s.slug}>
                      {s.name} ({s.base_range_ly} ly base)
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-[var(--text-muted)]">
                JDC
                <select className="eve-select ml-1 w-14" value={calibration} onChange={(e) => setCalibration(Number(e.target.value))}>
                  {[0, 1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </label>
              <label className="text-[var(--text-muted)]">
                JFC
                <select className="eve-select ml-1 w-14" value={conservation} onChange={(e) => setConservation(Number(e.target.value))}>
                  {[0, 1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </label>
              {selectedShip?.is_jump_freighter ? (
                <label className="text-[var(--text-muted)]">
                  JF
                  <select className="eve-select ml-1 w-14" value={jumpFreighters} onChange={(e) => setJumpFreighters(Number(e.target.value))}>
                    {[0, 1, 2, 3, 4, 5].map((n) => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                </label>
              ) : null}
            </div>
            {selectedShip ? (
              <p className="text-[var(--text-muted)] mb-2">
                {selectedShip.fuel_type} · {selectedShip.fuel_per_ly.toLocaleString()} units/ly · JDC {calibration} range{" "}
                {(selectedShip.base_range_ly * (1 + 0.2 * calibration)).toFixed(1)} ly
              </p>
            ) : null}
            <button type="button" className="eve-btn eve-btn-primary mr-2" disabled={loading} onClick={planJumpRoute}>
              Plan jump route
            </button>
            <button type="button" className="eve-btn" disabled={loading} onClick={calcRange}>
              Show jump range
            </button>
            {jumpResult && !jumpResult.error ? (
              <div className="mt-2">
                <KpiStrip>
                  <KpiTile label="Jump hops" value={String(jumpResult.jumps)} tone="accent" />
                  <KpiTile label="Route distance" value={`${jumpResult.total_distance_ly} ly`} />
                  <KpiTile label="Total fuel" value={`${jumpResult.total_fuel.toLocaleString()} ${jumpResult.fuel_type}`} tone="ok" />
                </KpiStrip>
                {jumpResult.legs?.length ? (
                  <div className="mt-2 space-y-1">
                    {jumpResult.legs.map((leg, i) => (
                      <p key={i} className="text-[11px] text-[var(--text-muted)]">
                        {i + 1}. {leg.from_name} → {leg.to_name} · {leg.distance_ly} ly · {leg.fuel.toLocaleString()} fuel
                      </p>
                    ))}
                  </div>
                ) : null}
                {jumpResult.waypoint_string ? (
                  <div className="mt-2">
                    <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)] mb-1">Waypoint string</p>
                    <textarea
                      className="eve-input w-full font-mono text-[10px] min-h-[72px]"
                      readOnly
                      value={jumpResult.waypoint_string}
                    />
                    <button
                      type="button"
                      className="eve-btn-sm mt-1"
                      onClick={() => void navigator.clipboard.writeText(jumpResult.waypoint_string ?? "")}
                    >
                      Copy waypoints
                    </button>
                  </div>
                ) : null}
                {activity?.systems?.length ? (
                  <RouteActivityTable
                    rows={activity.systems}
                    partial={activity.partial}
                    hoursAvailable={activity.hours_available}
                  />
                ) : null}
              </div>
            ) : jumpResult?.error ? (
              <p className="text-[var(--danger)] mt-2">{jumpResult.message ?? "No jump route found"}</p>
            ) : null}
          </>
        )}

        </>
        ) : null}

        {mode !== "browse" && canSave ? (
          <div className="mt-3 pt-2 border-t border-[var(--edge-dim)]">
            <SectionHead>Save & share</SectionHead>
            <div className="flex flex-wrap gap-2 items-end mb-2">
              <label className="flex flex-col gap-0.5">
                <span className="text-[var(--text-muted)]">Name</span>
                <input className="eve-input" value={saveName} onChange={(e) => setSaveName(e.target.value)} placeholder={`${originQ} → ${destQ}`} />
              </label>
              <label className="text-[var(--text-muted)]">
                Visibility
                <select className="eve-select ml-1" value={saveVisibility} onChange={(e) => setSaveVisibility(e.target.value as typeof saveVisibility)}>
                  <option value="personal">Personal</option>
                  <option value="corp">Corporation</option>
                  <option value="alliance">Alliance</option>
                  <option value="link">Link only</option>
                </select>
              </label>
              <button type="button" className="eve-btn eve-btn-primary" onClick={saveRoute}>
                Save route
              </button>
            </div>
            {lastShareUrl ? (
              <p className="eve-route-share-url">
                Share: <a href={lastShareUrl}>{lastShareUrl}</a>
              </p>
            ) : null}
          </div>
        ) : null}
      </EveWindow>

      <EveWindow id="map-planner" title="Route Bookmarks" defaultX={748} defaultY={16} defaultWidth={360} defaultHeight={620}>
        <SectionHead>Saved routes</SectionHead>
        <ul className="space-y-1 mb-3">
          {bookmarks.length === 0 ? (
            <li className="text-[var(--text-muted)]">No saved routes visible.</li>
          ) : (
            bookmarks.map((b) => (
              <li key={b.id} className="border border-[var(--edge-dim)] p-2 cursor-pointer hover:border-[var(--link)]" onClick={() => void applyBookmark(b)}>
                <strong>{b.name}</strong>
                <div className="text-[0.85em]">
                  {b.origin_system} → {b.destination_system} · {b.jumps} {b.route_mode === "jump" ? "hops" : "jumps"}
                </div>
                <div className="text-[var(--text-muted)] text-[0.75em]">
                  {b.visibility}
                  {b.owner_character_name ? ` · ${b.owner_character_name}` : ""}
                </div>
                {b.share_url ? (
                  <a href={b.share_url} className="text-[0.75em] text-[var(--link)]" onClick={(e) => e.stopPropagation()}>
                    Share link
                  </a>
                ) : null}
              </li>
            ))
          )}
        </ul>
        <SectionHead>Skills reference</SectionHead>
        <ul className="text-[var(--text-muted)] space-y-1 text-[0.85em]">
          <li>Jump Drive Calibration — +20% range per level</li>
          <li>Jump Fuel Conservation — −10% fuel per level</li>
          <li>Jump Freighters — −10% fuel for JFs</li>
        </ul>
      </EveWindow>
    </DesktopSurface>
  );
}
