/** Preloaded EVE map atlas (clustered layout positions + stargate edges). */

/** Rotate layout 180° counter-clockwise for in-game map orientation. */
export function mapDisplayCoord(x: number, y: number): { x: number; y: number } {
  return { x: -x, y: -y };
}

export type AtlasSystem = {
  system_id: number;
  name: string;
  security: number;
  x: number;
  y: number;
  region_name: string;
  constellation_name: string;
};

export type AtlasGroup = {
  key: string;
  name: string;
  region_name: string;
  cx: number;
  cy: number;
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
  count: number;
};

export type MapAtlas = {
  version: number;
  systems: AtlasSystem[];
  systemsById: Map<number, AtlasSystem>;
  edges: [number, number][];
  adjacency: Map<number, number[]>;
  bounds: { minX: number; minY: number; maxX: number; maxY: number };
  system_count: number;
  edge_count: number;
  regions: AtlasGroup[];
  constellations: AtlasGroup[];
};

type AtlasPayload = {
  version?: number;
  systems?: unknown[];
  edges?: unknown[];
  system_count?: number;
  edge_count?: number;
};

function parseSystem(row: unknown): AtlasSystem | null {
  if (!Array.isArray(row) || row.length < 5) return null;
  const [system_id, name, security, x, y, region_name, constellation_name] = row;
  if (typeof system_id !== "number") return null;
  const raw = mapDisplayCoord(Number(x ?? 0), Number(y ?? 0));
  return {
    system_id,
    name: String(name ?? system_id),
    security: Number(security ?? 0),
    x: raw.x,
    y: raw.y,
    region_name: String(region_name ?? ""),
    constellation_name: String(constellation_name ?? ""),
  };
}

export function parseMapAtlas(payload: AtlasPayload): MapAtlas | null {
  const systems: AtlasSystem[] = [];
  const systemsById = new Map<number, AtlasSystem>();
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  for (const row of payload.systems ?? []) {
    const sys = parseSystem(row);
    if (!sys) continue;
    systems.push(sys);
    systemsById.set(sys.system_id, sys);
    minX = Math.min(minX, sys.x);
    minY = Math.min(minY, sys.y);
    maxX = Math.max(maxX, sys.x);
    maxY = Math.max(maxY, sys.y);
  }

  if (!systems.length) return null;
  if (!Number.isFinite(minX)) {
    minX = minY = 0;
    maxX = maxY = 1;
  }

  const adjacency = new Map<number, number[]>();
  const edges: [number, number][] = [];
  for (const row of payload.edges ?? []) {
    if (!Array.isArray(row) || row.length < 2) continue;
    const from = Number(row[0]);
    const to = Number(row[1]);
    if (!systemsById.has(from) || !systemsById.has(to)) continue;
    edges.push([from, to]);
    const fa = adjacency.get(from) ?? [];
    fa.push(to);
    adjacency.set(from, fa);
    const ta = adjacency.get(to) ?? [];
    ta.push(from);
    adjacency.set(to, ta);
  }

  return {
    version: payload.version ?? 1,
    systems,
    systemsById,
    edges,
    adjacency,
    bounds: { minX, minY, maxX, maxY },
    system_count: payload.system_count ?? systems.length,
    edge_count: payload.edge_count ?? edges.length,
    ...buildAtlasGroups(systems),
  };
}

function foldGroup(
  map: Map<string, AtlasGroup>,
  key: string,
  name: string,
  regionName: string,
  sys: AtlasSystem
) {
  const g = map.get(key);
  if (!g) {
    map.set(key, {
      key,
      name,
      region_name: regionName,
      cx: sys.x,
      cy: sys.y,
      minX: sys.x,
      minY: sys.y,
      maxX: sys.x,
      maxY: sys.y,
      count: 1,
    });
    return;
  }
  g.count += 1;
  g.cx += sys.x;
  g.cy += sys.y;
  g.minX = Math.min(g.minX, sys.x);
  g.minY = Math.min(g.minY, sys.y);
  g.maxX = Math.max(g.maxX, sys.x);
  g.maxY = Math.max(g.maxY, sys.y);
}

export function buildAtlasGroups(systems: AtlasSystem[]): {
  regions: AtlasGroup[];
  constellations: AtlasGroup[];
} {
  const regionMap = new Map<string, AtlasGroup>();
  const constMap = new Map<string, AtlasGroup>();

  for (const sys of systems) {
    const regionName = sys.region_name || "Unknown Region";
    const constName = sys.constellation_name || "Unknown Constellation";
    foldGroup(regionMap, regionName, regionName, regionName, sys);
    foldGroup(constMap, `${regionName}::${constName}`, constName, regionName, sys);
  }

  const finalize = (groups: AtlasGroup[]) => {
    for (const g of groups) {
      g.cx /= g.count;
      g.cy /= g.count;
    }
    return groups.sort((a, b) => b.count - a.count);
  };

  return {
    regions: finalize([...regionMap.values()]),
    constellations: finalize([...constMap.values()]),
  };
}

let atlasCache: MapAtlas | null = null;
let atlasPromise: Promise<MapAtlas | null> | null = null;

