"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { boundsForSystems, buildPositionMap, expandWithNeighbors, layoutRouteChain, positionsAreDegenerate, type AtlasGroup, type AtlasSystem, type MapAtlas } from "@/lib/mapAtlas";
import type { MapWaypoint } from "./RouteMapVisual";

type JumpLeg = {
  from_system_id: number;
  to_system_id: number;
  distance_ly?: number;
  fuel?: number;
};

type ViewTransform = { scale: number; tx: number; ty: number };

type EveMapCanvasProps = {
  atlas: MapAtlas | null;
  atlasLoading?: boolean;
  routeSystemIds?: number[];
  rangeSystemIds?: number[];
  jumpLegs?: JumpLeg[];
  waypoints?: MapWaypoint[];
  jumpRangeLy?: number;
  rangeDistancesLy?: Map<number, number>;
  originSystemId?: number;
  destinationSystemId?: number;
  selectedSystemId?: number;
  focusRequest?: { ids: number[]; nonce: number };
  mode?: "stargate" | "jump";
  browseMode?: boolean;
  onSystemClick?: (sys: AtlasSystem) => void;
  height?: number;
};

function secColor(sec: number): string {
  if (sec >= 0.5) return "#48bb78";
  if (sec >= 0.0) return "#eab308";
  return "#ef4444";
}

function secGlow(sec: number): string {
  if (sec >= 0.5) return "rgba(72, 187, 120, 0.35)";
  if (sec >= 0.0) return "rgba(234, 179, 8, 0.35)";
  return "rgba(239, 68, 68, 0.35)";
}

function fitTransform(
  bounds: { minX: number; minY: number; maxX: number; maxY: number },
  width: number,
  height: number,
  pad = 48
): ViewTransform {
  const spanX = bounds.maxX - bounds.minX || 1;
  const spanY = bounds.maxY - bounds.minY || 1;
  const scale = Math.min((width - pad * 2) / spanX, (height - pad * 2) / spanY);
  const cx = (bounds.minX + bounds.maxX) / 2;
  const cy = (bounds.minY + bounds.maxY) / 2;
  return {
    scale,
    tx: width / 2 - cx * scale,
    ty: height / 2 + cy * scale,
  };
}

function worldToScreen(x: number, y: number, t: ViewTransform) {
  return { x: x * t.scale + t.tx, y: -y * t.scale + t.ty };
}

function screenToWorld(sx: number, sy: number, t: ViewTransform) {
  return { x: (sx - t.tx) / t.scale, y: -(sy - t.ty) / t.scale };
}

type MapLod = "region" | "constellation" | "local" | "detail";

function mapLod(scale: number): MapLod {
  if (scale < 0.18) return "region";
  if (scale < 0.55) return "constellation";
  if (scale < 1.1) return "local";
  return "detail";
}

function systemsForDraw(
  atlas: MapAtlas,
  t: ViewTransform,
  w: number,
  h: number,
  highlightIds: Set<number>,
  showAllNodes: boolean
): Set<number> {
  const out = new Set<number>(highlightIds);
  if (!showAllNodes) return out;

  const lod = mapLod(t.scale);
  if (lod === "region") return out;

  const cell = lod === "constellation" ? 30 : lod === "local" ? 18 : 12;
  const grid = new Map<string, number>();
  const margin = 48;

  for (const sys of atlas.systems) {
    if (highlightIds.has(sys.system_id)) continue;
    const screen = worldToScreen(sys.x, sys.y, t);
    if (screen.x < -margin || screen.x > w + margin || screen.y < -margin || screen.y > h + margin) continue;
    const key = `${Math.floor(screen.x / cell)},${Math.floor(screen.y / cell)}`;
    if (!grid.has(key)) grid.set(key, sys.system_id);
  }
  for (const id of grid.values()) out.add(id);
  return out;
}

type LabelRect = { x: number; y: number; w: number; h: number };

