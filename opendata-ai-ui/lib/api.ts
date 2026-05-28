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
