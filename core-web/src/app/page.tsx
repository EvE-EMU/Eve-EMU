const authUrl =
  process.env.NEXT_PUBLIC_AUTH_URL?.replace(/\/$/, "") ||
  "https://auth.eve-emu.com";

export default function HomePage() {
  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-8 px-6 py-20">
      <div>
        <p className="text-sm font-medium uppercase tracking-widest text-[var(--accent)]">
          EvE-EMU
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white">
          EVE Online tools for your organization
        </h1>
        <p className="mt-3 text-[var(--muted)]">
          Public market data for <strong className="text-white">W O M P S T A R</strong>{" "}
          (3-FKCZ) — spreads, order books, and hub comparisons. Members sign in through
          Alliance Auth for corp services, buyback, and permissions.
        </p>
      </div>
      <section className="flex flex-wrap gap-3">
        <a
          href="/margin_finder"
          className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-black hover:opacity-90"
        >
          Market tools
        </a>
        <a
          href={authUrl}
          className="rounded-md border border-white/15 px-4 py-2 text-sm font-medium text-white hover:bg-white/5"
        >
          Member login &amp; services
        </a>
      </section>
      <section className="rounded-lg border border-white/10 bg-white/5 p-4 text-sm text-[var(--muted)]">
        <p>
          <strong className="text-white">Alliance Auth</strong> (groups, SRP, buyback,
          wiki) is at{" "}
          <a href={authUrl} className="text-[var(--accent)] hover:underline">
            {authUrl.replace(/^https?:\/\//, "")}
          </a>
          . Market pages on this domain are served separately from the member portal.
        </p>
      </section>
    </main>
  );
}