function labelsOverlap(a: LabelRect, b: LabelRect) {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

function drawAreaLabels(
  ctx: CanvasRenderingContext2D,
  groups: AtlasGroup[],
  t: ViewTransform,
  canvasW: number,
  canvasH: number,
  opts: {
    minSpan: number;
    fontSize: number;
    fontWeight: string;
    color: string;
    bg: string;
    border: string;
  }
) {
  const placed: LabelRect[] = [];
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  for (const g of groups) {
    const spanX = (g.maxX - g.minX) * t.scale;
    const spanY = (g.maxY - g.minY) * t.scale;
    if (Math.max(spanX, spanY) < opts.minSpan) continue;

    const c = worldToScreen(g.cx, g.cy, t);
    if (c.x < -100 || c.x > canvasW + 100 || c.y < -50 || c.y > canvasH + 50) continue;

    const label = g.name.length > 26 ? `${g.name.slice(0, 24)}…` : g.name;
    ctx.font = `${opts.fontWeight} ${opts.fontSize}px system-ui, sans-serif`;
    const tw = ctx.measureText(label).width;
    const padX = 7;
    const padY = 4;
    const bw = tw + padX * 2;
    const bh = opts.fontSize + padY * 2;
    const rect: LabelRect = { x: c.x - bw / 2, y: c.y - bh / 2, w: bw, h: bh };
    if (placed.some((p) => labelsOverlap(rect, p))) continue;
    placed.push(rect);

    ctx.fillStyle = opts.bg;
    ctx.strokeStyle = opts.border;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(rect.x, rect.y, rect.w, rect.h, 4);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = opts.color;
    ctx.fillText(label, c.x, c.y);
  }
}

function hitTestSystem(
  atlas: MapAtlas,
  positions: Map<number, { x: number; y: number }>,
  t: ViewTransform,
  sx: number,
  sy: number,
  drawIds: Set<number>,
  radius = 12
): AtlasSystem | null {
  let best: { sys: AtlasSystem; d: number } | null = null;
  for (const id of drawIds) {
    const sys = atlas.systemsById.get(id);
    const p = positions.get(id);
    if (!sys || !p) continue;
    const screen = worldToScreen(p.x, p.y, t);
    const d = Math.hypot(screen.x - sx, screen.y - sy);
    if (d <= radius && (!best || d < best.d)) best = { sys, d };
  }
  return best?.sys ?? null;
}

type HoverState = { sys: AtlasSystem; sx: number; sy: number };

export function EveMapCanvas({
  atlas,
  atlasLoading = false,
  routeSystemIds = [],
  rangeSystemIds = [],
  jumpLegs = [],
  waypoints = [],
  jumpRangeLy,
  rangeDistancesLy,
  originSystemId,
  destinationSystemId,
  selectedSystemId,
  focusRequest,
  mode = "stargate",
  browseMode = false,
  onSystemClick,
  height = 420,
}: EveMapCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [transform, setTransform] = useState<ViewTransform>({ scale: 1, tx: 0, ty: 0 });
  const [dragging, setDragging] = useState(false);
  const [hover, setHover] = useState<HoverState | null>(null);
  const dragRef = useRef<{ x: number; y: number; tx: number; ty: number } | null>(null);
  const dragMovedRef = useRef(false);
  const mouseRef = useRef<{ x: number; y: number } | null>(null);
  const drawIdsRef = useRef<Set<number>>(new Set());
  const hoverIdRef = useRef<number | null>(null);
  const transformRef = useRef(transform);
  transformRef.current = transform;

  const routeSet = useMemo(() => new Set(routeSystemIds), [routeSystemIds.join(",")]);
  const rangeSet = useMemo(() => new Set(rangeSystemIds), [rangeSystemIds.join(",")]);

  const positions = useMemo(
    () => buildPositionMap(atlas, routeSystemIds, rangeSystemIds),
    [atlas, routeSystemIds.join(","), rangeSystemIds.join(",")]
  );

  const pos = useCallback(
    (systemId: number) => positions.get(systemId) ?? null,
    [positions]
  );

  const fitBoundsForIds = useCallback(
    (ids: number[]) => {
      if (!atlas) return null;
      if (ids.length && positionsAreDegenerate(ids, atlas)) {
        const chain = layoutRouteChain(ids, atlas);
        let minX = Infinity;
        let minY = Infinity;
        let maxX = -Infinity;
        let maxY = -Infinity;
        for (const p of chain.values()) {
          minX = Math.min(minX, p.x);
          minY = Math.min(minY, p.y);
          maxX = Math.max(maxX, p.x);
          maxY = Math.max(maxY, p.y);
        }
        if (Number.isFinite(minX)) {
          const pad = 60;
          return { minX: minX - pad, minY: minY - pad, maxX: maxX + pad, maxY: maxY + pad };
        }
      }
      return boundsForSystems(atlas, ids, 90);
    },
    [atlas]
  );

  const applyFit = useCallback(
    (ids?: number[]) => {
      if (!atlas || !containerRef.current) return;
      const w = containerRef.current.clientWidth;
      const bounds = ids && ids.length ? fitBoundsForIds(ids) : atlas.bounds;
      if (!bounds) return;
      setTransform(fitTransform(bounds, w, height));
    },
    [atlas, height, fitBoundsForIds]
  );

  useEffect(() => {
    if (!atlas) return;
    if (focusRequest !== undefined) {
      const ids = focusRequest.ids;
      applyFit(ids.length ? (ids.length > 120 ? ids.slice(0, 120) : ids) : undefined);
      return;
    }
    if (routeSystemIds.length) {
      const expanded = [...expandWithNeighbors(atlas, routeSystemIds, 1)];
      applyFit(expanded);
    } else if (originSystemId && atlas.systemsById.has(originSystemId)) {
      applyFit([originSystemId]);
    } else if (!browseMode) {
      applyFit();
    }
  }, [atlas, routeSystemIds.join(","), originSystemId, focusRequest?.nonce, browseMode, applyFit]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const dpr = window.devicePixelRatio || 1;
    const w = container.clientWidth;
    const h = height;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const t = transformRef.current;

    const bg = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, Math.max(w, h) * 0.65);
    bg.addColorStop(0, "rgba(30, 45, 60, 0.35)");
    bg.addColorStop(1, "rgba(4, 6, 10, 0.95)");
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);

    ctx.strokeStyle = "rgba(255,255,255,0.03)";
    ctx.lineWidth = 1;
    const gridStep = 40;
    for (let gx = 0; gx < w; gx += gridStep) {
      ctx.beginPath();
      ctx.moveTo(gx, 0);
      ctx.lineTo(gx, h);
      ctx.stroke();
    }
    for (let gy = 0; gy < h; gy += gridStep) {
      ctx.beginPath();
      ctx.moveTo(0, gy);
      ctx.lineTo(w, gy);
      ctx.stroke();
    }

    if (!atlas) {
      ctx.fillStyle = "rgba(255,255,255,0.45)";
      ctx.font = "13px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(atlasLoading ? "Loading map atlas…" : "Map atlas unavailable", w / 2, h / 2);
      return;
    }

    const margin = 80;
    const visible = (wx: number, wy: number) => {
      const p = worldToScreen(wx, wy, t);
      return p.x >= -margin && p.x <= w + margin && p.y >= -margin && p.y <= h + margin;
    };

    const highlightIds = new Set<number>([...routeSystemIds, ...rangeSystemIds]);
    if (originSystemId) highlightIds.add(originSystemId);
    if (destinationSystemId) highlightIds.add(destinationSystemId);
    if (selectedSystemId) highlightIds.add(selectedSystemId);

    const showAllNodes = browseMode || (routeSystemIds.length === 0 && rangeSystemIds.length === 0);
    const lod = mapLod(t.scale);
    const drawIds = systemsForDraw(atlas, t, w, h, highlightIds, showAllNodes);
    drawIdsRef.current = drawIds;

    const drawEdges = lod !== "region" && t.scale >= 0.12;

    if (drawEdges) {
      for (const [from, to] of atlas.edges) {
        if (!drawIds.has(from) || !drawIds.has(to)) continue;
        const pa = pos(from);
        const pb = pos(to);
        if (!pa || !pb) continue;
        const onRoute = routeSet.has(from) && routeSet.has(to);
        const nearFocus = highlightIds.has(from) || highlightIds.has(to);
        if (!showAllNodes && !onRoute && !nearFocus) continue;
        if (!visible(pa.x, pa.y) && !visible(pb.x, pb.y)) continue;

        const p1 = worldToScreen(pa.x, pa.y, t);
        const p2 = worldToScreen(pb.x, pb.y, t);
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.strokeStyle = onRoute ? "rgba(100, 180, 255, 0.25)" : "rgba(255,255,255, 0.05)";
        ctx.lineWidth = onRoute ? 1.5 : 0.6;
        ctx.stroke();
      }
    }

    if (mode === "jump" && jumpRangeLy && originSystemId) {
      const origin = pos(originSystemId);
      if (origin) {
        let pxPerLy = 0;
        if (rangeDistancesLy && rangeDistancesLy.size) {
          for (const [sid, ly] of rangeDistancesLy) {
            if (sid === originSystemId || ly <= 0) continue;
            const other = pos(sid);
            if (!other) continue;
            const layoutDist = Math.hypot(other.x - origin.x, other.y - origin.y);
            if (layoutDist > 0) {
              pxPerLy = (layoutDist * t.scale) / ly;
              break;
            }
          }
        }
        if (!pxPerLy && jumpLegs.length) {
          const leg = jumpLegs.find((l) => l.distance_ly && l.distance_ly > 0);
          if (leg) {
            const a = pos(leg.from_system_id);
            const b = pos(leg.to_system_id);
            if (a && b) {
              const layoutDist = Math.hypot(b.x - a.x, b.y - a.y);
              pxPerLy = (layoutDist * t.scale) / (leg.distance_ly ?? 1);
            }
          }
        }
        if (pxPerLy > 0) {
          const po = worldToScreen(origin.x, origin.y, t);
          const r = jumpRangeLy * pxPerLy;
          ctx.beginPath();
          ctx.arc(po.x, po.y, r + 4, 0, Math.PI * 2);
          ctx.strokeStyle = "rgba(120, 200, 255, 0.15)";
          ctx.lineWidth = 2;
          ctx.stroke();
          ctx.beginPath();
          ctx.arc(po.x, po.y, r, 0, Math.PI * 2);
          ctx.strokeStyle = "rgba(120, 200, 255, 0.35)";
          ctx.setLineDash([6, 6]);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      }
    }

    for (const leg of jumpLegs) {
      const a = pos(leg.from_system_id);
      const b = pos(leg.to_system_id);
      if (!a || !b) continue;
      const pa = worldToScreen(a.x, a.y, t);
      const pb = worldToScreen(b.x, b.y, t);
      ctx.beginPath();
      ctx.moveTo(pa.x, pa.y);
      ctx.lineTo(pb.x, pb.y);
      ctx.strokeStyle = "rgba(255, 160, 80, 0.85)";
      ctx.lineWidth = 2.5;
      ctx.shadowColor = "rgba(255, 160, 80, 0.5)";
      ctx.shadowBlur = 8;
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    if (routeSystemIds.length > 1) {
      for (let i = 0; i < routeSystemIds.length - 1; i++) {
        const fromId = routeSystemIds[i];
        const toId = routeSystemIds[i + 1];
        const a = pos(fromId);
        const b = pos(toId);
        if (!a || !b) continue;
        const pa = worldToScreen(a.x, a.y, t);
        const pb = worldToScreen(b.x, b.y, t);
        ctx.beginPath();
        ctx.moveTo(pa.x, pa.y);
        ctx.lineTo(pb.x, pb.y);
        ctx.strokeStyle = "rgba(100, 200, 255, 0.95)";
        ctx.lineWidth = 3;
        ctx.shadowColor = "rgba(100, 200, 255, 0.6)";
        ctx.shadowBlur = 10;
        ctx.stroke();
        ctx.shadowBlur = 0;

        const mx = (pa.x + pb.x) / 2;
        const my = (pa.y + pb.y) / 2;
        ctx.beginPath();
        ctx.arc(mx, my, 9, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(20, 35, 50, 0.92)";
        ctx.fill();
        ctx.strokeStyle = "rgba(100, 200, 255, 0.8)";
        ctx.lineWidth = 1.5;
        ctx.stroke();
        ctx.fillStyle = "rgba(200, 230, 255, 0.95)";
        ctx.font = "bold 10px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(String(i + 1), mx, my);
      }
    }

    for (const sysId of drawIds) {
      const sys = atlas.systemsById.get(sysId);
      const p = pos(sysId);
      if (!sys || !p) continue;
      const active = routeSet.has(sysId);
      const inRange = rangeSet.has(sysId);
      const isOrigin = sysId === originSystemId;
      const isDest = sysId === destinationSystemId;
      const isSelected = sysId === selectedSystemId;
      if (!visible(p.x, p.y)) continue;

      const screen = worldToScreen(p.x, p.y, t);
      const emphasized = active || isOrigin || isDest || isSelected;
      const r = emphasized ? 7 : inRange ? 5.5 : lod === "region" ? 0 : lod === "constellation" ? 2.4 : 3.2;
      if (r <= 0) continue;

      if (emphasized) {
        ctx.beginPath();
        ctx.arc(screen.x, screen.y, r + 5, 0, Math.PI * 2);
        ctx.fillStyle = secGlow(p.security);
        ctx.fill();
      }

      ctx.beginPath();
      ctx.arc(screen.x, screen.y, r, 0, Math.PI * 2);
      ctx.fillStyle = secColor(p.security);
      ctx.fill();

      if (isOrigin) {
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 2;
        ctx.stroke();
      } else       if (isDest) {
        ctx.strokeStyle = "rgba(255, 200, 100, 0.95)";
        ctx.lineWidth = 2;
        ctx.stroke();
      } else if (isSelected) {
        ctx.strokeStyle = "rgba(180, 220, 255, 0.95)";
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      if (sysId === hoverIdRef.current && !emphasized) {
        ctx.beginPath();
        ctx.arc(screen.x, screen.y, r + 4, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(255, 255, 255, 0.85)";
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      if (emphasized && (lod === "detail" || isSelected)) {
        const label = p.name.length > 16 ? `${p.name.slice(0, 14)}…` : p.name;
        ctx.font = "11px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "bottom";
        ctx.fillStyle = "rgba(220, 235, 255, 0.92)";
        ctx.fillText(label, screen.x, screen.y - r - 6);
      }
    }

    if (showAllNodes) {
      if (lod === "region") {
        drawAreaLabels(ctx, atlas.regions, t, w, h, {
          minSpan: 24,
          fontSize: 13,
          fontWeight: "600",
          color: "rgba(210, 225, 245, 0.92)",
          bg: "rgba(12, 20, 32, 0.78)",
          border: "rgba(100, 140, 180, 0.35)",
        });
      } else if (lod === "constellation") {
        drawAreaLabels(ctx, atlas.constellations, t, w, h, {
          minSpan: 40,
          fontSize: 11,
          fontWeight: "500",
          color: "rgba(190, 210, 235, 0.9)",
          bg: "rgba(8, 14, 22, 0.72)",
          border: "rgba(80, 110, 140, 0.28)",
        });
      } else if (lod === "local") {
        drawAreaLabels(ctx, atlas.regions, t, w, h, {
          minSpan: 120,
          fontSize: 11,
          fontWeight: "600",
          color: "rgba(180, 200, 225, 0.75)",
          bg: "rgba(8, 14, 22, 0.65)",
          border: "rgba(70, 100, 130, 0.22)",
        });
        drawAreaLabels(ctx, atlas.constellations, t, w, h, {
          minSpan: 72,
          fontSize: 10,
          fontWeight: "500",
          color: "rgba(170, 195, 220, 0.8)",
          bg: "rgba(8, 14, 22, 0.68)",
          border: "rgba(80, 110, 140, 0.24)",
        });
      }
    }

    for (const wp of waypoints) {
      const p = pos(wp.system_id);
      if (!p) continue;
      const screen = worldToScreen(p.x, p.y, t);
      ctx.beginPath();
      ctx.moveTo(screen.x, screen.y - 10);
      ctx.lineTo(screen.x + 8, screen.y + 6);
      ctx.lineTo(screen.x - 8, screen.y + 6);
      ctx.closePath();
      ctx.fillStyle = wp.kind === "structure" ? "rgba(180, 140, 255, 0.9)" : "rgba(140, 200, 255, 0.9)";
      ctx.fill();
    }
  }, [
    atlas,
    atlasLoading,
    height,
    jumpLegs,
    jumpRangeLy,
    mode,
    originSystemId,
    destinationSystemId,
    selectedSystemId,
    browseMode,
    rangeDistancesLy,
    rangeSet,
    routeSet,
    routeSystemIds,
    rangeSystemIds,
    positions,
    pos,
    waypoints,
  ]);

  useEffect(() => {
    draw();
  }, [draw, transform, hover?.sys.system_id]);

  useEffect(() => {
    const onResize = () => draw();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [draw]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left;
      const sy = e.clientY - rect.top;
      const factor = e.deltaY > 0 ? 0.9 : 1.1;
      setTransform((prev) => {
        const world = screenToWorld(sx, sy, prev);
        const nextScale = Math.min(8, Math.max(0.05, prev.scale * factor));
        return {
          scale: nextScale,
          tx: sx - world.x * nextScale,
          ty: sy + world.y * nextScale,
        };
      });
    };

    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", onWheel);
  }, []);

  const updateHover = useCallback(
    (clientX: number, clientY: number) => {
      const canvas = canvasRef.current;
      const container = containerRef.current;
      if (!canvas || !container || !atlas || dragging) {
        setHover(null);
        return;
      }
      const rect = canvas.getBoundingClientRect();
      const sx = clientX - rect.left;
      const sy = clientY - rect.top;
      if (sx < 0 || sy < 0 || sx > rect.width || sy > rect.height) {
        setHover(null);
        return;
      }
      const t = transformRef.current;
      const w = container.clientWidth;
      const h = height;
      const highlightIds = new Set<number>([...routeSystemIds, ...rangeSystemIds]);
      if (originSystemId) highlightIds.add(originSystemId);
      if (destinationSystemId) highlightIds.add(destinationSystemId);
      const showAllNodes = routeSystemIds.length === 0 && rangeSystemIds.length === 0;
      const drawIds = systemsForDraw(atlas, t, w, h, highlightIds, showAllNodes);
      const posMap = new Map<number, { x: number; y: number }>();
      for (const id of drawIds) {
        const p = positions.get(id);
        if (p) posMap.set(id, { x: p.x, y: p.y });
      }
      const hit = hitTestSystem(atlas, posMap, t, sx, sy, drawIds, 14);
      if (hit) {
        hoverIdRef.current = hit.system_id;
        setHover({ sys: hit, sx, sy });
      } else {
        hoverIdRef.current = null;
        setHover(null);
      }
    },
    [atlas, dragging, height, originSystemId, destinationSystemId, positions, routeSystemIds, rangeSystemIds]
  );

  useEffect(() => {
    if (dragging || !mouseRef.current) return;
    updateHover(mouseRef.current.x, mouseRef.current.y);
  }, [transform, draw, dragging, updateHover]);

  const onPointerDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    setDragging(true);
    dragMovedRef.current = false;
    setHover(null);
    dragRef.current = { x: e.clientX, y: e.clientY, tx: transform.tx, ty: transform.ty };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const drag = dragRef.current;
    if (dragging && drag) {
      const dx = e.clientX - drag.x;
      const dy = e.clientY - drag.y;
      if (Math.hypot(dx, dy) > 4) dragMovedRef.current = true;
      setTransform((prev) => ({
        ...prev,
        tx: drag.tx + dx,
        ty: drag.ty + dy,
      }));
      return;
    }
    mouseRef.current = { x: e.clientX, y: e.clientY };
    updateHover(e.clientX, e.clientY);
  };

  const onPointerUp = (e: React.PointerEvent) => {
    const drag = dragRef.current;
    if (!dragMovedRef.current && drag && atlas && onSystemClick) {
      const canvas = canvasRef.current;
      if (canvas) {
        const rect = canvas.getBoundingClientRect();
        const sx = e.clientX - rect.left;
        const sy = e.clientY - rect.top;
        const t = transformRef.current;
        const w = containerRef.current?.clientWidth ?? 0;
        const h = height;
        const highlightIds = new Set<number>([...routeSystemIds, ...rangeSystemIds]);
        if (originSystemId) highlightIds.add(originSystemId);
        if (destinationSystemId) highlightIds.add(destinationSystemId);
        if (selectedSystemId) highlightIds.add(selectedSystemId);
        const showAllNodes = browseMode || (routeSystemIds.length === 0 && rangeSystemIds.length === 0);
        const drawIds = systemsForDraw(atlas, t, w, h, highlightIds, showAllNodes);
        const posMap = new Map<number, { x: number; y: number }>();
        for (const id of drawIds) {
          const p = positions.get(id);
          if (p) posMap.set(id, { x: p.x, y: p.y });
        }
        const hit = hitTestSystem(atlas, posMap, t, sx, sy, drawIds, 14);
        if (hit) onSystemClick(hit);
      }
    }
    setDragging(false);
    dragRef.current = null;
  };

  const onPointerLeave = (e: React.PointerEvent) => {
    onPointerUp(e);
    mouseRef.current = null;
    hoverIdRef.current = null;
    setHover(null);
  };

  return (
    <div className="eve-map-canvas-wrap" ref={containerRef}>
      <canvas
        ref={canvasRef}
        className={`eve-map-canvas${dragging ? " eve-map-canvas--dragging" : ""}${browseMode ? " eve-map-canvas--browse" : ""}`}
        style={{ height }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerLeave}
        role="img"
        aria-label="EVE map"
      />
      {hover && !dragging && (
        <div className="eve-map-system-tooltip" style={{ left: hover.sx, top: hover.sy }}>
          <div className="eve-map-system-tooltip-name">{hover.sys.name}</div>
          <div className="eve-map-system-tooltip-meta">
            {hover.sys.security.toFixed(1)} sec
            {hover.sys.constellation_name ? ` · ${hover.sys.constellation_name}` : ""}
          </div>
          {hover.sys.region_name ? (
            <div className="eve-map-system-tooltip-region">{hover.sys.region_name}</div>
          ) : null}
        </div>
      )}
      <div className="eve-map-canvas-hud">
        <span>{atlas ? `${atlas.system_count.toLocaleString()} systems` : "—"}</span>
        <button
          type="button"
          className="eve-btn eve-btn-sm"
          disabled={!atlas}
          onClick={() => {
            if (!atlas) return;
            if (routeSystemIds.length) {
              applyFit([...expandWithNeighbors(atlas, routeSystemIds, 1)]);
            } else {
              applyFit();
            }
          }}
        >
          Fit view
        </button>
      </div>
    </div>
  );
}
