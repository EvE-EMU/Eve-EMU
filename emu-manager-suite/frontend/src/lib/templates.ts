import type { Template } from "@/lib/api";

export type TemplateUpdate = {
  subject?: string;
  body?: string;
  name?: string;
};

export type TemplateRenderResult = {
  subject: string;
  body: string;
};

export function parseTemplateVariables(template: Template): string[] {
  try {
    const raw = JSON.parse(template.variables_json || "[]") as unknown;
    if (!Array.isArray(raw)) return [];
    return raw.map((v) => String(v));
  } catch {
    return [];
  }
}

const SAMPLE_VALUES: Record<string, string> = {
  character_name: "Citizen Alpha",
  structure_name: "DS-LO3 — PUBLIC P9M1",
  total_due_isk: "42,500,000",
  invoice_number: "INV-2401",
  bill_count: "14",
  total_isk: "6,617,702,295",
  tagline: "MOON OUTPUT FOR THE WAR EFFORT — EVERY BAR REFINED COUNTS",
  week_label: "Week 24",
  structure_count: "12",
  total_volume: "310,406",
};

export function sampleVariables(names: string[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const name of names) {
    out[name] =
      SAMPLE_VALUES[name] ??
      name
        .split("_")
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ");
  }
  return out;
}

/** Client-side preview for simple `{{ variable }}` Jinja placeholders. */
export function renderTemplateLocal(text: string, variables: Record<string, string>): string {
  return text.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (_, name: string) => variables[name] ?? `[${name}]`);
}

export async function updateTemplate(id: number, payload: TemplateUpdate): Promise<Template> {
  const res = await fetch(`/api/templates/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to save template");
  return res.json() as Promise<Template>;
}

export async function renderTemplate(
  id: number,
  variables: Record<string, string>
): Promise<TemplateRenderResult> {
  const res = await fetch(`/api/templates/${id}/render`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ variables }),
  });
  if (!res.ok) throw new Error("Failed to render preview");
  return res.json() as Promise<TemplateRenderResult>;
}

export function formatPreviewHtml(text: string, channel: string): string {
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  if (channel === "discord") {
    return escaped
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/\n/g, "<br />");
  }
  if (channel === "report") {
    return escaped
      .replace(/^# (.+)$/gm, "<h3 class=\"eve-template-h\">$1</h3>")
      .replace(/\n/g, "<br />");
  }
  return escaped.replace(/\n/g, "<br />");
}