export async function loadMapAtlas(): Promise<MapAtlas | null> {
  if (atlasCache) return atlasCache;
  if (atlasPromise) return atlasPromise;

  atlasPromise = (async () => {
    const res = await fetch("/api/tools/map/atlas", { cache: "no-store" });
    if (!res.ok) return null;
    const data = await res.json();
    if (atlasCache && atlasNeedsRefresh(data)) {
      atlasCache = null;
    }
    atlasCache = parseMapAtlas(data);
    return atlasCache;
  })();

  return atlasPromise;
}

export function atlasSystemToNode(sys: AtlasSystem) {
  return {
    system_id: sys.system_id,
    name: sys.name,
    security: sys.security,
    x: sys.x,
    y: sys.y,
  };
}

export function systemIdsInRegion(atlas: MapAtlas, regionName: string): number[] {
  if (!regionName) return [];
  return atlas.systems.filter((s) => s.region_name === regionName).map((s) => s.system_id);
}

export function systemIdsInConstellation(atlas: MapAtlas, constellationName: string, regionName?: string): number[] {
  if (!constellationName) return [];
  return atlas.systems
    .filter(
      (s) =>
        s.constellation_name === constellationName &&
        (!regionName || s.region_name === regionName)
    )
    .map((s) => s.system_id);
}

export function expandWithNeighbors(atlas: MapAtlas, systemIds: number[], hops = 1): Set<number> {
  const out = new Set(systemIds);
  let frontier = [...systemIds];
  for (let h = 0; h < hops; h++) {
    const next: number[] = [];
    for (const sid of frontier) {
      for (const n of atlas.adjacency.get(sid) ?? []) {
        if (!out.has(n)) {
          out.add(n);
          next.push(n);
        }
      }
    }
    frontier = next;
  }
  return out;
}

export function boundsForSystems(atlas: MapAtlas, systemIds: number[], padding = 60) {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const sid of systemIds) {
    const s = atlas.systemsById.get(sid);
    if (!s) continue;
    minX = Math.min(minX, s.x);
    minY = Math.min(minY, s.y);
    maxX = Math.max(maxX, s.x);
    maxY = Math.max(maxY, s.y);
  }
  if (!Number.isFinite(minX)) return atlas.bounds;
  return {
    minX: minX - padding,
    minY: minY - padding,
    maxX: maxX + padding,
    maxY: maxY + padding,
  };
}

/** True when route systems share essentially the same map position. */
export function positionsAreDegenerate(systemIds: number[], atlas: MapAtlas): boolean {
  if (systemIds.length < 2) return false;
  const pts = systemIds
    .map((id) => atlas.systemsById.get(id))
    .filter((s): s is AtlasSystem => Boolean(s));
  if (pts.length < 2) return true;
  const first = pts[0];
  return pts.every((p) => Math.hypot(p.x - first.x, p.y - first.y) < 2);
}

/** Snake layout for a planned route when atlas coords are missing or collapsed. */
export function layoutRouteChain(
  routeIds: number[],
  atlas: MapAtlas | null,
  spacing = 44
): Map<number, { x: number; y: number }> {
  const out = new Map<number, { x: number; y: number }>();
  if (!routeIds.length) return out;

  let baseX = 0;
  let baseY = 0;
  if (atlas) {
    for (const id of routeIds) {
      const s = atlas.systemsById.get(id);
      if (s && (Math.abs(s.x) > 1 || Math.abs(s.y) > 1)) {
        baseX = s.x;
        baseY = s.y;
        break;
      }
    }
  }

  const cols = 6;
  routeIds.forEach((id, i) => {
    const row = Math.floor(i / cols);
    const col = i % cols;
    const flip = row % 2 === 1;
    const c = flip ? cols - 1 - col : col;
    out.set(id, {
      x: baseX + c * spacing + row * 18,
      y: baseY + row * spacing * 0.9,
    });
  });
  return out;
}

export function buildPositionMap(
  atlas: MapAtlas | null,
  routeIds: number[],
  rangeIds: number[] = []
): Map<number, { x: number; y: number; security: number; name: string }> {
  const out = new Map<number, { x: number; y: number; security: number; name: string }>();
  if (!atlas) return out;

  for (const sys of atlas.systems) {
    out.set(sys.system_id, { x: sys.x, y: sys.y, security: sys.security, name: sys.name });
  }

  const focusIds = [...new Set([...routeIds, ...rangeIds])];
  if (focusIds.length && positionsAreDegenerate(focusIds, atlas)) {
    const chain = layoutRouteChain(routeIds.length ? routeIds : focusIds, atlas);
    for (const [id, pos] of chain) {
      const sys = atlas.systemsById.get(id);
      out.set(id, {
        x: pos.x,
        y: pos.y,
        security: sys?.security ?? 0,
        name: sys?.name ?? String(id),
      });
    }
  }

  return out;
}

export function invalidateMapAtlasCache() {
  atlasCache = null;
  atlasPromise = null;
}

/** Drop cached atlas when server bumps layout version. */
export function atlasNeedsRefresh(payload: { version?: number }) {
  if (!atlasCache) return false;
  return (payload.version ?? 1) > (atlasCache.version ?? 1);
}
