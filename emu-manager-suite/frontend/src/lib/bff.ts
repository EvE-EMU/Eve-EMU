/** Shared EMUMS backend proxy config for Next.js route handlers. */

import { NextRequest, NextResponse } from "next/server";

const INVALID_PUBLIC_HOSTS = new Set(["0.0.0.0", "[::]", "::", "127.0.0.1"]);

/** Public browser origin for redirects (never use container bind address 0.0.0.0). */
export function publicAppOrigin(req: NextRequest): string {
  const configured =
    process.env.EMUMS_PUBLIC_BASE_URL?.trim() ||
    process.env.NEXT_PUBLIC_EMUMS_BASE_URL?.trim();
  if (configured) {
    return configured.replace(/\/$/, "");
  }

  const forwardedHost = req.headers.get("x-forwarded-host")?.split(",")[0]?.trim();
  const forwardedProto = req.headers.get("x-forwarded-proto")?.split(",")[0]?.trim() || "https";
  if (forwardedHost) {
    const hostname = forwardedHost.split(":")[0];
    if (!INVALID_PUBLIC_HOSTS.has(hostname)) {
      return `${forwardedProto}://${forwardedHost}`;
    }
  }

  const hostname = req.nextUrl.hostname;
  if (!INVALID_PUBLIC_HOSTS.has(hostname)) {
    return `${req.nextUrl.protocol}//${req.nextUrl.host}`;
  }

  return "http://localhost:3020";
}

export function publicAppUrl(req: NextRequest, path: string): URL {
  return new URL(path, `${publicAppOrigin(req)}/`);
}

export const EMUMS_API_URL = process.env.EMUMS_API_URL || "http://127.0.0.1:8020/v1";
export const EMUMS_API_KEY = process.env.EMUMS_API_KEY || "emums-dev-key-change-me";

export function emumsBackendHeaders(extra?: HeadersInit): HeadersInit {
  return { "X-EMUMS-Key": EMUMS_API_KEY, ...extra };
}

/** Forward browser session cookie to the FastAPI backend. */
export function emumsSessionHeaders(req: Request): HeadersInit {
  const cookie = req.headers.get("cookie") ?? "";
  const match = cookie.match(/(?:^|;\s*)emums_session=([^;]+)/);
  return match ? { "X-EMUMS-Session": decodeURIComponent(match[1]) } : {};
}

export function emumsAuthedBackendFetch(path: string, req: Request, init?: RequestInit): Promise<Response> {
  const url = path.startsWith("http") ? path : `${EMUMS_API_URL}${path}`;
  return fetch(url, {
    cache: "no-store",
    ...init,
    headers: {
      ...emumsBackendHeaders(),
      ...emumsSessionHeaders(req),
      ...(init?.headers || {}),
    },
  });
}

/** Proxy to the FastAPI backend (no-store). */
export function emumsBackendFetch(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith("http") ? path : `${EMUMS_API_URL}${path}`;
  return fetch(url, {
    cache: "no-store",
    ...init,
    headers: { ...emumsBackendHeaders(), ...(init?.headers || {}) },
  });
}

export async function emumsJsonResponse(res: Response): Promise<NextResponse> {
  return NextResponse.json(await res.json(), { status: res.status });
}

export async function emumsTextJsonResponse(res: Response): Promise<NextResponse> {
  const body = await res.text();
  return new NextResponse(body, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
