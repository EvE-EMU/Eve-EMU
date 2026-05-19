import Link from "next/link";

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
          Public information and member-facing utilities. Sign in through Alliance
          Auth for corp services, permissions, and integrations.
        </p>
      </div>
      <section className="flex flex-wrap gap-3">
        <a
          href={authUrl}
          className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-black hover:opacity-90"
        >
          Member login &amp; services
        </a>
        <Link
          href="/industrial"
          className="rounded-md border border-white/15 px-4 py-2 text-sm font-medium text-white hover:bg-white/5"
        >
          Industrial tools
        </Link>
      </section>
      <section className="rounded-lg border border-white/10 bg-white/5 p-4 text-sm text-[var(--muted)]">
        <p>
          <strong className="text-white">Alliance Auth</strong> (groups, SRP, market
          tools, wiki access) lives at{" "}
          <a href={authUrl} className="text-[var(--accent)] hover:underline">
            {authUrl.replace(/^https?:\/\//, "")}
          </a>
          . This site is the public EvE-EMU front door; authenticated apps and APIs
          are linked from there.
        </p>
      </section>
    </main>
  );
}
