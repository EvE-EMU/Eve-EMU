"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { useWindowManager } from "@/components/WindowManager";
import { TOOLS } from "@/lib/tools/registry";
import { openToolInDesktop } from "@/lib/openTool";

type SearchResult = {
  tools: { id: string; label: string; href: string; window?: string; category: string }[];
  types: { type_id: number; name: string; group_name: string; category_name: string }[];
  systems: { system_id: number; name: string; security: number; region_name: string }[];
};

export function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { openWindow, focusWindow } = useWindowManager();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
    } else {
      setQ("");
      setResults(null);
    }
  }, [open]);

  const runSearch = useCallback(async (query: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/tools/search?q=${encodeURIComponent(query)}`);
      setResults((await res.json()) as SearchResult);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => runSearch(q), q ? 180 : 0);
    return () => clearTimeout(t);
  }, [q, open, runSearch]);

  const navigateTool = (windowId?: string, slug?: string) => {
    setOpen(false);
    if (windowId && slug) {
      openToolInDesktop(slug, windowId, openWindow, focusWindow);
      return;
    }
    if (windowId) {
      openWindow(windowId);
      focusWindow(windowId);
    }
  };

  const localTools =
    q.trim() === ""
      ? TOOLS.slice(0, 10).map((t) => ({
          id: t.slug,
          label: t.label,
          href: t.href ?? (t.category === "operations" ? "/industrial" : `/${t.category}`),
          window: t.windowId,
          category: t.category,
        }))
      : [];

  const tools = results?.tools?.length ? results.tools : localTools;

  return (
    <>
      <button
        type="button"
        className="eve-global-search-trigger"
        onClick={() => setOpen(true)}
        aria-label="Search tools, SDE, and windows"
      >
        <span className="eve-global-search-placeholder">Search tools, items, systems…</span>
        <kbd className="eve-global-search-kbd">⌘K</kbd>
      </button>

      {open ? (
        <div className="eve-global-search-overlay" onClick={() => setOpen(false)} role="presentation">
          <div className="eve-global-search-panel" onClick={(e) => e.stopPropagation()} role="dialog">
            <input
              ref={inputRef}
              className="eve-global-search-input"
              placeholder="Search windows, SDE types, systems…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
            {loading ? <p className="eve-global-search-hint">Searching…</p> : null}
            <div className="eve-global-search-results">
              {tools.length > 0 ? (
                <section>
                  <h4>Tools & Windows</h4>
                  <ul>
                    {tools.map((t) => (
                      <li key={t.id}>
                        <button type="button" onClick={() => navigateTool(t.window, t.id)}>
                          <strong>{t.label}</strong>
                          <span>{t.category}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
              {results?.types?.length ? (
                <section>
                  <h4>SDE Types</h4>
                  <ul>
                    {results.types.map((t) => (
                      <li key={t.type_id}>
                        <button type="button" onClick={() => navigateTool("sde-browser", "sde")}>
                          <strong>{t.name}</strong>
                          <span>
                            {t.group_name} · #{t.type_id}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
              {results?.systems?.length ? (
                <section>
                  <h4>Systems</h4>
                  <ul>
                    {results.systems.map((s) => (
                      <li key={s.system_id}>
                        <button type="button" onClick={() => navigateTool("map-visual", "map")}>
                          <strong>{s.name}</strong>
                          <span>
                            {s.security.toFixed(2)} · {s.region_name}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
              {!loading && !tools.length && !results?.types?.length && !results?.systems?.length ? (
                <p className="eve-global-search-hint">No matches — try item names, system names, or tool labels.</p>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

export function useLocale() {
  const [locale, setLocaleState] = useState("en");

  useEffect(() => {
    setLocaleState(localStorage.getItem("emums-locale") || "en");
  }, []);

  const setLocale = (code: string) => {
    localStorage.setItem("emums-locale", code);
    setLocaleState(code);
    document.documentElement.lang = code;
  };

  return { locale, setLocale };
}

const FOOTER_STRINGS: Record<string, Record<string, string>> = {
  en: { suite: "EMU Manager Suite", tagline: "Thoughtfully created by", interface: "Tranquility-style interface" },
  de: { suite: "EMU Manager Suite", tagline: "Mit Sorgfalt erstellt von", interface: "Tranquility-Oberfläche" },
  fr: { suite: "EMU Manager Suite", tagline: "Créé avec soin par", interface: "Interface style Tranquility" },
  ru: { suite: "EMU Manager Suite", tagline: "Создано с заботой", interface: "Интерфейс в стиле Tranquility" },
  ja: { suite: "EMU Manager Suite", tagline: "丁寧に作成", interface: "Tranquility スタイル UI" },
};

export function AppFooter() {
  const { locale, setLocale } = useLocale();
  const strings = FOOTER_STRINGS[locale] ?? FOOTER_STRINGS.en;

  return (
    <footer className="eve-app-footer">
      <div className="eve-app-footer-main">
        <span>{strings.suite}</span>
        <span className="eve-app-footer-sep">·</span>
        <span>
          {strings.tagline}{" "}
          <a href="https://evewho.com/character/715529239" target="_blank" rel="noreferrer" className="eve-footer-link">
            sevey
          </a>
        </span>
      </div>
      <div className="eve-app-footer-meta">
        <span>{strings.interface}</span>
        <div className="eve-locale-buttons" role="group" aria-label="Language">
          {(["en", "de", "fr", "ru", "ja"] as const).map((code) => (
            <button
              key={code}
              type="button"
              className={clsx("eve-locale-btn", locale === code && "active")}
              onClick={() => setLocale(code)}
              aria-pressed={locale === code}
            >
              {code.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
    </footer>
  );
}
