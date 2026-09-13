"use client";

import { TemplateEditorWindow } from "@/components/TemplateEditor";
import { DesktopSurface } from "@/components/WindowManager";
import { StatusStrip } from "@/components/ui";
import type { Template } from "@/lib/api";

export function TemplatesWorkspace({ templates, embedded }: { templates: Template[]; embedded?: boolean }) {
  const windows = (
    <>
      {templates.map((t, i) => (
        <TemplateEditorWindow key={t.id} template={t} index={i} />
      ))}
    </>
  );

  if (embedded) return windows;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <StatusStrip>
        Message templates · edit content, insert variables, preview before send
      </StatusStrip>
      <DesktopSurface className="min-h-0 flex-1">{windows}</DesktopSurface>
    </div>
  );
}
