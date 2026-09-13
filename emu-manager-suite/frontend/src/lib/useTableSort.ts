"use client";

import { useCallback, useMemo, useState } from "react";

export function useTableSort<K extends string>(defaultKey: K, defaultAsc = true) {
  const [sortKey, setSortKey] = useState<K>(defaultKey);
  const [sortAsc, setSortAsc] = useState(defaultAsc);

  const toggleSort = useCallback(
    (key: K) => {
      if (sortKey === key) setSortAsc((v) => !v);
      else {
        setSortKey(key);
        setSortAsc(true);
      }
    },
    [sortKey]
  );

  return { sortKey, sortAsc, toggleSort, setSortKey, setSortAsc };
}

export function compareSortValues(a: unknown, b: unknown): number {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  if (typeof a === "boolean" && typeof b === "boolean") return Number(a) - Number(b);
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
}

export function sortByKey<T, K extends string>(
  rows: T[],
  sortKey: K,
  sortAsc: boolean,
  accessor: (row: T, key: K) => unknown
): T[] {
  const dir = sortAsc ? 1 : -1;
  return [...rows].sort((a, b) => compareSortValues(accessor(a, sortKey), accessor(b, sortKey)) * dir);
}

export function useSortedRows<T, K extends string>(
  rows: T[],
  defaultKey: K,
  accessor: (row: T, key: K) => unknown,
  defaultAsc = true
) {
  const { sortKey, sortAsc, toggleSort } = useTableSort(defaultKey, defaultAsc);
  const sorted = useMemo(
    () => sortByKey(rows, sortKey, sortAsc, accessor),
    [rows, sortKey, sortAsc, accessor]
  );
  return { sorted, sortKey, sortAsc, toggleSort };
}
