"use client";

import clsx from "clsx";
import { EveWindow } from "@/components/ui";
import {
  FONT_OPTIONS,
  UI_SCALE_PRESETS,
  UI_SCALE_REFERENCE,
} from "@/lib/displayPreferences";
import {
  UI_SCALE_MAX,
  UI_SCALE_MIN,
  UI_SCALE_STEP,
  uiScalePercent,
  useDisplayPreferences,
} from "@/components/DisplayPreferencesProvider";

export function DisplaySettingsWindow() {
  const { prefs, setFontId, setUiScale, bumpUiScale, resetDisplayPrefs } = useDisplayPreferences();
  const zoomLabel = `${uiScalePercent(prefs.uiScale)}%`;

  return (
    <EveWindow
      id="display-settings"
      title="Display & accessibility"
      defaultX={4}
      defaultY={300}
      defaultWidth={420}
      defaultHeight={360}
    >
      <div className="eve-display-settings">
        <p className="eve-settings-hint">
          Adjust text and interface size for easier reading. Saved in this browser only.
        </p>

        <section className="eve-display-section">
          <h3 className="eve-display-section-title">UI scale / zoom</h3>
          <div className="eve-display-scale-row">
            <button
              type="button"
              className="eve-btn-sm"
              aria-label="Decrease UI size"
              disabled={prefs.uiScale <= UI_SCALE_MIN}
              onClick={() => bumpUiScale(-UI_SCALE_STEP)}
            >
              A−
            </button>
            <input
              className="eve-display-range"
              type="range"
              min={UI_SCALE_MIN}
              max={UI_SCALE_MAX}
              step={UI_SCALE_STEP}
              value={prefs.uiScale}
              aria-label="UI scale"
              onChange={(e) => setUiScale(Number(e.target.value))}
            />
            <button
              type="button"
              className="eve-btn-sm"
              aria-label="Increase UI size"
              disabled={prefs.uiScale >= UI_SCALE_MAX}
              onClick={() => bumpUiScale(UI_SCALE_STEP)}
            >
              A+
            </button>
            <span className="eve-display-scale-value">{zoomLabel}</span>
          </div>
          <div className="eve-display-presets">
            {UI_SCALE_PRESETS.map((preset) => (
              <button
                key={preset.id}
                type="button"
                className={clsx(
                  "eve-btn-sm",
                  Math.abs(prefs.uiScale - preset.value) < 0.001 && "eve-btn-primary"
                )}
                onClick={() => setUiScale(preset.value)}
              >
                {preset.label}
                {preset.value === UI_SCALE_REFERENCE ? "" : ` (${uiScalePercent(preset.value)}%)`}
              </button>
            ))}
          </div>
        </section>

        <section className="eve-display-section">
          <h3 className="eve-display-section-title">Font</h3>
          <label className="eve-settings-field">
            <span>Typeface</span>
            <select
              className="eve-select w-full"
              value={prefs.fontId}
              onChange={(e) => setFontId(e.target.value as typeof prefs.fontId)}
            >
              {FONT_OPTIONS.map((font) => (
                <option key={font.id} value={font.id}>
                  {font.label}
                </option>
              ))}
            </select>
          </label>
          <p className="eve-display-font-preview" style={{ fontFamily: "var(--app-font)" }}>
            The quick brown fox jumps over the lazy dog. ISK 1,234,567.89 · Jita 4-4
          </p>
        </section>

        <div className="eve-display-actions">
          <button type="button" className="eve-btn-sm" onClick={resetDisplayPrefs}>
            Reset to default
          </button>
        </div>
      </div>
    </EveWindow>
  );
}
