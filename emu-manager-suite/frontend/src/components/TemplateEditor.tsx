"use client";

import { useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { EveWindow } from "@/components/ui";
import type { Template } from "@/lib/api";
import {
  formatPreviewHtml,
  parseTemplateVariables,
  renderTemplateLocal,
  sampleVariables,
  updateTemplate,
} from "@/lib/templates";

type ViewMode = "edit" | "preview";

function wrapSelection(
  textarea: HTMLTextAreaElement,
  before: string,
  after: string,
  value: string,
  onChange: (next: string) => void
) {
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const selected = value.slice(start, end);
  const next = value.slice(0, start) + before + selected + after + value.slice(end);
  onChange(next);
  requestAnimationFrame(() => {
    textarea.focus();
    const cursor = start + before.length + selected.length + after.length;
    textarea.setSelectionRange(cursor, cursor);
  });
}

function insertAtCursor(
  textarea: HTMLTextAreaElement,
  token: string,
  value: string,
  onChange: (next: string) => void
) {
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const next = value.slice(0, start) + token + value.slice(end);
  onChange(next);
  requestAnimationFrame(() => {
    textarea.focus();
    const cursor = start + token.length;
    textarea.setSelectionRange(cursor, cursor);
  });
}

export function TemplateEditorWindow({
  template,
  index,
}: {
  template: Template;
  index: number;
}) {
  const bodyRef = useRef<HTMLTextAreaElement>(null);
  const [subject, setSubject] = useState(template.subject);
  const [body, setBody] = useState(template.body);
  const [baseline, setBaseline] = useState({ subject: template.subject, body: template.body });
  const [mode, setMode] = useState<ViewMode>("edit");
  const [varsOpen, setVarsOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const variables = useMemo(
    () => parseTemplateVariables(template),
    [template.variables_json]
  );
  const previewVars = useMemo(() => sampleVariables(variables), [variables]);
  const previewSubject = useMemo(
    () => renderTemplateLocal(subject, previewVars),
    [subject, previewVars]
  );
  const previewBody = useMemo(
    () => renderTemplateLocal(body, previewVars),
    [body, previewVars]
  );

  const dirty = subject !== baseline.subject || body !== baseline.body;
  const showSubject = template.channel === "mail" || Boolean(subject.trim());

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await updateTemplate(template.id, { subject, body });
      setBaseline({ subject, body });
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2000);
    } catch {
      setError("Could not save template.");
    } finally {
      setSaving(false);
    }
  };

  const insertVariable = (name: string) => {
    const el = bodyRef.current;
    if (!el) {
      setBody((b) => `${b}{{ ${name} }}`);
      return;
    }
    insertAtCursor(el, `{{ ${name} }}`, body, setBody);
  };

  const format = (before: string, after: string) => {
    const el = bodyRef.current;
    if (!el) return;
    wrapSelection(el, before, after, body, setBody);
  };

  const titleActions = (
    <button
      type="button"
      className={clsx("eve-btn-sm", dirty && "eve-template-save-pulse")}
      disabled={!dirty || saving}
      onClick={() => void save()}
    >
      {saving ? "Saving…" : saved ? "Saved" : "Save"}
    </button>
  );

  return (
    <EveWindow
      id={`template-${template.slug}`}
      title={template.name}
      actions={titleActions}
      defaultX={4 + (index % 2) * 420}
      defaultY={4 + Math.floor(index / 2) * 280}
      defaultWidth={400}
      defaultHeight={360}
    >
      <div className="eve-template-editor">
        <div className="eve-template-meta">
          <span className={clsx("eve-template-channel", `eve-template-channel--${template.channel}`)}>
            {template.channel}
          </span>
          <span className="eve-template-slug">{template.slug}</span>
        </div>

        <div className="eve-template-toolbar">
          <div className="eve-template-toolbar-group">
            <button
              type="button"
              className={clsx("eve-template-tab", mode === "edit" && "eve-template-tab--active")}
              onClick={() => setMode("edit")}
            >
              Edit
            </button>
            <button
              type="button"
              className={clsx("eve-template-tab", mode === "preview" && "eve-template-tab--active")}
              onClick={() => setMode("preview")}
            >
              Preview
            </button>
          </div>

          {mode === "edit" ? (
            <div className="eve-template-toolbar-group">
              {template.channel === "discord" ? (
                <>
                  <button type="button" className="eve-template-fmt" title="Bold" onClick={() => format("**", "**")}>
                    B
                  </button>
                  <button type="button" className="eve-template-fmt" title="Italic" onClick={() => format("*", "*")}>
                    I
                  </button>
                </>
              ) : null}
              <button
                type="button"
                className={clsx("eve-template-vars-btn", varsOpen && "eve-template-vars-btn--open")}
                onClick={() => setVarsOpen((v) => !v)}
                aria-expanded={varsOpen}
              >
                {"{ }"} Variables
              </button>
            </div>
          ) : null}
        </div>

        {varsOpen && mode === "edit" ? (
          <div className="eve-template-vars-panel">
            <p className="eve-template-vars-hint">
              Click a variable to insert at the cursor. Jinja syntax:{" "}
              <code className="eve-template-code">{"{{ name }}"}</code>
            </p>
            <div className="eve-template-vars-list">
              {variables.length === 0 ? (
                <span className="eve-template-vars-empty">No variables declared for this template.</span>
              ) : (
                variables.map((name) => (
                  <button
                    key={name}
                    type="button"
                    className="eve-template-var-chip"
                    onClick={() => insertVariable(name)}
                    title={`Insert {{ ${name} }}`}
                  >
                    <span className="eve-template-var-chip-label">{name}</span>
                    <span className="eve-template-var-chip-token">{`{{ ${name} }}`}</span>
                  </button>
                ))
              )}
            </div>
          </div>
        ) : null}

        {error ? <p className="eve-template-error">{error}</p> : null}

        {mode === "edit" ? (
          <div className="eve-template-fields">
            {showSubject ? (
              <label className="eve-template-field">
                <span>Subject</span>
                <input
                  className="eve-input"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="Message subject…"
                />
              </label>
            ) : null}
            <label className="eve-template-field eve-template-field--grow">
              <span>Message body</span>
              <textarea
                ref={bodyRef}
                className="eve-textarea eve-template-body-input"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                rows={10}
                spellCheck
              />
            </label>
          </div>
        ) : (
          <div className="eve-template-preview">
            {showSubject && previewSubject ? (
              <div className="eve-template-preview-subject">
                <span className="eve-template-preview-label">Subject</span>
                <p>{previewSubject}</p>
              </div>
            ) : null}
            <div
              className="eve-template-preview-body"
              dangerouslySetInnerHTML={{
                __html: formatPreviewHtml(previewBody, template.channel),
              }}
            />
          </div>
        )}
      </div>
    </EveWindow>
  );
}
