"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { EveWindow } from "@/components/ui";
import { WindowDesktop } from "@/components/WindowManager";

type WhSystem = {
  id: number;
  solar_system_id: number;
  system_name: string;
  system_signature: string;
  wh_class: string;
  pos_x: number;
  pos_y: number;
};

type WhConnection = {
  id: number;
  source_node_id: number;
  target_node_id: number;
  wh_type: string;
  mass_status: string;
  eol: boolean;
};

type WhMap = { id: number; name: string };

type SimNode = WhSystem & { vx: number; vy: number; fx?: number; fy?: number };

const MASS_COLORS: Record<string, string> = {
  normal: "#7eb8ca",
  reduced: "#c9a227",
  critical: "#c44",
};

export function WhMapWorkspace() {
  const [maps, setMaps] = useState<WhMap[]>([]);
  const [mapId, setMapId] = useState<number | null>(null);
  const [systems, setSystems] = useState<WhSystem[]>([]);
  const [connections, setConnections] = useState<WhConnection[]>([]);
  const [selectedNode, setSelectedNode] = useState<number | null>(null);
  const [sigQuery, setSigQuery] = useState("");
  const svgRef = useRef<SVGSVGElement>(null);
  const nodesRef = useRef<SimNode[]>([]);

  const loadMaps = useCallback(async () => {
    const res = await fetch("/api/map/wh/maps", { cache: "no-store" });
    if (res.ok) {
      const rows: WhMap[] = await res.json();
      setMaps(rows);
      if (rows.length && !mapId) setMapId(rows[0].id);
    }
  }, [mapId]);

  const loadMap = useCallback(async (id: number) => {
    const res = await fetch(`/api/map/wh/maps/${id}`, { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    setSystems(data.systems ?? []);
    setConnections(data.connections ?? []);
  }, []);

  useEffect(() => {
    void loadMaps();
  }, [loadMaps]);

  useEffect(() => {
    if (mapId) void loadMap(mapId);
  }, [mapId, loadMap]);

  useEffect(() => {
    if (!mapId) return;
    const poll = window.setInterval(() => void loadMap(mapId), 5000);
    return () => window.clearInterval(poll);
  }, [mapId, loadMap]);

  useEffect(() => {
    nodesRef.current = systems.map((s, i) => ({
      ...s,
      pos_x: s.pos_x || Math.cos(i) * 120,
      pos_y: s.pos_y || Math.sin(i) * 120,
      vx: 0,
      vy: 0,
    }));
  }, [systems]);

  useEffect(() => {
    let frame = 0;
    const tick = () => {
      const nodes = nodesRef.current;
      const alpha = 0.15;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].pos_x - nodes[i].pos_x;
          const dy = nodes[j].pos_y - nodes[i].pos_y;
          const dist = Math.max(40, Math.hypot(dx, dy));
          const force = (8000 / dist) * alpha;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          nodes[i].vx -= fx;
          nodes[i].vy -= fy;
          nodes[j].vx += fx;
          nodes[j].vy += fy;
        }
      }
      for (const c of connections) {
        const a = nodes.find((n) => n.id === c.source_node_id);
        const b = nodes.find((n) => n.id === c.target_node_id);
        if (!a || !b) continue;
        const dx = b.pos_x - a.pos_x;
        const dy = b.pos_y - a.pos_y;
        const dist = Math.max(1, Math.hypot(dx, dy));
        const force = (dist - 100) * 0.05 * alpha;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        a.vx += fx;
        a.vy += fy;
        b.vx -= fx;
        b.vy -= fy;
      }
      for (const n of nodes) {
        if (n.fx != null && n.fy != null) {
          n.pos_x = n.fx;
          n.pos_y = n.fy;
          n.vx = 0;
          n.vy = 0;
        } else {
          n.vx *= 0.85;
          n.vy *= 0.85;
          n.pos_x += n.vx;
          n.pos_y += n.vy;
        }
      }
      const svg = svgRef.current;
      if (svg) {
        for (const g of svg.querySelectorAll<SVGGElement>("[data-node-id]")) {
          const id = Number(g.dataset.nodeId);
          const node = nodes.find((n) => n.id === id);
          if (node) g.setAttribute("transform", `translate(${node.pos_x},${node.pos_y})`);
        }
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [connections, systems]);

  const createMap = async () => {
    const name = window.prompt("Map name", "Chain Alpha");
    if (!name) return;
    const res = await fetch("/api/map/wh/maps", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, creator_character_id: 0, creator_character_name: "Director" }),
    });
    if (res.ok) {
      const row = await res.json();
      setMapId(row.id);
      void loadMaps();
    }
  };

  const addSystem = async () => {
    if (!mapId || !sigQuery.trim()) return;
    const res = await fetch(`/api/tools/sde/systems?q=${encodeURIComponent(sigQuery)}&limit=5`);
    const rows: { system_id: number; name: string; security: number }[] = res.ok ? await res.json() : [];
    const pick = rows[0];
    if (!pick) return;
    await fetch(`/api/map/wh/maps/${mapId}/systems`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        solar_system_id: pick.system_id,
        system_name: pick.name,
        system_signature: sigQuery.trim(),
        wh_class: pick.security < 0 ? `C${Math.abs(Math.round(pick.security * 10))}` : "K-space",
        space_type: pick.security < 0 ? "j-space" : "k-space",
        pos_x: Math.random() * 80 - 40,
        pos_y: Math.random() * 80 - 40,
      }),
    });
    setSigQuery("");
    void loadMap(mapId);
  };

  const connectSelected = async (targetId: number) => {
    if (!mapId || !selectedNode || selectedNode === targetId) return;
    await fetch(`/api/map/wh/maps/${mapId}/connections`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_node_id: selectedNode, target_node_id: targetId, wh_type: "K162" }),
    });
    void loadMap(mapId);
  };

  const cycleMass = async (conn: WhConnection) => {
    const order = ["normal", "reduced", "critical"];
    const next = order[(order.indexOf(conn.mass_status) + 1) % order.length];
    await fetch(`/api/map/wh/connections/${conn.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mass_status: next }),
    });
  };

  const toggleEol = async (conn: WhConnection) => {
    await fetch(`/api/map/wh/connections/${conn.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ eol: !conn.eol }),
    });
  };

  const nodeById = useMemo(() => new Map(systems.map((s) => [s.id, s])), [systems]);

  return (
    <WindowDesktop className="min-h-0 flex-1">
      <EveWindow id="wh-map" title="Wormhole Chain Map" defaultWidth={920} defaultHeight={640}>
        <div className="flex flex-col gap-2 h-full min-h-[480px]">
          <div className="flex flex-wrap gap-2 items-center">
            <select
              className="eve-input text-[11px]"
              value={mapId ?? ""}
              onChange={(e) => setMapId(Number(e.target.value))}
            >
              {maps.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
            <button type="button" className="eve-btn-sm" onClick={() => void createMap()}>
              New map
            </button>
            <input
              className="eve-input text-[11px] flex-1 min-w-[120px]"
              placeholder="Signature / system search"
              value={sigQuery}
              onChange={(e) => setSigQuery(e.target.value)}
            />
            <button type="button" className="eve-btn-sm eve-btn-primary" onClick={() => void addSystem()}>
              Add system
            </button>
          </div>
          <svg ref={svgRef} className="flex-1 w-full bg-[#0a0e12] border border-[#12181f] rounded">
            <g transform="translate(460,280)">
              {connections.map((c) => {
                const a = nodeById.get(c.source_node_id);
                const b = nodeById.get(c.target_node_id);
                if (!a || !b) return null;
                return (
                  <line
                    key={c.id}
                    x1={a.pos_x}
                    y1={a.pos_y}
                    x2={b.pos_x}
                    y2={b.pos_y}
                    stroke={c.eol ? "#c44" : MASS_COLORS[c.mass_status] ?? "#7eb8ca"}
                    strokeWidth={c.mass_status === "critical" ? 3 : 2}
                    strokeDasharray={c.eol ? "6 4" : undefined}
                    onContextMenu={(e) => {
                      e.preventDefault();
                      void cycleMass(c);
                    }}
                    onDoubleClick={() => void toggleEol(c)}
                  />
                );
              })}
              {systems.map((s) => (
                <g
                  key={s.id}
                  data-node-id={s.id}
                  transform={`translate(${s.pos_x},${s.pos_y})`}
                  style={{ cursor: "grab" }}
                  onClick={() => {
                    if (selectedNode && selectedNode !== s.id) void connectSelected(s.id);
                    else setSelectedNode(s.id);
                  }}
                >
                  <circle r={14} fill={selectedNode === s.id ? "#7eb8ca" : "#1a2430"} stroke="#7eb8ca" />
                  <text y={4} textAnchor="middle" fill="#dce6ee" fontSize={9}>
                    {s.wh_class || "?"}
                  </text>
                  <text y={26} textAnchor="middle" fill="#9ab" fontSize={8}>
                    {s.system_name.slice(0, 12)}
                  </text>
                </g>
              ))}
            </g>
          </svg>
          <p className="text-[10px] text-[var(--text-muted)]">
            Click node to select · click another to connect · right-click line = cycle mass · double-click line = toggle EOL
          </p>
        </div>
      </EveWindow>
    </WindowDesktop>
  );
}
