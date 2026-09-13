"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import type { Invoice } from "@/lib/api";

const columns: ColumnDef<Invoice>[] = [
  {
    accessorKey: "invoice_number",
    header: "Invoice",
    cell: ({ getValue }) => (
      <span className="font-mono text-[10px] text-[var(--link)]">{String(getValue())}</span>
    ),
  },
  { accessorKey: "character_name", header: "Pilot" },
  {
    accessorKey: "structure_name",
    header: "Structure",
    cell: ({ getValue }) => <span className="text-[var(--text-muted)]">{String(getValue())}</span>,
  },
  {
    accessorKey: "total_due_isk",
    header: "Due ISK",
    cell: ({ getValue }) => (
      <span className="num">{Number(getValue()).toLocaleString()}</span>
    ),
    sortingFn: (a, b) =>
      Number(a.original.total_due_isk) - Number(b.original.total_due_isk),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => {
      const inv = row.original;
      return (
        <span
          className={
            inv.on_naughty_list
              ? "text-[var(--danger)]"
              : inv.status === "paid"
                ? "text-[var(--ok)]"
                : "text-[var(--warn)]"
          }
        >
          {inv.status}
        </span>
      );
    },
  },
];

export function TaxAssessmentsTable({ invoices }: { invoices: Invoice[] }) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState("");

  const data = useMemo(() => invoices, [invoices]);

  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    globalFilterFn: (row, _columnId, filter) => {
      const q = String(filter).toLowerCase();
      if (!q) return true;
      const inv = row.original;
      return (
        inv.invoice_number.toLowerCase().includes(q) ||
        inv.character_name.toLowerCase().includes(q) ||
        inv.structure_name.toLowerCase().includes(q) ||
        inv.status.toLowerCase().includes(q)
      );
    },
  });

  return (
    <div className="eve-tax-table">
      <div className="eve-tax-table-toolbar">
        <input
          className="eve-input eve-tax-table-search"
          placeholder="Search invoices, pilots, structures…"
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
        />
        <span className="eve-tax-table-count">
          {table.getFilteredRowModel().rows.length} of {invoices.length}
        </span>
      </div>
      <div className="overflow-x-auto eve-scroll eve-tax-table-wrap">
        <table className="eve-table min-w-full">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => (
                  <th
                    key={header.id}
                    className={clsx(
                      header.column.getCanSort() && "eve-th-sortable",
                      header.column.id === "total_due_isk" && "text-right"
                    )}
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <span className="eve-th-label">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {header.column.getIsSorted() === "asc"
                        ? " ▲"
                        : header.column.getIsSorted() === "desc"
                          ? " ▼"
                          : header.column.getCanSort()
                            ? " ⇅"
                            : null}
                    </span>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="eve-tax-table-empty">
                  No matching assessments
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className={cell.column.id === "total_due_isk" ? "text-right" : undefined}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
