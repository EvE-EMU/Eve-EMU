"use client";

import { useMemo, type CSSProperties, type ReactNode } from "react";

/** Convert EVE ARGB (#AARRGGBB) to CSS rgba(). */
function eveArgbToCss(hex: string): string | undefined {
  const m = hex.trim().match(/^#?([0-9a-fA-F]{8})$/);
  if (!m) {
    const short = hex.trim().match(/^#?([0-9a-fA-F]{6})$/);
    if (short) return `#${short[1]}`;
    return undefined;
  }
  const n = parseInt(m[1], 16);
  const a = ((n >> 24) & 0xff) / 255;
  const r = (n >> 16) & 0xff;
  const g = (n >> 8) & 0xff;
  const b = n & 0xff;
  if (a >= 0.99) return `rgb(${r}, ${g}, ${b})`;
  return `rgba(${r}, ${g}, ${b}, ${a.toFixed(3)})`;
}

function eveFontSizePx(size: string): string | undefined {
  const n = parseInt(size, 10);
  if (Number.isNaN(n)) return undefined;
  if (n <= 11) return "11px";
  if (n <= 13) return "12px";
  if (n <= 14) return "13px";
  return "14px";
}

function decodeHtmlEntities(text: string): string {
  return text
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

type StyleFrame = { size?: string; color?: string };

function parseFontAttrs(raw: string): StyleFrame {
  return {
    size: raw.match(/\bsize="(\d+)"/i)?.[1],
    color: raw.match(/\bcolor="(#[0-9a-fA-F]+)"/i)?.[1],
  };
}

function parseHref(raw: string): string {
  const href = raw.match(/\bhref="([^"]+)"/i)?.[1];
  return href ? decodeHtmlEntities(href) : "";
}

function stackStyle(stack: StyleFrame[]): CSSProperties {
  const style: CSSProperties = {};
  for (const frame of stack) {
    if (frame.color) {
      const css = eveArgbToCss(frame.color);
      if (css) style.color = css;
    }
    if (frame.size) {
      const px = eveFontSizePx(frame.size);
      if (px) style.fontSize = px;
    }
  }
  return style;
}

function EveMailLink({ href, children }: { href: string; children: ReactNode }) {
  const showinfo = href.match(/^showinfo:(\d+)\/\/(\d+)/i);
  if (showinfo) {
    const [, category, id] = showinfo;
    const isCharacter = category === "1377" || category === "16159";
    if (isCharacter) {
      return (
        <a
          href={`https://zkillboard.com/character/${id}/`}
          target="_blank"
          rel="noreferrer"
          className="eve-mail-link"
        >
          {children}
        </a>
      );
    }
    return (
      <span className="eve-mail-link" title={`showinfo:${category}//${id}`}>
        {children}
      </span>
    );
  }

  const contract = href.match(/^contract:(\d+)\/\/(\d+)/i);
  if (contract) {
    const contractId = contract[2];
    return (
      <a
        href={`https://evepraisal.com/a/${contractId}`}
        target="_blank"
        rel="noreferrer"
        className="eve-mail-link eve-mail-contract"
        title={`Contract ${contractId}`}
      >
        {children}
      </a>
    );
  }

  if (href.startsWith("http://") || href.startsWith("https://")) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className="eve-mail-link">
        {children}
      </a>
    );
  }

  return (
    <span className="eve-mail-link" title={href}>
      {children}
    </span>
  );
}

let nodeKey = 0;

function nextKey(prefix: string) {
  nodeKey += 1;
  return `${prefix}-${nodeKey}`;
}

function parseEveMailSegment(input: string, stack: StyleFrame[] = []): ReactNode[] {
  const nodes: ReactNode[] = [];
  const re = /<(\/?)(font|br|a)\b([^>]*)>|([^<]+)/gi;
  let match: RegExpExecArray | null;

  while ((match = re.exec(input)) !== null) {
    const text = match[4];
    if (text) {
      const style = stackStyle(stack);
      nodes.push(
        <span key={nextKey("t")} style={Object.keys(style).length ? style : undefined}>
          {text}
        </span>
      );
      continue;
    }

    const closing = match[1] === "/";
    const tag = match[2].toLowerCase();
    const attrs = match[3] || "";

    if (tag === "br") {
      nodes.push(<br key={nextKey("br")} />);
    } else if (tag === "font") {
      if (closing) {
        if (stack.length) stack.pop();
      } else {
        stack.push(parseFontAttrs(attrs));
      }
    } else if (tag === "a" && !closing) {
      const href = parseHref(attrs);
      const rest = input.slice(re.lastIndex);
      const closeMatch = /^([\s\S]*?)<\/a>/i.exec(rest);
      if (!closeMatch) continue;
      const inner = closeMatch[1];
      re.lastIndex += closeMatch[0].length;
      const innerNodes = parseEveMailSegment(inner, [...stack]);
      nodes.push(
        <span key={nextKey("a")} style={stackStyle(stack)}>
          <EveMailLink href={href}>{innerNodes}</EveMailLink>
        </span>
      );
    }
  }

  return nodes;
}

export function EveMailBody({ body }: { body: string }) {
  const nodes = useMemo(() => {
    nodeKey = 0;
    return parseEveMailSegment(decodeHtmlEntities(body || ""));
  }, [body]);

  if (!body?.trim()) {
    return <p className="text-[var(--text-muted)]">(empty body)</p>;
  }

  return <div className="eve-char-sheet-mail-body-html">{nodes}</div>;
}
