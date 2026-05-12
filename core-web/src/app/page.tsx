const apiBase =
  process.env.NEXT_PUBLIC_CORE_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export default function HomePage() {
  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">
          EVE-EMU Core (web)
        </h1>
        <p className="mt-2 text-[var(--muted)]">
          This Next.js app is the <strong className="text-[var(--fg)]">primary browser experience</strong>.
          The Python FastAPI service is the <strong className="text-[var(--fg)]">API + SSO backend</strong>{" "}
          (same repo under <code className="text-[var(--accent)]">core/</code>). The Discord bot stays on
          Discord and talks to that API with the bot secret where needed.
        </p>
      </div>
      <section className="rounded-lg border border-white/10 bg-white/5 p-4 text-sm text-[var(--muted)]">
        <p className="font-medium text-white">Configure</p>
        <ul className="mt-2 list-inside list-disc space-y-1">
          <li>
            <code className="text-[var(--accent)]">NEXT_PUBLIC_CORE_API_URL</code> — FastAPI base (shown:{" "}
            <code className="text-white/90">{apiBase}</code>)
          </li>
          <li>
            Optional <code className="text-[var(--accent)]">CORE_WEB_BASE_PATH</code> at{" "}
            <em>build time</em> if the site is served under a subpath (e.g. <code>/core</code>).
          </li>
        </ul>
      </section>
      <p className="text-sm text-[var(--muted)]">
        Next steps: add auth flows that call <code className="text-[var(--accent)]">/v1/auth/eve/...</code>, build
        dashboards for plugins (finance, moon taxes, etc.), and keep bot-only routes on the API for Discord.
      </p>
    </main>
  );
}
