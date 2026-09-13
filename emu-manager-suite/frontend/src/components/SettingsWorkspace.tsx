"use client";

import { useState } from "react";
import clsx from "clsx";
import { EveWindow, StatusStrip } from "@/components/ui";
import { DesktopSurface } from "@/components/WindowManager";
import type { Invoice, MiningLog, OrgSettings, StructureTaxRule } from "@/lib/api";
import { updateSettings } from "@/lib/settings";
import { patchTaxRule } from "@/lib/admin";
import { useAuth } from "@/components/AuthProvider";
import { isAdministrator } from "@/lib/permissions";
import { MoonTaxPanel } from "@/components/MoonOperations";
import { AdminUserLookupPanel } from "@/components/AdminUserLookupPanel";

function SettingsField({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: "text" | "number";
}) {
  return (
    <label className="eve-settings-field">
      <span>{label}</span>
      <input
        className="eve-input"
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

export function SettingsWorkspace({
  settings: initial,
  taxRules = [],
  logs = [],
  invoices = [],
  embedded,
}: {
  settings: OrgSettings;
  taxRules?: StructureTaxRule[];
  logs?: MiningLog[];
  invoices?: Invoice[];
  embedded?: boolean;
}) {
  const { session } = useAuth();
  const admin = isAdministrator(session);
  const [orgName, setOrgName] = useState(initial.org_name);
  const [taxCorp, setTaxCorp] = useState(initial.tax_corp_name);
  const [corpId, setCorpId] = useState(String(initial.corporation_id));
  const [observerId, setObserverId] = useState(String(initial.observer_corporation_id));
  const [mailSender, setMailSender] = useState(initial.mail_sender_character || "");
  const [mailEnabled, setMailEnabled] = useState(initial.mail_enabled);
  const [tagline, setTagline] = useState(initial.propaganda_tagline);
  const [baseline, setBaseline] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dirty =
    orgName !== baseline.org_name ||
    taxCorp !== baseline.tax_corp_name ||
    corpId !== String(baseline.corporation_id) ||
    observerId !== String(baseline.observer_corporation_id) ||
    mailSender !== (baseline.mail_sender_character || "") ||
    mailEnabled !== baseline.mail_enabled ||
    tagline !== baseline.propaganda_tagline;

  const saveOrg = async () => {
    setSaving(true);
    setError(null);
    try {
      const updated = await updateSettings({
        org_name: orgName.trim(),
        tax_corp_name: taxCorp.trim(),
        corporation_id: Number(corpId) || 0,
        observer_corporation_id: Number(observerId) || 0,
        mail_sender_character: mailSender.trim(),
        mail_enabled: mailEnabled,
      });
      setBaseline(updated);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2000);
    } catch {
      setError("Could not save organization settings.");
    } finally {
      setSaving(false);
    }
  };

  const saveTagline = async () => {
    setSaving(true);
    setError(null);
    try {
      const updated = await updateSettings({ propaganda_tagline: tagline.trim() });
      setBaseline(updated);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2000);
    } catch {
      setError("Could not save tagline.");
    } finally {
      setSaving(false);
    }
  };

  const orgActions = (
    <button
      type="button"
      className={clsx("eve-btn-sm", dirty && "eve-template-save-pulse")}
      disabled={!dirty || saving}
      onClick={() => void saveOrg()}
    >
      {saving ? "Saving…" : saved ? "Saved" : "Save"}
    </button>
  );

  const taglineDirty = tagline !== baseline.propaganda_tagline;
  const taglineActions = (
    <button
      type="button"
      className={clsx("eve-btn-sm", taglineDirty && "eve-template-save-pulse")}
      disabled={!taglineDirty || saving}
      onClick={() => void saveTagline()}
    >
      {saving ? "Saving…" : saved ? "Saved" : "Save"}
    </button>
  );

  const settingsWindows = (
    <>
      {admin ? (
        <>
          <EveWindow
            id="org-settings"
            title="Organization"
            actions={orgActions}
            defaultX={4}
            defaultY={4}
            defaultWidth={400}
            defaultHeight={280}
          >
            <div className="eve-settings-form">
              <SettingsField label="Organization name" value={orgName} onChange={setOrgName} />
              <SettingsField label="Tax corporation" value={taxCorp} onChange={setTaxCorp} />
              <SettingsField label="Corporation ID" value={corpId} onChange={setCorpId} type="number" />
              <SettingsField
                label="Observer corporation ID"
                value={observerId}
                onChange={setObserverId}
                type="number"
              />
              <SettingsField
                label="EVE mail sender (character)"
                value={mailSender}
                onChange={setMailSender}
              />
              <label className="eve-check-row eve-settings-check">
                <button
                  type="button"
                  className={clsx("eve-checkbox", mailEnabled && "on")}
                  aria-pressed={mailEnabled}
                  onClick={() => setMailEnabled((v) => !v)}
                />
                <span>Send tax invoices via EVE mail</span>
              </label>
            </div>
          </EveWindow>

          <EveWindow
            id="ops-tagline"
            title="Operations tagline"
            actions={taglineActions}
            defaultX={416}
            defaultY={4}
            defaultWidth={380}
            defaultHeight={200}
          >
            <label className="eve-settings-field eve-settings-field--grow">
              <span>Dashboard status strip</span>
              <textarea
                className="eve-textarea"
                value={tagline}
                onChange={(e) => setTagline(e.target.value)}
                rows={4}
                maxLength={256}
              />
            </label>
            <p className="eve-settings-hint">
              Shown on the command dashboard and available as {"{{ tagline }}"} in templates.
            </p>
          </EveWindow>

          <MoonTaxPanel
            settings={initial}
            taxRules={taxRules}
            logs={logs}
            invoices={invoices}
            defaultX={800}
            defaultY={4}
            defaultWidth={440}
            defaultHeight={520}
            onApplyTax={async ({ ruleId, r16, r32, r64 }) => {
              await patchTaxRule(ruleId, { r16_pct: r16, r32_pct: r32, r64_pct: r64 });
            }}
          />

          <AdminUserLookupPanel />
        </>
      ) : null}
    </>
  );

  if (embedded) return settingsWindows;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <StatusStrip>
        {admin ? "Administrator configuration" : "Settings"}
      </StatusStrip>

      {error ? <p className="eve-template-error px-1">{error}</p> : null}

      <DesktopSurface className="min-h-0 flex-1">{settingsWindows}</DesktopSurface>
    </div>
  );
}
