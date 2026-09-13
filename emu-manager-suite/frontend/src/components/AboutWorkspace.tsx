"use client";

import { EveWindow } from "@/components/ui";

const SUITE_TOOLS = [
  "Intel Paste",
  "Trade Margins",
  "Haul Finder",
  "Gate Camp Route",
  "Corp Who",
  "Battle Report",
  "Structure Board",
  "Ship Compare",
  "Insurance Check",
  "Skill Queues",
];

const CORE_TOOLS = [
  "Character Audit (skills, assets, wallet, mail, contracts)",
  "Industrial suite on eve-emu.com/industrial (Plan / Orders / Ops / Tools) — primary product",
  "Legacy EMUMS Build Planner / Storefront (bridges quotes to ManufacturingProject; prefer /industrial)",
  "Structure Fuel board (ESI fuel timers + fuel blocks)",
  "Moon Mining Timing (activity windows from mining logs)",
  "Market Browser & Appraisal / Buyback",
  "Killboard & SRP",
  "Route / Jump Map & Wormhole Map",
  "Planetary Interaction",
  "HR Directorate & Service Links",
  "Moon productivity & tax config",
  "Knowledge & SDE browser",
];

export function AboutWorkspace() {
  return (
    <EveWindow
      id="about"
      title="About EMU Manager Suite"
      defaultX={96}
      defaultY={72}
      defaultWidth={520}
      defaultHeight={560}
    >
      <div className="eve-about-body">
        <p className="eve-about-lead">
          <strong>EMU Manager Suite (EMUMS)</strong> is the coalition desktop for EvE EMU — finance,
          industry, intelligence, storefront, and administration in one EVE-client-style workspace.
        </p>

        <dl className="eve-about-meta">
          <div>
            <dt>Version</dt>
            <dd>0.2.1</dd>
          </div>
          <div>
            <dt>Host</dt>
            <dd>
              <a href="https://emums.eve-emu.com" target="_blank" rel="noreferrer">
                emums.eve-emu.com
              </a>
            </dd>
          </div>
          <div>
            <dt>Wiki</dt>
            <dd>
              <a href="https://wiki.eve-emu.com" target="_blank" rel="noreferrer">
                wiki.eve-emu.com
              </a>
            </dd>
          </div>
          <div>
            <dt>Auth</dt>
            <dd>
              <a href="https://auth.eve-emu.com" target="_blank" rel="noreferrer">
                auth.eve-emu.com
              </a>
            </dd>
          </div>
          <div>
            <dt>Data</dt>
            <dd>ESI · zKill · Janice · audit DB (no demo fixtures in production)</dd>
          </div>
        </dl>

        <h3 className="text-[11px] uppercase tracking-wide text-[var(--text-muted)] mt-3 mb-1">
          Core tools
        </h3>
        <ul className="text-[11px] list-disc pl-4 space-y-0.5 text-[var(--text)]">
          {CORE_TOOLS.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>

        <h3 className="text-[11px] uppercase tracking-wide text-[var(--text-muted)] mt-3 mb-1">
          Awesome Tool Suite
        </h3>
        <p className="text-[10px] text-[var(--text-muted)] mb-1">
          Combined from{" "}
          <a
            href="https://github.com/devfleet/awesome-eve"
            target="_blank"
            rel="noreferrer"
            className="eve-char-sheet-link"
          >
            awesome-eve
          </a>{" "}
          community tools — open via Utilities → Awesome Tool Suite.
        </p>
        <ul className="text-[11px] list-disc pl-4 columns-2 gap-4 space-y-0.5">
          {SUITE_TOOLS.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>

        <p className="eve-about-hint mt-3">
          Open tools from the neocom on the left. Double-click a section icon for its default window.
          Use <strong>Close All Windows</strong> above Log off to clear the desktop. Log in with EVE
          SSO for character audit, storefront checkout, and skill queues.
        </p>

        <p className="text-[10px] text-[var(--text-muted)] mt-2">
          Thoughtfully created for EvE EMU · Moon rental UI is paused for now.
        </p>
      </div>
    </EveWindow>
  );
}
