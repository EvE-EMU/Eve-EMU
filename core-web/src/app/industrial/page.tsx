import Link from "next/link";
import { LogisticsCalculator } from "./LogisticsCalculator";
import { NotificationToggles } from "./NotificationToggles";

const apiBase =
  process.env.NEXT_PUBLIC_CORE_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export default function IndustrialPage() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-10 px-6 py-16">
      <header className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
          EvE-EMU · Industrial Command
        </p>
        <h1 className="text-3xl font-semibold tracking-tight text-white">
          Industrial dark console
        </h1>
        <p className="text-[var(--muted)]">
          Browser shell for coalition tooling. Privileged routes stay on FastAPI (
          <code className="text-[var(--accent)]">{apiBase}</code>
          ) with bot or SSO secrets — this page is mostly layout + calculators until
          wired to authenticated APIs.
        </p>
        <Link
          href="/"
          className="inline-block text-sm text-[var(--accent)] underline-offset-4 hover:underline"
        >
          ← Back to home
        </Link>
      </header>

      <section className="rounded-xl border border-amber-500/20 bg-gradient-to-br from-amber-500/5 to-transparent p-6 shadow-[0_0_40px_-20px_rgba(245,158,11,0.35)]">
        <h2 className="text-lg font-semibold text-amber-100">Moon mining taxes</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Ledger-driven estimates run through <code className="text-[var(--accent)]">core</code> (
          <code className="text-white/80">POST /v1/plugins/moon-taxes/summary</code> with the bot
          secret). Surface results here once the Next auth layer is connected.
        </p>
      </section>

      <section className="rounded-xl border border-white/10 bg-white/[0.03] p-6">
        <h2 className="text-lg font-semibold text-white">BPC service</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">
          The Django <code className="text-[var(--accent)]">industry_suite</code> app defines{" "}
          <code className="text-white/80">BlueprintCopyListing</code> for a searchable index and
          &quot;request copy&quot; workflows — hook your Alliance Auth UI or REST to those models.
        </p>
      </section>

      <section className="rounded-xl border border-white/10 bg-white/[0.03] p-6">
        <h2 className="text-lg font-semibold text-white">Logistics calculator</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Rough Jita → structure freight from volume, collateral, and your org&apos;s ISK/m³ + minimum
          fee (tune numbers to your courier contract rules).
        </p>
        <div className="mt-4">
          <LogisticsCalculator />
        </div>
      </section>

      <section className="rounded-xl border border-white/10 bg-white/[0.03] p-6">
        <h2 className="text-lg font-semibold text-white">Discord alert toggles</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Prototype: mute categories client-side until per-user prefs are stored in{" "}
          <code className="text-[var(--accent)]">core</code> or Alliance Auth.
        </p>
        <div className="mt-4">
          <NotificationToggles />
        </div>
      </section>
    </main>
  );
}
