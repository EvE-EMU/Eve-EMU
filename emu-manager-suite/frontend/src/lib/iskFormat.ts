/** Full-precision ISK display: 19,881,262,204.81 ISK */
export function fmtIskFull(value: string | number | null | undefined): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return "— ISK";
  return `${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ISK`;
}

/** Compact ISK for headers (K/M/B/T). */
export function fmtIskCompact(value: string | number | null | undefined): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  if (Math.abs(n) >= 1e12) return `${(n / 1e12).toFixed(2)} T`;
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(2)} B`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(2)} M`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(1)} K`;
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

export function formatWalletDropFlag(detail: string): string {
  const m = detail.match(/Wallet dropped\s+([\d.eE+-]+)\s+ISK/i);
  if (!m) return detail;
  return `Wallet dropped ${fmtIskFull(Number(m[1]))} since last snapshot`;
}
