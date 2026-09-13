"use client";

import { useCallback, useEffect, useRef } from "react";
import clsx from "clsx";
import { Tooltip } from "./Tooltip";
import {
  useWindowManager,
  type WindowMode,
} from "./WindowManager";

const MIN_WIDTH = 220;
const MIN_HEIGHT = 72;
const TITLEBAR_H = 22;

type ResizeDir = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

const RESIZE_HANDLES: { dir: ResizeDir; className: string; label: string }[] = [
  { dir: "n", className: "eve-resize-n", label: "Resize top edge" },
  { dir: "s", className: "eve-resize-s", label: "Resize bottom edge" },
  { dir: "e", className: "eve-resize-e", label: "Resize right edge" },
  { dir: "w", className: "eve-resize-w", label: "Resize left edge" },
  { dir: "nw", className: "eve-resize-nw", label: "Resize top-left corner" },
  { dir: "ne", className: "eve-resize-ne", label: "Resize top-right corner" },
  { dir: "sw", className: "eve-resize-sw", label: "Resize bottom-left corner" },
  { dir: "se", className: "eve-resize-se", label: "Resize bottom-right corner" },
];

function WindowChromeControls({
  mode,
  onMinimize,
  onToggleMaximize,
  onClose,
}: {
  mode: WindowMode;
  onMinimize: (e: React.MouseEvent) => void;
  onToggleMaximize: (e: React.MouseEvent) => void;
  onClose: (e: React.MouseEvent) => void;
}) {
  const maxLabel = mode === "maximized" ? "Restore down" : "Maximize";

  return (
    <div className="eve-window-controls" onMouseDown={(e) => e.stopPropagation()}>
      <Tooltip label="Minimize" side="bottom">
        <button type="button" className="eve-wc-btn" aria-label="Minimize" onClick={onMinimize}>
          —
        </button>
      </Tooltip>
      <Tooltip label={maxLabel} side="bottom">
        <button type="button" className="eve-wc-btn" aria-label={maxLabel} onClick={onToggleMaximize}>
          □
        </button>
      </Tooltip>
      <Tooltip label="Close" side="bottom">
        <button type="button" className="eve-wc-btn eve-wc-close" aria-label="Close" onClick={onClose}>
          ×
        </button>
      </Tooltip>
    </div>
  );
}

function WindowResizeHandles({ onResizeStart }: { onResizeStart: (dir: ResizeDir, e: React.MouseEvent) => void }) {
  return (
    <>
      {RESIZE_HANDLES.map(({ dir, className, label }) => (
        <div
          key={dir}
          role="presentation"
          className={clsx("eve-resize-handle", className)}
          aria-label={label}
          onMouseDown={(e) => onResizeStart(dir, e)}
        />
      ))}
    </>
  );
}

