"use client";

import { useMemo, useState } from "react";

function parseISK(raw: string): number {
  const n = Number(String(raw).replace(/,/g, "").trim());
  return Number.isFinite(n) ? n : 0;
}

export function LogisticsCalculator() {
  const [m3, setM3] = useState("50000");
  const [collateral, setCollateral] = useState("5000000000");
  const [iskPerM3, setIskPerM3] = useState("1200");
  const [minimumFee, setMinimumFee] = useState("15000000");
  const [collateralPct, setCollateralPct] = useState("1");

  const quote = useMemo(() => {
    const vol = Math.max(0, parseISK(m3));
    const coll = Math.max(0, parseISK(collateral));
    const rate = Math.max(0, parseISK(iskPerM3));
    const minFee = Math.max(0, parseISK(minimumFee));
    const pct = Math.max(0, parseISK(collateralPct));
    const freight = Math.max(minFee, vol * rate);
    const collFee = coll * (pct / 100);
    const total = freight + collFee;
    return { freight, collFee, total };
  }, [m3, collateral, iskPerM3, minimumFee, collateralPct]);

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <label className="text-sm text-[var(--muted)]">
        Volume (m³)
        <input
          className="mt-1 w-full rounded border border-white/10 bg-black/40 px-3 py-2 text-white outline-none focus:border-[var(--accent)]"
          value={m3}
          onChange={(e) => setM3(e.target.value)}
          inputMode="decimal"
        />
      </label>
      <label className="text-sm text-[var(--muted)]">
        Collateral (ISK)
        <input
          className="mt-1 w-full rounded border border-white/10 bg-black/40 px-3 py-2 text-white outline-none focus:border-[var(--accent)]"
          value={collateral}
          onChange={(e) => setCollateral(e.target.value)}
          inputMode="numeric"
        />
      </label>
      <label className="text-sm text-[var(--muted)]">
        Freight ISK / m³
        <input
          className="mt-1 w-full rounded border border-white/10 bg-black/40 px-3 py-2 text-white outline-none focus:border-[var(--accent)]"
          value={iskPerM3}
          onChange={(e) => setIskPerM3(e.target.value)}
          inputMode="decimal"
        />
      </label>
      <label className="text-sm text-[var(--muted)]">
        Minimum freight (ISK)
        <input
          className="mt-1 w-full rounded border border-white/10 bg-black/40 px-3 py-2 text-white outline-none focus:border-[var(--accent)]"
          value={minimumFee}
          onChange={(e) => setMinimumFee(e.target.value)}
          inputMode="numeric"
        />
      </label>
      <label className="text-sm text-[var(--muted)] sm:col-span-2">
        Collateral fee (% of collateral)
        <input
          className="mt-1 w-full rounded border border-white/10 bg-black/40 px-3 py-2 text-white outline-none focus:border-[var(--accent)]"
          value={collateralPct}
          onChange={(e) => setCollateralPct(e.target.value)}
          inputMode="decimal"
        />
      </label>
      <div className="sm:col-span-2 rounded-lg border border-white/10 bg-black/30 p-4 text-sm text-[var(--muted)]">
        <p>
          <span className="text-[var(--fg)]">Freight component:</span>{" "}
          <strong className="text-white">{quote.freight.toLocaleString()}</strong> ISK
        </p>
        <p className="mt-1">
          <span className="text-[var(--fg)]">Collateral component:</span>{" "}
          <strong className="text-white">{quote.collFee.toLocaleString()}</strong> ISK
        </p>
        <p className="mt-2 text-base text-[var(--accent)]">
          Indicative total:{" "}
          <strong>{quote.total.toLocaleString()}</strong> ISK
        </p>
      </div>
    </div>
  );
}
