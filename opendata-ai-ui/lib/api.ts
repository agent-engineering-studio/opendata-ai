/**
 * Browser-side API client for the opendata-backend.
 *
 * Static export means the frontend has no server runtime — every request
 * goes directly from the browser to `NEXT_PUBLIC_API_URL`. Clerk attaches
 * the JWT via `useAuth().getToken()`.
 */

const RAW_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/+$/, "");

export function apiUrl(path: string): string {
  const slash = path.startsWith("/") ? "" : "/";
  return `${RAW_BASE}${slash}${path}`;
}

export interface ApiFetchOptions extends Omit<RequestInit, "headers"> {
  /** Bearer token from Clerk's useAuth().getToken(). May be null in dev when AUTH_ENABLED=false. */
  token?: string | null;
  headers?: Record<string, string>;
}

export async function apiFetch(path: string, opts: ApiFetchOptions = {}): Promise<Response> {
  const { token, headers, ...rest } = opts;
  const merged: Record<string, string> = {
    "Content-Type": "application/json",
    ...(headers ?? {}),
  };
  if (token) merged["Authorization"] = `Bearer ${token}`;
  return fetch(apiUrl(path), { ...rest, headers: merged });
}

/**
 * Server-side proxy for arbitrary file URLs (CSV/JSON/GeoJSON/KML/SHP zips).
 * The static UI can't run a Next.js proxy route anymore (`output: 'export'`),
 * so the backend exposes `GET /datasets/proxy?url=…` and we route through it.
 *
 * Returns the backend URL string — pass it to `fetch()` (with a Bearer token
 * via the `Authorization` header if AUTH_ENABLED=true).
 */
export function proxyUrl(targetUrl: string): string {
  return apiUrl(`/datasets/proxy?url=${encodeURIComponent(targetUrl)}`);
}

/** Convenience: GET the proxy URL with the standard Auth header pattern. */
export async function proxyFetch(
  targetUrl: string,
  opts: { token?: string | null; signal?: AbortSignal } = {},
): Promise<Response> {
  const headers: Record<string, string> = {};
  if (opts.token) headers["Authorization"] = `Bearer ${opts.token}`;
  return fetch(proxyUrl(targetUrl), { headers, signal: opts.signal });
}
