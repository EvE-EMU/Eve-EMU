"use client";

import { useEffect, useState } from "react";
import { EveTypeIcon } from "@/components/ui/EveTypeIcon";
import { StatusStrip } from "@/components/ui";

export type SdeComparePayload = {
  type_ids: number[];
  items: { type_id: number; name: string; group_name: string; volume_m3: number; base_price: number }[];
  attributes: { attribute_id: number; name: string; values: Record<string, number | null> }[];
  requirements: { name: string; levels: Record<string, number | null> }[];
};

function fmtNum(v: number | null | undefined) {
  if (v == null) return "—";
  if (Math.abs(v) >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (Number.isInteger(v)) return String(v);
  return v.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

export function SdeComparePanel({
  typeIds,
  onSelectType,
}: {
  typeIds: number[];
  onSelectType?: (typeId: number) => void;
}) {
  const [data, setData] = useState<SdeComparePayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (typeIds.length < 2) {
      setData(null);
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    fetch("/api/tools/sde/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type_ids: typeIds }),
    })
      .then(async (res) => {
        if (!res.ok) throw new Error("Compare failed");
        return res.json() as Promise<SdeComparePayload>;
      })
      .then(setData)
      .catch(() => {
        setData(null);
        setError("Could not compare selected types.");
      })
      .finally(() => setLoading(false));
  }, [typeIds]);

  if (typeIds.length < 2) {
    return (
      <p className="text-[var(--text-muted)] text-[11px]">
        Select two or more types in the browser (checkbox column) or use Compare group on an item detail.
      </p>
    );
  }

  if (loading) return <StatusStrip>Comparing {typeIds.length} types…</StatusStrip>;
  if (error || !data) return <p className="text-[var(--danger)] text-[11px]">{error || "No data."}</p>;

  return (
    <div className="flex flex-col gap-3 h-full min-h-0 text-[10px]">
      <div className="flex flex-wrap gap-2">
        {data.items.map((item) => (
          <button
            key={item.type_id}
            type="button"
            className="eve-sde-compare-item flex items-center gap-1 border border-[var(--border)] px-2 py-1 hover:bg-[var(--panel-elevated)]"
            onClick={() => onSelectType?.(item.type_id)}
          >
            <EveTypeIcon
              typeId={item.type_id}
              size={24}
              categoryName={item.group_name.includes("Blueprint") ? "Blueprint" : undefined}
              groupName={item.group_name}
            />
            <span className="font-semibold">{item.name}</span>
          </button>
        ))}
      </div>

      <div className="overflow-auto flex-1 min-h-0 space-y-3">
        <section>
          <h3 className="text-[11px] font-semibold mb-1">Attributes</h3>
          <table className="eve-table">
            <thead>
              <tr>
                <th>Attribute</th>
                {data.items.map((item) => (
                  <th key={item.type_id} className="text-left">
                    {item.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.attributes.map((row) => (
                <tr key={row.attribute_id}>
                  <td>{row.name}</td>
                  {data.items.map((item) => (
                    <td key={item.type_id} className="num">
                      {fmtNum(row.values[String(item.type_id)])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {data.requirements.length ? (
          <section>
            <h3 className="text-[11px] font-semibold mb-1">Skill requirements</h3>
            <table className="eve-table">
              <thead>
                <tr>
                  <th>Skill</th>
                  {data.items.map((item) => (
                    <th key={item.type_id}>{item.name}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.requirements.map((row) => (
                  <tr key={row.name}>
                    <td>{row.name}</td>
                    {data.items.map((item) => (
                      <td key={item.type_id} className="num">
                        {row.levels[String(item.type_id)] != null ? `L${row.levels[String(item.type_id)]}` : "—"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ) : null}
      </div>
    </div>
  );
}
