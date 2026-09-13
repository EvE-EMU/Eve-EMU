import clsx from "clsx";
import { EveWindow } from "./EveWindow";

export { EveWindow } from "./EveWindow";

export function StatusStrip({ children }: { children: React.ReactNode }) {
  return <div className="eve-ticker">{children}</div>;
}

export function KpiTile({
  label,
  value,
  tone = "accent",
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  const toneClass =
    tone === "danger"
      ? "text-[var(--danger)]"
      : tone === "warn"
        ? "text-[var(--warn)]"
        : tone === "ok"
          ? "text-[var(--ok)]"
          : "text-[var(--link)]";
  return (
    <div className="eve-kpi-cell">
      <p className="label">{label}</p>
      <p className={clsx("value", toneClass)}>{value}</p>
    </div>
  );
}

export function KpiStrip({ children }: { children: React.ReactNode }) {
  return <div className="eve-kpi-strip">{children}</div>;
}

/** @deprecated use EveWindow with id */
export function Panel({
  id,
  title,
  children,
  className,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <EveWindow id={id} title={title} className={className}>
      {children}
    </EveWindow>
  );
}

export function DataField({
  label,
  value,
  children,
}: {
  label: string;
  value?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="eve-field-row">
      <span className="eve-field-label">{label}</span>
      <span className="eve-field-value">{children ?? value}</span>
    </div>
  );
}

export function SectionHead({ children }: { children: React.ReactNode }) {
  return <p className="eve-section-head">{children}</p>;
}

export function RarityTag({ rarity }: { rarity: string }) {
  const r = rarity.toLowerCase();
  return <span className={clsx("eve-tag", `eve-tag-${r}`)}>{r.toUpperCase()}</span>;
}

export function EveTable({
  headers,
  children,
  className,
}: {
  headers: { label: React.ReactNode; align?: "left" | "right" }[];
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("overflow-x-auto eve-scroll", className)}>
      <table className="eve-table min-w-full">
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th key={i} className={h.align === "right" ? "text-right" : undefined}>
                {h.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
