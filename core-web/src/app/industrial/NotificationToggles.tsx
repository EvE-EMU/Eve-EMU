"use client";

import { useEffect, useState } from "react";

const KEYS = [
  { id: "pi", label: "Planetary industry pings" },
  { id: "research", label: "Research / invention complete" },
  { id: "moon", label: "Moon timer alerts" },
  { id: "mining", label: "Mining anomaly belt timers" },
  { id: "production", label: "Corp production batches" },
] as const;

const STORAGE_KEY = "eve_emu_discord_alert_prefs_v1";

type Prefs = Record<string, boolean>;

function loadPrefs(): Prefs {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Prefs;
    return typeof parsed === "object" && parsed ? parsed : {};
  } catch {
    return {};
  }
}

export function NotificationToggles() {
  const [muted, setMuted] = useState<Prefs>({});

  useEffect(() => {
    setMuted(loadPrefs());
  }, []);

  const toggle = (id: string, value: boolean) => {
    setMuted((prev) => {
      const next = { ...prev, [id]: value };
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        /* ignore quota */
      }
      return next;
    });
  };

  return (
    <ul className="space-y-3">
      {KEYS.map((k) => (
        <li
          key={k.id}
          className="flex items-center justify-between gap-4 rounded-lg border border-white/5 bg-black/25 px-3 py-2"
        >
          <span className="text-sm text-[var(--fg)]">{k.label}</span>
          <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
            <input
              type="checkbox"
              checked={Boolean(muted[k.id])}
              onChange={(e) => toggle(k.id, e.target.checked)}
              className="accent-[var(--accent)]"
            />
            Mute
          </label>
        </li>
      ))}
    </ul>
  );
}
