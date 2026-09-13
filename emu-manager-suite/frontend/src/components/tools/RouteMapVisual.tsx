"use client";

import { useMemo } from "react";

export type MapNode = {
  system_id: number;
  name: string;
  security: number;
  x: number;
  y: number;
};

export type MapEdge = {
  from_system_id: number;
  to_system_id: number;
};

export type MapWaypoint = {
  id: string;
  system_id: number;
  label: string;
  kind: "npc_station" | "structure";
};

type RouteMapVisualProps = {
  nodes: MapNode[];
  stargateEdges?: MapEdge[];
  routeSystemIds?: number[];
  jumpLegs?: { from_system_id: number; to_system_id: number; distance_ly?: number; fuel?: number }[];
  waypoints?: MapWaypoint[];
  jumpRangeLy?: number;
  originSystemId?: number;
  destinationSystemId?: number;
  mode?: "stargate" | "jump";
  height?: number;
};

function secColor(sec: number): string {
  if (sec >= 0.5) return "var(--ok)";
  if (sec >= 0.0) return "var(--warn)";
  return "var(--danger)";
}

function secGlow(sec: number): string {
  if (sec >= 0.5) return "rgba(72, 187, 120, 0.45)";
  if (sec >= 0.0) return "rgba(234, 179, 8, 0.45)";
  return "rgba(239, 68, 68, 0.45)";
}

