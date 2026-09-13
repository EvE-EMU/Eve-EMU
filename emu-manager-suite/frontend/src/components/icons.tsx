/** Minimal monochrome stroke icons — EVE client style. */

type IconProps = { className?: string };

export function IconCommand({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
      <rect x="1.5" y="1.5" width="5" height="5" />
      <rect x="9.5" y="1.5" width="5" height="5" />
      <rect x="1.5" y="9.5" width="5" height="5" />
      <rect x="9.5" y="9.5" width="5" height="5" />
    </svg>
  );
}

export function IconMoons({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
      <circle cx="8" cy="8" r="5.5" />
      <path d="M11 4.5a4 4 0 1 0 0 7" />
    </svg>
  );
}

export function IconTemplates({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
      <path d="M3 2.5h7l3 3V13.5H3z" />
      <path d="M10 2.5v3h3" />
      <path d="M5.5 8h5M5.5 10.5h5" />
    </svg>
  );
}

export function IconSettings({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
      <circle cx="8" cy="8" r="2" />
      <path d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.05 3.05l1.06 1.06M11.9 11.9l1.06 1.06M3.05 12.95l1.06-1.06M11.9 4.1l1.06-1.06" />
    </svg>
  );
}

export function IconApi({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
      <path d="M6 3H3.5v9H6M10 6l3-3v10l-3-3" />
    </svg>
  );
}

export function IconHub({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
      <circle cx="8" cy="8" r="2" />
      <path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.05 3.05l1.4 1.4M11.55 11.55l1.4 1.4M3.05 12.95l1.4-1.4M11.55 4.45l1.4-1.4" />
    </svg>
  );
}

export function IconCommerce({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
      <path d="M2 4h12v8H2zM5 4V2h6v2" />
      <path d="M6 8h4" />
    </svg>
  );
}

export function IconIntel({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
      <circle cx="8" cy="8" r="5.5" />
      <circle cx="8" cy="8" r="1.5" />
      <path d="M8 2.5v2M8 11.5v2" />
    </svg>
  );
}

export function IconIndustry({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
      <path d="M3 13V6l3-2v9M9 13V3l4 2v8H3" />
      <path d="M6 8h2" />
    </svg>
  );
}

export function IconAdmin({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
      <path d="M8 1.5l6 3v4c0 3.5-2.5 6-6 6.5C4.5 14.5 2 12 2 8.5v-4l6-3z" />
      <path d="M6 8l1.5 1.5L10 7" />
    </svg>
  );
}

export function IconSde({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
      <ellipse cx="8" cy="8" rx="6" ry="3.5" />
      <path d="M2 8v2.5c0 1.9 2.7 3.5 6 3.5s6-1.6 6-3.5V8" />
      <path d="M2 5.5V8M14 5.5V8" />
    </svg>
  );
}

export function IconLogOff({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
      <path d="M6 2.5H3.5v11H6M9.5 8H13M13 8l-2-2M13 8l-2 2" />
    </svg>
  );
}

export function IconCloseAll({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
      <rect x="2.5" y="3" width="11" height="8" rx="0.5" />
      <path d="M5.5 3V2h5v1M6 10.5h4" />
      <path d="M4 6.5l8 4M12 6.5l-8 4" strokeWidth="1" />
    </svg>
  );
}

export function IconChevronPanel({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <path d="M10 3.5L5.5 8 10 12.5" />
    </svg>
  );
}

export function IconMap({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
      <path d="M2 3.5l4-1.5 4 1.5 4-1.5v10l-4 1.5-4-1.5-4 1.5z" />
      <path d="M6 2v10M10 3.5v10" />
    </svg>
  );
}
