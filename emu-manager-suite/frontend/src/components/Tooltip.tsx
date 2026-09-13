"use client";

import clsx from "clsx";

export function Tooltip({
  label,
  hint,
  children,
  side = "top",
  className,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
  side?: "top" | "right" | "bottom";
  className?: string;
}) {
  return (
    <span
      className={clsx("eve-tooltip-wrap", hint && "eve-tooltip-wrap--rich", className)}
      data-side={side}
    >
      {children}
      <span className="eve-tooltip" role="tooltip">
        <span className="eve-tooltip-label">{label}</span>
        {hint ? <span className="eve-tooltip-hint">{hint}</span> : null}
      </span>
    </span>
  );
}