export function RouteMapVisual({
  nodes,
  stargateEdges = [],
  routeSystemIds = [],
  jumpLegs = [],
  waypoints = [],
  jumpRangeLy,
  originSystemId,
  destinationSystemId,
  mode = "stargate",
  height = 320,
}: RouteMapVisualProps) {
  const layout = useMemo(() => {
    if (nodes.length === 0) return null;

    const pad = 44;
    const w = 560;
    const h = height;
    const xs = nodes.map((n) => n.x);
    const ys = nodes.map((n) => n.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const spanX = maxX - minX || 1;
    const spanY = maxY - minY || 1;

    const scale = Math.min((w - pad * 2) / spanX, (h - pad * 2) / spanY);
    const toPx = (n: MapNode) => ({
      x: pad + (n.x - minX) * scale,
      y: h - pad - (n.y - minY) * scale,
    });

    const pos = new Map(nodes.map((n) => [n.system_id, toPx(n)]));
    const routeSet = new Set(routeSystemIds);

    return { w, h, pos, routeSet, pad, scale };
  }, [nodes, routeSystemIds, height]);

  if (!layout || nodes.length === 0) {
    return (
      <div className="eve-route-map eve-route-map--empty" style={{ height }}>
        <div className="eve-route-map-empty-inner">
          <span className="eve-route-map-empty-icon">◎</span>
          <p>Plan a route to see the tactical map</p>
        </div>
      </div>
    );
  }

  const { w, h, pos, routeSet } = layout;
  const nodeById = new Map(nodes.map((n) => [n.system_id, n]));

  const routeSegments = routeSystemIds.slice(0, -1).map((fromId, i) => {
    const toId = routeSystemIds[i + 1];
    const a = pos.get(fromId);
    const b = pos.get(toId);
    if (!a || !b) return null;
    const mx = (a.x + b.x) / 2;
    const my = (a.y + b.y) / 2;
    const angle = (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI;
    return { key: `${fromId}-${toId}`, a, b, mx, my, angle, hop: i + 1 };
  }).filter(Boolean) as {
    key: string;
    a: { x: number; y: number };
    b: { x: number; y: number };
    mx: number;
    my: number;
    angle: number;
    hop: number;
  }[];

  return (
    <div className="eve-route-map">
      <svg viewBox={`0 0 ${w} ${h}`} className="eve-route-map-svg" role="img" aria-label="Route map">
        <defs>
          <radialGradient id="eve-map-vignette" cx="50%" cy="50%" r="65%">
            <stop offset="0%" stopColor="rgba(30, 45, 60, 0.35)" />
            <stop offset="100%" stopColor="rgba(4, 6, 10, 0.92)" />
          </radialGradient>
          <filter id="eve-map-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="eve-route-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <marker id="eve-route-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" fill="var(--link-hi)" opacity="0.9" />
          </marker>
        </defs>

        <rect width={w} height={h} fill="url(#eve-map-vignette)" />
        <rect width={w} height={h} className="eve-route-map-grid" />

        {/* Jump range */}
        {mode === "jump" && jumpRangeLy && originSystemId && pos.has(originSystemId) ? (
          (() => {
            const o = pos.get(originSystemId)!;
            const sample = nodes.find((n) => n.system_id !== originSystemId);
            if (!sample) return null;
            const p = pos.get(sample.system_id)!;
            const node = nodeById.get(sample.system_id)!;
            const originNode = nodeById.get(originSystemId)!;
            const lyDist =
              Math.hypot(node.x - originNode.x, node.y - originNode.y) || 1;
            const pxDist = Math.hypot(p.x - o.x, p.y - o.y);
            const pxPerLy = pxDist / lyDist;
            const r = jumpRangeLy * pxPerLy;
            return (
              <>
                <circle cx={o.x} cy={o.y} r={r + 6} className="eve-route-map-range-outer" />
                <circle cx={o.x} cy={o.y} r={r} className="eve-route-map-range" />
              </>
            );
          })()
        ) : null}

        {/* Background stargate mesh */}
        {stargateEdges.map((e, i) => {
          const a = pos.get(e.from_system_id);
          const b = pos.get(e.to_system_id);
          if (!a || !b) return null;
          const onRoute = routeSet.has(e.from_system_id) && routeSet.has(e.to_system_id);
          return (
            <line
              key={`sg-${i}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              className={onRoute ? "eve-route-map-edge eve-route-map-edge--route-bg" : "eve-route-map-edge"}
            />
          );
        })}

        {/* Jump legs */}
        {jumpLegs.map((leg, i) => {
          const a = pos.get(leg.from_system_id);
          const b = pos.get(leg.to_system_id);
          if (!a || !b) return null;
          return (
            <g key={`jp-${i}`} filter="url(#eve-route-glow)">
              <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="eve-route-map-jump" />
              <title>
                {leg.distance_ly != null ? `${leg.distance_ly} ly` : ""}
                {leg.fuel != null ? ` · ${leg.fuel} fuel` : ""}
              </title>
            </g>
          );
        })}

        {/* Active route with arrows */}
        {routeSegments.map((seg) => (
          <g key={seg.key} filter="url(#eve-route-glow)">
            <line
              x1={seg.a.x}
              y1={seg.a.y}
              x2={seg.b.x}
              y2={seg.b.y}
              className="eve-route-map-edge eve-route-map-edge--route"
              markerEnd="url(#eve-route-arrow)"
            />
            <circle cx={seg.mx} cy={seg.my} r={8} className="eve-route-map-hop" />
            <text x={seg.mx} y={seg.my + 3} textAnchor="middle" className="eve-route-map-hop-label">
              {seg.hop}
            </text>
          </g>
        ))}

        {/* Waypoint docks */}
        {waypoints.map((wp) => {
          const p = pos.get(wp.system_id);
          if (!p) return null;
          return (
            <g key={wp.id} className="eve-route-map-waypoint">
              <polygon
                points={`${p.x},${p.y - 11} ${p.x + 9},${p.y + 7} ${p.x - 9},${p.y + 7}`}
                className={wp.kind === "structure" ? "eve-route-map-waypoint-shape--structure" : "eve-route-map-waypoint-shape--npc"}
              />
              <title>{wp.label}</title>
            </g>
          );
        })}

        {/* System nodes */}
        {nodes.map((n) => {
          const p = pos.get(n.system_id);
          if (!p) return null;
          const active = routeSet.has(n.system_id);
          const isOrigin = n.system_id === originSystemId;
          const isDest = n.system_id === destinationSystemId;
          const r = active ? 8 : 5.5;
          return (
            <g key={n.system_id} className="eve-route-map-node" filter={active ? "url(#eve-map-glow)" : undefined}>
              {active ? (
                <circle cx={p.x} cy={p.y} r={r + 4} fill={secGlow(n.security)} opacity="0.35" />
              ) : null}
              <circle
                cx={p.x}
                cy={p.y}
                r={r}
                fill={secColor(n.security)}
                className={
                  isOrigin
                    ? "eve-route-map-node-dot eve-route-map-node-dot--origin"
                    : isDest
                      ? "eve-route-map-node-dot eve-route-map-node-dot--dest"
                      : active
                        ? "eve-route-map-node-dot eve-route-map-node-dot--active"
                        : "eve-route-map-node-dot"
                }
              />
              {(active || isOrigin || isDest) && (
                <text x={p.x} y={p.y - r - 6} textAnchor="middle" className="eve-route-map-label eve-route-map-label--active">
                  {n.name.length > 14 ? `${n.name.slice(0, 12)}…` : n.name}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
