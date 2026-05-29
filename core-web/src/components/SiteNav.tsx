import Link from "next/link";

const marketTools = [
  { href: "/margin_finder", label: "Margin finder" },
  { href: "/market_trends", label: "Market trends" },
  { href: "/contract_price", label: "Contract prices" },
  { href: "/tradeVol_type", label: "Trade volume" },
  { href: "/price_compare", label: "Price compare" },
  { href: "/pi_rank", label: "PI rank" },
  { href: "/market-browser", label: "Market browser" },
  { href: "/appraisal", label: "Appraisal" },
] as const;

export function SiteNav() {
  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-[#0a0d11]/95 backdrop-blur">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-2 px-4 py-2">
        <Link href="/" className="mr-2 text-sm font-semibold tracking-wide text-white">
          eve-emu
        </Link>
        {marketTools.map((tool) => (
          <a
            key={tool.href}
            href={tool.href}
            className="rounded border border-transparent px-2 py-1 text-[11px] uppercase tracking-wider text-[var(--muted)] hover:border-white/15 hover:bg-white/5 hover:text-white"
          >
            {tool.label}
          </a>
        ))}
      </div>
    </header>
  );
}
