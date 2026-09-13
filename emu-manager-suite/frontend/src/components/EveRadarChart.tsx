"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { RadarPoint } from "@/lib/shipRadarStats";

const TOOLTIP_STYLE = {
  background: "#12181f",
  border: "1px solid #2a3540",
  fontSize: 10,
};

export function EveRadarChart({
  data,
  title,
  compact,
}: {
  data: RadarPoint[];
  title?: string;
  compact?: boolean;
}) {
  if (data.length < 3) {
    return (
      <p className="text-[10px] text-[var(--text-muted)] py-2">
        Not enough combat stats for a radar chart.
      </p>
    );
  }

  const chartData = data.map((d) => ({ axis: d.axis, score: d.value, raw: d.raw, unit: d.unit }));

  return (
    <div className={compact ? "eve-radar-chart eve-radar-chart--compact" : "eve-radar-chart"}>
      {title ? <div className="eve-radar-chart-title">{title}</div> : null}
      <ResponsiveContainer width="100%" height={compact ? 160 : 220}>
        <RadarChart data={chartData} cx="50%" cy="50%" outerRadius={compact ? "68%" : "72%"}>
          <defs>
            <linearGradient id="eveRadarFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#9ed0e0" stopOpacity={0.55} />
              <stop offset="100%" stopColor="#3a6878" stopOpacity={0.15} />
            </linearGradient>
          </defs>
          <PolarGrid stroke="#2a3540" radialLines={true} />
          <PolarAngleAxis dataKey="axis" tick={{ fill: "#9ab0c0", fontSize: compact ? 9 : 10 }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} axisLine={false} />
          <Radar
            name="Stats"
            dataKey="score"
            stroke="#7ec8e0"
            fill="url(#eveRadarFill)"
            fillOpacity={0.65}
            strokeWidth={2}
            isAnimationActive={false}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={(value, _name, item) => {
              const row = item?.payload as { raw?: number; unit?: string } | undefined;
              const raw = row?.raw;
              const unit = row?.unit ? ` ${row.unit}` : "";
              return [`${raw != null ? raw.toLocaleString() : value}${unit}`, "Rating"];
            }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
