"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import {
  createDesktopBackground,
  deleteDesktopBackground,
  fetchAllDesktopBackgrounds,
  updateDesktopBackground,
  uploadDesktopBackground,
  type DesktopBackground,
} from "@/lib/desktopBackgrounds";
import { Tooltip } from "./Tooltip";

function BackgroundRow({
  row,
  onChange,
  onDelete,
}: {
  row: DesktopBackground;
  onChange: () => void;
  onDelete: () => void;
}) {
  const [busy, setBusy] = useState(false);

  const toggleActive = async () => {
    setBusy(true);
    try {
      await updateDesktopBackground(row.id, { active: !row.active });
      onChange();
    } catch {
      alert("Could not update background. Check API connection.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!confirm(`Remove "${row.label}" from rotation?`)) return;
    setBusy(true);
    try {
      await deleteDesktopBackground(row.id);
      onDelete();
    } catch {
      alert("Could not remove background. Check API connection.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={clsx("eve-admin-bg-row", !row.active && "eve-admin-bg-row--off")}>
      <div className="eve-admin-bg-row-main">
        <span className="eve-admin-bg-label">{row.label}</span>
        <span className="eve-admin-bg-url" title={row.video_url}>
          {row.video_url}
        </span>
      </div>
      <div className="eve-admin-bg-row-actions">
        <button type="button" className="eve-btn-sm" disabled={busy} onClick={toggleActive}>
          {row.active ? "Active" : "Off"}
        </button>
        <button type="button" className="eve-btn-sm eve-btn-danger" disabled={busy} onClick={remove}>
          Remove
        </button>
      </div>
    </div>
  );
}

export function AdminPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [rows, setRows] = useState<DesktopBackground[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [label, setLabel] = useState("");
  const [videoUrl, setVideoUrl] = useState("");
  const [uploadLabel, setUploadLabel] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRows(await fetchAllDesktopBackgrounds());
    } catch {
      setError("Could not load backgrounds. API may be unavailable.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) void reload();
  }, [open, reload]);

  const addBackground = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!label.trim() || !videoUrl.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await createDesktopBackground({
        label: label.trim(),
        video_url: videoUrl.trim(),
        active: true,
        sort_order: rows.length,
      });
      setLabel("");
      setVideoUrl("");
      await reload();
    } catch {
      setError("Failed to add background.");
    } finally {
      setSaving(false);
    }
  };

  const uploadBackground = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadLabel.trim() || !uploadFile) return;
    setUploading(true);
    setError(null);
    try {
      await uploadDesktopBackground(uploadFile, uploadLabel.trim());
      setUploadLabel("");
      setUploadFile(null);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload video.");
    } finally {
      setUploading(false);
    }
  };

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    setUploadFile(file);
    if (file && !uploadLabel.trim()) {
      const base = file.name.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ");
      setUploadLabel(base.slice(0, 128));
    }
  };

  if (!open) return null;

  return (
    <div className="eve-admin-overlay" role="dialog" aria-label="System administration">
      <button type="button" className="eve-admin-overlay-dismiss" aria-label="Close" onClick={onClose} />
      <section className="eve-admin-panel">
        <header className="eve-admin-panel-head">
          <div>
            <p className="eve-admin-panel-kicker">System Administration</p>
            <h2 className="eve-admin-panel-title">Desktop Backgrounds</h2>
          </div>
          <button type="button" className="eve-wc-btn eve-wc-close" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </header>

        <div className="eve-admin-panel-body eve-scroll">
          <p className="eve-admin-note">
            One background is active at a time. Activating a video turns off all others. Refresh the
            page to see the new desktop video.
          </p>

          <form className="eve-admin-form" onSubmit={uploadBackground}>
            <p className="eve-section-head">Upload video</p>
            <label className="eve-admin-field">
              <span>Label</span>
              <input
                className="eve-input"
                value={uploadLabel}
                onChange={(e) => setUploadLabel(e.target.value)}
                placeholder="Deep space drift"
                maxLength={128}
              />
            </label>
            <label className="eve-admin-field">
              <span>Video file (MP4, WebM, MOV — max 100 MB)</span>
              <input
                className="eve-file-input"
                type="file"
                accept="video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov"
                onChange={onFileChange}
              />
              {uploadFile ? (
                <span className="eve-admin-file-name">
                  {uploadFile.name} ({(uploadFile.size / (1024 * 1024)).toFixed(1)} MB)
                </span>
              ) : null}
            </label>
            <button
              type="submit"
              className="eve-btn-primary"
              disabled={uploading || !uploadFile || !uploadLabel.trim()}
            >
              {uploading ? "Uploading…" : "Upload & add to rotation"}
            </button>
          </form>

          <form className="eve-admin-form" onSubmit={addBackground}>
            <p className="eve-section-head">Or add by URL</p>
            <label className="eve-admin-field">
              <span>Label</span>
              <input
                className="eve-input"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="Deep space drift"
                maxLength={128}
              />
            </label>
            <label className="eve-admin-field">
              <span>Video URL (.mp4)</span>
              <input
                className="eve-input"
                value={videoUrl}
                onChange={(e) => setVideoUrl(e.target.value)}
                placeholder="https://…/background.mp4"
                maxLength={1024}
              />
            </label>
            <button type="submit" className="eve-btn-primary" disabled={saving}>
              {saving ? "Adding…" : "Add to rotation"}
            </button>
          </form>

          {error ? <p className="eve-admin-error">{error}</p> : null}

          <p className="eve-section-head">Rotation pool ({rows.length})</p>
          {loading ? (
            <p className="eve-admin-muted">Loading…</p>
          ) : rows.length === 0 ? (
            <p className="eve-admin-muted">No backgrounds configured.</p>
          ) : (
            <div className="eve-admin-bg-list">
              {rows.map((row) => (
                <BackgroundRow
                  key={row.id}
                  row={row}
                  onChange={reload}
                  onDelete={reload}
                />
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

export function AdminGear() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Tooltip label="Administration" hint="Desktop backgrounds & system settings" side="right" className="eve-neocom-tooltip">
        <button
          type="button"
          className="eve-admin-gear"
          aria-label="System administration"
          onClick={() => setOpen(true)}
        >
          <IconGear className="h-5 w-5" />
        </button>
      </Tooltip>
      <AdminPanel open={open} onClose={() => setOpen(false)} />
    </>
  );
}

function IconGear({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
      <circle cx="8" cy="8" r="2.2" />
      <path d="M8 1.8v1.6M8 12.6v1.6M1.8 8H3.4M12.6 8h1.6M3.4 3.4l1.1 1.1M11.5 11.5l1.1 1.1M3.4 12.6l1.1-1.1M11.5 4.5l1.1-1.1" />
      <path d="M8 4.2l.9-.5.3 1 .9.3-.6.8.1 1-.9-.5-.9.5.1-1-.6-.8.9-.3.3-1 .9.5z" opacity="0" />
    </svg>
  );
}
