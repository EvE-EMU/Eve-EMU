"use client";

import { EveTypeIcon } from "@/components/ui/EveTypeIcon";
import { useCharSheetInspect } from "@/components/tools/CharSheetInspectContext";

export type CloneSnapshot = {
  last_clone_jump_date?: string | null;
  last_station_change_date?: string | null;
  active_implants?: { type_id: number; type_name: string }[];
  jump_clones?: {
    jump_clone_id: number;
    location_id: number;
    location_name?: string | null;
    solar_system_id?: number | null;
    solar_system_name?: string | null;
    name?: string;
    implant_details?: { type_id: number; type_name: string }[];
  }[];
};

function SystemLink({ systemId, systemName }: { systemId?: number | null; systemName?: string | null }) {
  const inspect = useCharSheetInspect();
  if (!systemId) {
    return null;
  }
  const label = systemName || `System ${systemId}`;
  if (!inspect?.openSystemDetail) {
    return <span>{label}</span>;
  }
  return (
    <button type="button" className="eve-char-sheet-location-link" onClick={() => inspect.openSystemDetail(systemId, label)}>
      {label}
    </button>
  );
}

export function CharacterSheetClones({ clones }: { clones: CloneSnapshot }) {
  const active = clones.active_implants ?? [];
  const jumpClones = clones.jump_clones ?? [];

  return (
    <div className="eve-char-sheet-clones space-y-4">
      <section>
        <h3 className="eve-char-sheet-section-title">Active clone</h3>
        <dl className="eve-char-sheet-dl">
          <dt>Last clone jump</dt>
          <dd>{clones.last_clone_jump_date ? clones.last_clone_jump_date.replace("T", " ").slice(0, 16) : "—"}</dd>
        </dl>
        {active.length ? (
          <table className="eve-table w-full text-[10px] mt-2">
            <thead>
              <tr>
                <th />
                <th>Implant</th>
              </tr>
            </thead>
            <tbody>
              {active.map((imp) => (
                <tr key={imp.type_id}>
                  <td className="w-6">
                    <EveTypeIcon typeId={imp.type_id} size={18} preferRender />
                  </td>
                  <td>{imp.type_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-[var(--text-muted)]">No active implants.</p>
        )}
      </section>

      <section>
        <h3 className="eve-char-sheet-section-title">Jump clones ({jumpClones.length})</h3>
        {jumpClones.length ? (
          jumpClones.map((jc) => (
            <div key={jc.jump_clone_id} className="eve-char-sheet-clone-card">
              <div className="eve-char-sheet-clone-head">
                <strong>{jc.name || `Jump clone ${jc.jump_clone_id}`}</strong>
                <span className="text-[var(--text-muted)]">{jc.location_name || `Location ${jc.location_id}`}</span>
              </div>
              {jc.solar_system_id ? (
                <p className="text-[10px] text-[var(--text-muted)] mb-1">
                  System: <SystemLink systemId={jc.solar_system_id} systemName={jc.solar_system_name} />
                </p>
              ) : null}
              {(jc.implant_details?.length ?? 0) > 0 ? (
                <ul className="eve-char-sheet-clone-implants">
                  {jc.implant_details!.map((imp) => (
                    <li key={imp.type_id}>
                      <EveTypeIcon typeId={imp.type_id} size={16} preferRender />
                      <span>{imp.type_name}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[var(--text-muted)] text-[10px]">No implants installed.</p>
              )}
            </div>
          ))
        ) : (
          <p className="text-[var(--text-muted)]">No jump clones recorded.</p>
        )}
      </section>
    </div>
  );
}
