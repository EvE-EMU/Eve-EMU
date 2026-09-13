"use client";

import { useEffect, useState } from "react";
import { DashboardWorkspace } from "@/components/DashboardWorkspace";
import type { Dashboard } from "@/lib/api";

export function DashboardLoader() {
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch("/api/dashboard", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then(setDash)
      .catch(() => setError(true));
  }, []);

  if (error) {
    return <p className="text-[11px] text-[var(--danger)]">Dashboard data unavailable.</p>;
  }

  if (!dash) {
    return <p className="text-[11px] text-[var(--text-muted)]">Loading command dashboard…</p>;
  }

  return <DashboardWorkspace dash={dash} />;
}
