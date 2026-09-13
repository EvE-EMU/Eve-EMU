"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const RARITY_COLORS: Record<string, string> = {
  r4: "#9ad4e8",
  r8: "#9ee8b8",
  r16: "#f0d060",
  r32: "#e8c878",
  r64: "#e89090",
};

const TOOLTIP_STYLE = {
  background: "#12181f",
  border: "1px solid #2a3540",
  fontSize: 10,
};

const CHART_3D_FILTER = (
  <defs>
    <filter id="chartDepth" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="3" stdDeviation="3" floodColor="#000" floodOpacity="0.45" />
    </filter>
    <linearGradient id="bar3dGold" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor="#c04040" />
      <stop offset="55%" stopColor="#8b1a1a" />
      <stop offset="100%" stopColor="#4a0e0e" />
    </linearGradient>
    <linearGradient id="bar3dWarn" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor="#e8b878" />
      <stop offset="55%" stopColor="#c07840" />
      <stop offset="100%" stopColor="#6a4020" />
    </linearGradient>
    <linearGradient id="bar3dOk" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor="#98e8b0" />
      <stop offset="55%" stopColor="#58a878" />
      <stop offset="100%" stopColor="#2a5840" />
    </linearGradient>
    <linearGradient id="area3d" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor="#9ed0e0" stopOpacity={0.45} />
      <stop offset="100%" stopColor="#3a6878" stopOpacity={0.05} />
    </linearGradient>
  </defs>
);

function rarityGradient(id: string, color: string) {
  return (
    <linearGradient key={id} id={id} x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stopColor={color} stopOpacity={1} />
      <stop offset="100%" stopColor={color} stopOpacity={0.55} />
    </linearGradient>
  );
}

export function MiningAreaChart({
  data,
}: {
  data: { date: string; volume: number; isk: number }[];
}) {
  const trimmed = data.slice(-21);
  return (
    <div className="eve-chart-3d h-52 w-full min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={trimmed} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          {CHART_3D_FILTER}
          <CartesianGrid stroke="#2a3540" strokeDasharray="2 2" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fill: "#9aa8b4", fontSize: 9 }}
            tickFormatter={(v) => v.slice(5)}
            axisLine={{ stroke: "#2a3540" }}
            tickLine={false}
          />
          <YAxis tick={{ fill: "#9aa8b4", fontSize: 9 }} axisLine={false} tickLine={false} width={36} />
          <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "#d4dce4" }} />
          <Area
            type="monotone"
            dataKey="volume"
            stroke="#9ed0e0"
            strokeWidth={2}
            fill="url(#area3d)"
            filter="url(#chartDepth)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RarityPieChart({ data }: { data: { rarity: string; volume: number }[] }) {
  const gradients = data.map((entry) =>
    rarityGradient(`rarity-${entry.rarity}`, RARITY_COLORS[entry.rarity] || "#8aa0b0")
  );

  return (
    <div className="eve-chart-3d h-52 w-full min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <defs>
            {gradients}
            <filter id="pieDepth" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="2" stdDeviation="2" floodColor="#000" floodOpacity="0.5" />
            </filter>
          </defs>
          <Pie
            data={data}
            dataKey="volume"
            nameKey="rarity"
            innerRadius={40}
            outerRadius={64}
            paddingAngle={2}
            stroke="#1a222c"
            strokeWidth={2}
            filter="url(#pieDepth)"
            label={({ rarity, percent }) =>
              `${String(rarity).toUpperCase()} ${(percent * 100).toFixed(0)}%`
            }
            labelLine={{ stroke: "#c8d4dc", strokeWidth: 1 }}
          >
            {data.map((entry) => (
              <Cell
                key={entry.rarity}
                fill={`url(#rarity-${entry.rarity})`}
                style={{ filter: "drop-shadow(0px 2px 2px rgba(0,0,0,0.4))" }}
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            itemStyle={{ color: "#e8f0f8" }}
            labelStyle={{ color: "#d4dce4" }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export function StructureBarChart({ data }: { data: { name: string; isk: number }[] }) {
  return (
    <div className="eve-chart-3d h-56 w-full min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 4, right: 8, top: 4, bottom: 4 }}>
          {CHART_3D_FILTER}
          <CartesianGrid stroke="#2a3540" strokeDasharray="2 2" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fill: "#9aa8b4", fontSize: 9 }}
            tickFormatter={(v) => `${(v / 1e9).toFixed(1)}B`}
            axisLine={{ stroke: "#2a3540" }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={108}
            tick={{ fill: "#c8d4dc", fontSize: 8 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            formatter={(v: number) => [`${v.toLocaleString()} ISK`, "Value"]}
            contentStyle={TOOLTIP_STYLE}
          />
          <Bar dataKey="isk" fill="url(#bar3dGold)" barSize={10} radius={[0, 3, 3, 0]} filter="url(#chartDepth)" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

const INVOICE_BAR_COLORS: Record<string, string> = {
  Outstanding: "url(#bar3dWarn)",
  Paid: "url(#bar3dOk)",
};

export function InvoiceStatusChart({ data }: { data: { status: string; isk: number }[] }) {
  return (
    <div className="eve-chart-3d h-48 w-full min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 12, right: 8, left: -8, bottom: 0 }}>
          {CHART_3D_FILTER}
          <CartesianGrid stroke="#2a3540" strokeDasharray="2 2" vertical={false} />
          <XAxis
            dataKey="status"
            tick={{ fill: "#c8d4dc", fontSize: 10 }}
            axisLine={{ stroke: "#2a3540" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "#9aa8b4", fontSize: 9 }}
            tickFormatter={(v) => `${(v / 1e9).toFixed(1)}B`}
            axisLine={false}
            tickLine={false}
            width={36}
          />
          <Tooltip
            formatter={(v: number) => [`${v.toLocaleString()} ISK`, "Amount"]}
            contentStyle={TOOLTIP_STYLE}
          />
          <Bar dataKey="isk" barSize={28} radius={[4, 4, 0, 0]} filter="url(#chartDepth)">
            {data.map((entry) => (
              <Cell key={entry.status} fill={INVOICE_BAR_COLORS[entry.status] || "url(#bar3dGold)"} />
            ))}
            <LabelList
              dataKey="isk"
              position="top"
              formatter={(v: number) => `${(v / 1e9).toFixed(2)}B`}
              fill="#e8f0f8"
              fontSize={10}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
