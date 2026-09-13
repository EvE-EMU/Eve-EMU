"use client";

export type SystemActivityRow = {
  system_id: number;
  name: string;
  security: number;
  jumps_24h: number;
  kills_24h: number;
  jumps_48h: number;
  kills_48h: number;
  npc_kills_24h?: number;
  npc_kills_48h?: number;
};

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 10_000) return `${Math.round(n / 1000)}k`;
  if (n >= 1_000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

function heatClass(kills: number): string {
  if (kills >= 50) return "eve-activity-hot";
  if (kills >= 15) return "eve-activity-warm";
  if (kills >= 5) return "eve-activity-mild";
  return "";
}

export function RouteActivityTable({
  rows,
  partial,
  hoursAvailable,
}: {
  rows: SystemActivityRow[];
  partial?: boolean;
  hoursAvailable?: number;
}) {
  if (!rows.length) return null;

  return (
    <div className="mt-2">
      <div className="flex items-baseline justify-between gap-2 mb-1">
        <span className="text-[var(--text-muted)] text-[0.85em]">System activity (Dotlan-style)</span>
        {partial ? (
          <span className="text-[var(--warn)] text-[0.75em]">
            ~{hoursAvailable ?? 1}h of history — 24h/48h fill in as hourly snapshots accumulate
          </span>
        ) : null}
      </div>
      <table className="eve-table eve-activity-table">
        <thead>
          <tr>
            <th>System</th>
            <th className="num">Sec</th>
            <th className="num" title="Ship jumps last 24 hours">
              J24
            </th>
            <th className="num" title="Ship + pod kills last 24 hours">
              K24
            </th>
            <th className="num" title="Ship jumps last 48 hours">
              J48
            </th>
            <th className="num" title="Ship + pod kills last 48 hours">
              K48
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.system_id} className={heatClass(r.kills_24h)}>
              <td>{r.name}</td>
              <td className="num">{r.security.toFixed(1)}</td>
              <td className="num">{fmt(r.jumps_24h)}</td>
              <td className="num">{fmt(r.kills_24h)}</td>
              <td className="num">{fmt(r.jumps_48h)}</td>
              <td className="num">{fmt(r.kills_48h)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
