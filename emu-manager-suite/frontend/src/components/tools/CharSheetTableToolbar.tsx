"use client";

import type { ReactNode } from "react";

export function CharSheetTableToolbar({
  query,
  onQueryChange,
  placeholder = "Filter…",
  filters,
  shown,
  total,
}: {
  query: string;
  onQueryChange: (value: string) => void;
  placeholder?: string;
  filters?: ReactNode;
  shown: number;
  total: number;
}) {
  return (
    <>
      <div className="eve-char-sheet-assets-toolbar">
        <input
          className="eve-input flex-1"
          placeholder={placeholder}
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
        />
        {filters}
      </div>
      <p className="text-[10px] text-[var(--text-muted)] mb-2">
        {shown.toLocaleString()} of {total.toLocaleString()} entries
      </p>
    </>
  );
}

export function CharSheetSortButton({
  label,
  active,
  asc,
  onClick,
  align = "left",
}: {
  label: string;
  active: boolean;
  asc: boolean;
  onClick: () => void;
  align?: "left" | "right";
}) {
  return (
    <button
      type="button"
      className={`eve-char-sheet-th-sort${align === "right" ? " eve-char-sheet-th-sort--right" : ""}`}
      onClick={onClick}
    >
      {label}
      {active ? (asc ? " ↑" : " ↓") : ""}
    </button>
  );
}