export function EveWindow({
  id,
  title,
  children,
  className,
  actions,
  chrome = true,
  defaultX,
  defaultY,
  defaultWidth,
  defaultHeight,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
  className?: string;
  actions?: React.ReactNode;
  chrome?: boolean;
  defaultX?: number;
  defaultY?: number;
  defaultWidth?: number;
  defaultHeight?: number;
}) {
  const {
    windows,
    taskbarReserve,
    registerWindow,
    unregisterWindow,
    setMode,
    setPosition,
    setBounds,
    focusWindow,
    openWindow,
    minimizeWindow,
    maximizeWindow,
    restoreWindow,
    desktopRef,
  } = useWindowManager();

  const win = windows.find((w) => w.id === id);
  const windowRef = useRef<HTMLElement | null>(null);
  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(
    null
  );

  useEffect(() => {
    registerWindow({ id, title, defaultX, defaultY, defaultWidth, defaultHeight });
    return () => unregisterWindow(id);
  }, [id, title, defaultX, defaultY, defaultWidth, defaultHeight, registerWindow, unregisterWindow]);

  const mode: WindowMode = win?.mode ?? "closed";

  const minimize = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      minimizeWindow(id);
    },
    [id, minimizeWindow]
  );

  const close = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      setMode(id, "closed");
    },
    [id, setMode]
  );

  const toggleMaximize = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (mode === "minimized") {
        openWindow(id);
        focusWindow(id);
        return;
      }
      if (mode === "maximized") {
        restoreWindow(id);
        return;
      }
      if (win) {
        const h = win.height ?? windowRef.current?.offsetHeight ?? 200;
        setBounds(id, win.x, win.y, win.width, h);
      }
      maximizeWindow(id);
    },
    [id, mode, win, openWindow, focusWindow, restoreWindow, maximizeWindow, setBounds]
  );

  const getWindowHeight = useCallback(() => {
    if (win?.height) return win.height;
    return windowRef.current?.offsetHeight ?? 200;
  }, [win?.height]);

  const onResizeStart = useCallback(
    (dir: ResizeDir, e: React.MouseEvent) => {
      if (!win || mode !== "open") return;
      e.preventDefault();
      e.stopPropagation();
      focusWindow(id);

      const start = {
        clientX: e.clientX,
        clientY: e.clientY,
        x: win.x,
        y: win.y,
        width: win.width,
        height: getWindowHeight(),
      };

      const onMove = (ev: MouseEvent) => {
        if (!desktopRef.current) return;
        const desktop = desktopRef.current.getBoundingClientRect();
        const taskbarTop = taskbarReserve;
        const dx = ev.clientX - start.clientX;
        const dy = ev.clientY - start.clientY;

        let x = start.x;
        let y = start.y;
        let width = start.width;
        let height = start.height;

        if (dir.includes("e")) width = start.width + dx;
        if (dir.includes("w")) {
          width = start.width - dx;
          x = start.x + dx;
        }
        if (dir.includes("s")) height = start.height + dy;
        if (dir.includes("n")) {
          height = start.height - dy;
          y = start.y + dy;
        }

        width = Math.max(MIN_WIDTH, width);
        height = Math.max(MIN_HEIGHT, height);

        if (dir.includes("w")) x = start.x + (start.width - width);
        if (dir.includes("n")) y = start.y + (start.height - height);

        const maxW = desktop.width - x - 4;
        const maxH = desktop.height - y - TITLEBAR_H;
        width = Math.min(width, maxW);
        height = Math.min(height, maxH);

        x = Math.max(0, Math.min(x, desktop.width - MIN_WIDTH));
        y = Math.max(taskbarTop, Math.min(y, desktop.height - TITLEBAR_H));

        setBounds(id, x, y, width, height);
      };

      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        document.body.classList.remove("eve-resizing");
      };

      document.body.classList.add("eve-resizing");
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    },
    [id, mode, win, focusWindow, setBounds, desktopRef, getWindowHeight, taskbarReserve]
  );

  const onTitleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (mode === "maximized" || mode === "closed" || mode === "minimized") return;
      if ((e.target as HTMLElement).closest(".eve-window-controls")) return;
      if ((e.target as HTMLElement).closest(".eve-resize-handle")) return;
      e.preventDefault();
      focusWindow(id);
      dragRef.current = {
        startX: e.clientX,
        startY: e.clientY,
        origX: win?.x ?? 0,
        origY: win?.y ?? 0,
      };

      const onMove = (ev: MouseEvent) => {
        if (!dragRef.current || !desktopRef.current) return;
        const desktop = desktopRef.current.getBoundingClientRect();
        const dx = ev.clientX - dragRef.current.startX;
        const dy = ev.clientY - dragRef.current.startY;
        const w = win?.width ?? MIN_WIDTH;
        const maxX = Math.max(0, desktop.width - w);
        const maxY = Math.max(taskbarReserve, desktop.height - TITLEBAR_H);
        const x = Math.min(maxX, Math.max(0, dragRef.current.origX + dx));
        const y = Math.min(maxY, Math.max(taskbarReserve, dragRef.current.origY + dy));
        setPosition(id, x, y);
      };

      const onUp = () => {
        dragRef.current = null;
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    },
    [id, mode, win?.x, win?.y, win?.width, focusWindow, setPosition, desktopRef, taskbarReserve]
  );

  if (!win || mode === "closed" || mode === "minimized") {
    return null;
  }

  const sized = win.height !== null;

  const style =
    mode === "maximized"
      ? { zIndex: win.zIndex }
      : {
          left: win.x,
          top: win.y,
          width: win.width,
          ...(win.height ? { height: win.height } : {}),
          zIndex: win.zIndex,
        };

  return (
    <section
      ref={windowRef}
      className={clsx(
        "eve-window eve-window-floating",
        mode === "maximized" && "eve-window-maximized",
        sized && "eve-window-sized",
        className
      )}
      style={style}
      onMouseDown={() => focusWindow(id)}
    >
      <div
        className="eve-window-titlebar"
        onDoubleClick={toggleMaximize}
        onMouseDown={onTitleMouseDown}
      >
        <span className="eve-window-title">{title}</span>
        <div className="flex items-center gap-1">
          {actions}
          {chrome ? (
            <WindowChromeControls
              mode={mode}
              onMinimize={minimize}
              onToggleMaximize={toggleMaximize}
              onClose={close}
            />
          ) : null}
        </div>
      </div>
      <div className={clsx("eve-window-body eve-scroll", sized && "eve-window-body-fixed")}>
        {children}
      </div>
      {mode === "open" ? <WindowResizeHandles onResizeStart={onResizeStart} /> : null}
    </section>
  );
}
