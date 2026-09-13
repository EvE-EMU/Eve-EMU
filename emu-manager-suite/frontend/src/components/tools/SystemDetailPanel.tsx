"use client";

import { useEffect, useState } from "react";

type SystemRow = {
  system_id: number;
  name: string;
  security: number;
  region_name?: string;
  constellation_name?: string;
};

export function SystemDetailPanel({ systemId }: { systemId: number | null }) {
  const [system, setSystem] = useState<SystemRow | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!systemId) {
      setSystem(null);
      return;
    }
    setLoading(true);
    fetch(`/api/tools/sde/systems?q=${systemId}&limit=20`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then((rows: SystemRow[]) => {
        setSystem(rows.find((r) => r.system_id === systemId) ?? rows[0] ?? null);
      })
      .catch(() => setSystem(null))
      .finally(() => setLoading(false));
  }, [systemId]);

  if (!systemId) {
    return <p className="text-[11px] text-[var(--text-muted)] p-2">No system selected.</p>;
  }

  if (loading) {
    return <p className="text-[11px] text-[var(--text-muted)] p-2">Loading system…</p>;
  }

  if (!system) {
    return (
      <p className="text-[11px] text-[var(--text-muted)] p-2">
        System {systemId.toLocaleString()} not found in SDE.
      </p>
    );
  }

  const secClass =
    system.security >= 0.45 ? "text-[var(--ok)]" : system.security > 0 ? "text-[var(--warn)]" : "text-[var(--danger)]";

  return (
    <div className="eve-system-detail p-3 text-[11px] space-y-3">
      <div>
        <h3 className="text-[var(--accent)] text-sm font-semibold">{system.name}</h3>
        <p className="text-[var(--text-muted)] text-[10px]">System ID {system.system_id.toLocaleString()}</p>
      </div>
      <dl className="eve-char-sheet-dl">
        <dt>Security</dt>
        <dd className={secClass}>{system.security.toFixed(2)}</dd>
        <dt>Constellation</dt>
        <dd>{system.constellation_name || "—"}</dd>
        <dt>Region</dt>
        <dd>{system.region_name || "—"}</dd>
      </dl>
      <a href={`/map?system=${encodeURIComponent(system.name)}`} className="eve-btn eve-btn-primary inline-block">
        Open on map
      </a>
    </div>
  );
}
