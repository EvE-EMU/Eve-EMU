"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  DEFAULT_DISPLAY_PREFS,
  UI_SCALE_REFERENCE,
  UI_SCALE_MAX,
  UI_SCALE_MIN,
  UI_SCALE_STEP,
  applyDisplayPrefs,
  clampUiScale,
  loadDisplayPrefs,
  saveDisplayPrefs,
  type DisplayPrefs,
  type FontId,
} from "@/lib/displayPreferences";

type DisplayPreferencesContextValue = {
  prefs: DisplayPrefs;
  setFontId: (fontId: FontId) => void;
  setUiScale: (uiScale: number) => void;
  bumpUiScale: (delta: number) => void;
  resetDisplayPrefs: () => void;
};

const DisplayPreferencesContext = createContext<DisplayPreferencesContextValue | null>(null);

export function DisplayPreferencesProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<DisplayPrefs>(DEFAULT_DISPLAY_PREFS);

  useEffect(() => {
    const loaded = loadDisplayPrefs();
    setPrefs(loaded);
    applyDisplayPrefs(loaded);
  }, []);

  const commit = useCallback((patch: Partial<DisplayPrefs> | ((prev: DisplayPrefs) => DisplayPrefs)) => {
    setPrefs((prev) => {
      const nextRaw = typeof patch === "function" ? patch(prev) : { ...prev, ...patch };
      const normalized = {
        fontId: nextRaw.fontId,
        uiScale: clampUiScale(nextRaw.uiScale),
      };
      saveDisplayPrefs(normalized);
      applyDisplayPrefs(normalized);
      return normalized;
    });
  }, []);

  const setFontId = useCallback(
    (fontId: FontId) => {
      commit({ fontId });
    },
    [commit]
  );

  const setUiScale = useCallback(
    (uiScale: number) => {
      commit({ uiScale });
    },
    [commit]
  );

  const bumpUiScale = useCallback(
    (delta: number) => {
      commit((prev) => {
        const next = clampUiScale(prev.uiScale + delta);
        if (next === prev.uiScale) return prev;
        return { ...prev, uiScale: next };
      });
    },
    [commit]
  );

  const resetDisplayPrefs = useCallback(() => {
    commit(() => DEFAULT_DISPLAY_PREFS);
  }, [commit]);

  const value = useMemo(
    () => ({
      prefs,
      setFontId,
      setUiScale,
      bumpUiScale,
      resetDisplayPrefs,
    }),
    [prefs, setFontId, setUiScale, bumpUiScale, resetDisplayPrefs]
  );

  return (
    <DisplayPreferencesContext.Provider value={value}>{children}</DisplayPreferencesContext.Provider>
  );
}

export function useDisplayPreferences(): DisplayPreferencesContextValue {
  const ctx = useContext(DisplayPreferencesContext);
  if (!ctx) {
    throw new Error("useDisplayPreferences must be used within DisplayPreferencesProvider");
  }
  return ctx;
}

export function uiScalePercent(scale: number): number {
  return Math.round((scale / UI_SCALE_REFERENCE) * 100);
}

export { UI_SCALE_MIN, UI_SCALE_MAX, UI_SCALE_STEP };
