"use client";

import { useCallback, useEffect, useState } from "react";
import { characterPortraitUrl } from "@/lib/evetech";
import { useAuth } from "@/components/AuthProvider";

type PilotHit = {
  character_id: number;
  character_name: string;
  corporation_name: string;
};

export function PilotLookupPanel({ onSelect }: { onSelect?: (characterId: number) => void }) {
  const { session } = useAuth();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<PilotHit[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const search = useCallback(async (q: string) => {
    if (q.trim().length < 2) {
      setHits([]);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`/api/audit/search?q=${encodeURIComponent(q.trim())}`, {
        cache: "no-store",
        credentials: "same-origin",
      });
      if (!res.ok) {
        setHits([]);
        setError(res.status === 403 ? "HR lookup access required." : "Search failed.");
        return;
      }
      setHits((await res.json()) as PilotHit[]);
    } catch {
      setError("Search failed.");
      setHits([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const t = window.setTimeout(() => void search(query), 280);
    return () => window.clearTimeout(t);
  }, [query, search]);

  if (!session.authenticated) {
    return <p className="text-[11px] text-[var(--text-muted)] p-2">Log in to use pilot lookup.</p>;
  }

  if (!session.hr_lookup) {
    return (
      <p className="text-[11px] text-[var(--text-muted)] p-2">
        HR pilot lookup requires a configured corporation title or director access.
      </p>
    );
  }

  return (
    <div className="eve-pilot-lookup p-2">
      <label className="block text-[10px] uppercase tracking-wide text-[var(--text-muted)] mb-1">
        HR pilot lookup
      </label>
      <input
        type="search"
        className="eve-input w-full"
        placeholder="Character name…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        autoComplete="off"
      />
      {loading ? <p className="text-[10px] text-[var(--text-muted)] mt-2">Searching…</p> : null}
      {error ? <p className="text-[10px] text-[var(--warn)] mt-2">{error}</p> : null}
      <ul className="eve-pilot-lookup-hits mt-2">
        {hits.map((hit) => (
          <li key={hit.character_id}>
            <button
              type="button"
              className="eve-pilot-lookup-row"
              onClick={() => onSelect?.(hit.character_id)}
            >
              <img src={characterPortraitUrl(hit.character_id, 64)} alt="" width={32} height={32} />
              <span>
                <strong>{hit.character_name}</strong>
                {hit.corporation_name ? (
                  <span className="block text-[var(--text-muted)]">{hit.corporation_name}</span>
                ) : null}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
