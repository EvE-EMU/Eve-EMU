"use client";

import { useCallback, useEffect, useState } from "react";
import { SectionHead, StatusStrip } from "@/components/ui";

type FuelRow = {
  structure_id: number;
  structure_name: string;
  system_name: string;
  structure_type_name: string;
  structure_state: string;
  fuel_expires_at: string | null;
  hours_remaining: number | null;
  fuel_blocks_qty: number;
  status: string;
  has_market: boolean;
  has_reprocessing: boolean;
};

function statusClass(status: string) {
  if (status === "critical" || status === "empty") return "text-[var(--danger)]";
  if (status === "low") return "text-[var(--warn)]";
  if (status === "ok") return "text-[var(--ok)]";
  return "text-[var(--text-muted)]";
}

export function StructureFuelPanel() {
  const [rows, setRows] = useState<FuelRow[]>([]);
  const [summary, setSummary] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");
  const [syncNote, setSyncNote] = useState("");

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(
        `/api/tools/structure-fuel${refresh ? "?refresh=1" : ""}`,
        { cache: "no-store" }
      );
      if (!res.ok) {
        setError(res.status === 401 ? "Log in to view structure fuel." : "Failed to load fuel board.");
        return;
      }
      const data = await res.json();
      setRows(data.structures || []);
      setSummary(data.summary || {});
      if (data.sync?.errors?.length) {
        setSyncNote(data.sync.errors.slice(0, 3).join("; "));
      } else if (refresh) {
        setSyncNote(`Synced ${data.sync?.updated ?? 0} structure(s) from ESI.`);
      }
    } catch {
      setError("Failed to load fuel board.");
    } finally {
      setLoading(false);
    }
  }, []);

  const sync = async () => {
    setSyncing(true);
    setError("");
    try {
      const res = await fetch("/api/tools/structure-fuel/sync", { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Sync failed");
      } else {
        setSyncNote(
          `ESI sync: ${data.updated ?? 0} updated across ${data.corps ?? 0} corp(s).` +
            (data.errors?.length ? ` Notes: ${data.errors.slice(0, 2).join("; ")}` : "")
        );
      }
      await load(false);
    } catch {
      setError("Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    void load(false);
  }, [load]);

  return (
    <div className="flex flex-col gap-2 min-h-0 h-full">
      <StatusStrip>
        Structure fuel from ESI corp structures + fuel-block assets · critical{" "}
        {summary.critical ?? 0} · low {summary.low ?? 0} · ok {summary.ok ?? 0}
      </StatusStrip>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="eve-btn eve-btn-secondary text-sm" onClick={() => void load(false)} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
        <button type="button" className="eve-btn eve-btn-primary text-sm" onClick={() => void sync()} disabled={syncing}>
          {syncing ? "Syncing ESI…" : "Sync fuel from ESI"}
        </button>
      </div>
      {syncNote ? <p className="text-[10px] text-[var(--text-muted)]">{syncNote}</p> : null}
      {error ? <p className="text-[var(--danger)] text-sm">{error}</p> : null}
      <p className="text-[10px] text-[var(--text-muted)]">
        Requires a corp character with <code>esi-corporations.read_structures.v1</code> and Station Manager. Fuel block
        counts come from audit-synced assets at structure locations.
      </p>
      <div className="overflow-auto min-h-0 flex-1 border border-[var(--edge-dim)]">
        <table className="eve-table text-[11px]">
          <thead>
            <tr>
              <th>Structure</th>
              <th>System</th>
              <th>Type</th>
              <th>State</th>
              <th>Fuel expires</th>
              <th className="text-end">Hours</th>
              <th className="text-end">Blocks</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.structure_id}>
                <td>
                  <strong>{r.structure_name}</strong>
                  <div className="text-[9px] text-[var(--text-muted)]">
                    {r.has_market ? "market " : ""}
                    {r.has_reprocessing ? "reprocess" : ""}
                  </div>
                </td>
                <td>{r.system_name || "—"}</td>
                <td>{r.structure_type_name || "—"}</td>
                <td>{r.structure_state || "—"}</td>
                <td className="text-[10px]">{r.fuel_expires_at?.replace("T", " ").slice(0, 16) || "—"}</td>
                <td className="text-end">{r.hours_remaining != null ? r.hours_remaining.toFixed(1) : "—"}</td>
                <td className="text-end">{r.fuel_blocks_qty.toLocaleString()}</td>
                <td className={statusClass(r.status)}>{r.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && !loading ? (
          <p className="p-3 text-sm text-[var(--text-muted)]">
            No structures yet — run Sync fuel from ESI or wait for structure discovery during audit sync.
          </p>
        ) : null}
      </div>
      <SectionHead>Fuel block types tracked</SectionHead>
      <p className="text-[10px] text-[var(--text-muted)]">
        Helium, Hydrogen, Nitrogen, Oxygen Fuel Blocks (asset locations on structures).
      </p>
    </div>
  );
}
