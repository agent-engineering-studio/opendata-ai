/**
 * Dependency-free OIDC Authorization-Code + PKCE client (#235, Fase 6).
 *
 * The frontend is a static export (`output: 'export'`, R6) — no server, no API
 * routes — so authentication runs entirely in the browser against a standard
 * OIDC issuer (self-hosted **Keycloak**, which brokers SPID and hosts the local
 * email-OTP registration). No vendor SDK: just `fetch`, Web Crypto for PKCE and
 * `localStorage` for tokens. This keeps the bundle lean and the supply-chain
 * surface minimal — important for a public-administration self-host.
 *
 * When the OIDC env is not set the app runs in **no-auth dev mode** (mirrors the
 * backend `AUTH_ENABLED=false`): `getAccessToken` returns null and the UI treats
 * the visitor as an authenticated dev user (see lib/auth.tsx).
 *
 * Everything here touches browser globals, so call only from effects/handlers —
 * never at module load (module scope reads env only, safe during prerender).
 */

const AUTHORITY = (process.env.NEXT_PUBLIC_OIDC_AUTHORITY ?? "").replace(/\/+$/, "");
const CLIENT_ID = process.env.NEXT_PUBLIC_OIDC_CLIENT_ID ?? "";
const SCOPE = process.env.NEXT_PUBLIC_OIDC_SCOPE ?? "openid profile email";

/** True when the deployment configured an OIDC issuer + client id. */
export const oidcConfigured = !!(AUTHORITY && CLIENT_ID);

const TOKENS_KEY = "oda_oidc_tokens";
const PKCE_KEY = "oda_oidc_pkce";
const STATE_KEY = "oda_oidc_state";
const RETURN_KEY = "oda_oidc_return";

interface StoredTokens {
  access_token: string;
  refresh_token?: string;
  id_token?: string;
  expires_at: number; // epoch ms, already skew-adjusted
}

export interface OidcProfile {
  sub: string;
  email: string | null;
  name: string | null;
}

interface OidcMeta {
  authorization_endpoint: string;
  token_endpoint: string;
  end_session_endpoint?: string;
  userinfo_endpoint?: string;
}

let _meta: OidcMeta | null = null;

async function discover(): Promise<OidcMeta> {
  if (_meta) return _meta;
  const res = await fetch(`${AUTHORITY}/.well-known/openid-configuration`);
  if (!res.ok) throw new Error(`OIDC discovery failed: ${res.status}`);
  _meta = (await res.json()) as OidcMeta;
  return _meta;
}

function base64url(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function randomString(bytes = 48): string {
  const a = new Uint8Array(bytes);
  crypto.getRandomValues(a);
  return base64url(a);
}

async function pkceChallenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return base64url(new Uint8Array(digest));
}

// The redirect URI is the app root — the one path guaranteed to exist in a
// static export. Register `https://<host>/*` (or exactly the root) as a valid
// redirect URI on the Keycloak client. The pre-login path is restored from
// sessionStorage after the callback, so the user lands back where they were.
function redirectUri(): string {
  return `${window.location.origin}/`;
}

function loadTokens(): StoredTokens | null {
  try {
    const raw = localStorage.getItem(TOKENS_KEY);
    return raw ? (JSON.parse(raw) as StoredTokens) : null;
  } catch {
    return null;
  }
}

function storeTokens(t: {
  access_token: string;
  refresh_token?: string;
  id_token?: string;
  expires_in?: number;
}): void {
  const ttl = typeof t.expires_in === "number" ? t.expires_in : 300;
  const stored: StoredTokens = {
    access_token: t.access_token,
    refresh_token: t.refresh_token,
    id_token: t.id_token,
    expires_at: Date.now() + ttl * 1000 - 30_000, // 30s clock-skew safety
  };
  localStorage.setItem(TOKENS_KEY, JSON.stringify(stored));
}

function clearTokens(): void {
  localStorage.removeItem(TOKENS_KEY);
}

function decodeJwt(jwt: string): Record<string, unknown> | null {
  try {
    const payload = jwt.split(".")[1];
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** Start a login (or registration) by redirecting to the OIDC issuer. */
export async function login(kind: "login" | "register" = "login"): Promise<void> {
  const meta = await discover();
  const verifier = randomString();
  const state = randomString(16);
  sessionStorage.setItem(PKCE_KEY, verifier);
  sessionStorage.setItem(STATE_KEY, state);
  sessionStorage.setItem(RETURN_KEY, window.location.pathname + window.location.search);
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    response_type: "code",
    scope: SCOPE,
    redirect_uri: redirectUri(),
    state,
    code_challenge: await pkceChallenge(verifier),
    code_challenge_method: "S256",
  });
  // Keycloak (and OIDC core) honour `prompt=create` to land on the registration
  // form (SPID / email-OTP) instead of the login form.
  if (kind === "register") params.set("prompt", "create");
  window.location.assign(`${meta.authorization_endpoint}?${params.toString()}`);
}

/** True when the current URL carries an OIDC authorization-code callback. */
export function hasCallbackParams(): boolean {
  const p = new URLSearchParams(window.location.search);
  return p.has("code") && p.has("state");
}

/** Exchange the callback code for tokens. Returns the pre-login path to restore. */
export async function handleRedirectCallback(): Promise<string> {
  const p = new URLSearchParams(window.location.search);
  const code = p.get("code");
  const state = p.get("state");
  const verifier = sessionStorage.getItem(PKCE_KEY);
  if (!code || !verifier || state !== sessionStorage.getItem(STATE_KEY)) {
    throw new Error("OIDC callback state mismatch");
  }
  const meta = await discover();
  const res = await fetch(meta.token_endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      redirect_uri: redirectUri(),
      client_id: CLIENT_ID,
      code_verifier: verifier,
    }).toString(),
  });
  if (!res.ok) throw new Error(`OIDC token exchange failed: ${res.status}`);
  storeTokens(await res.json());
  const ret = sessionStorage.getItem(RETURN_KEY) || "/";
  sessionStorage.removeItem(PKCE_KEY);
  sessionStorage.removeItem(STATE_KEY);
  sessionStorage.removeItem(RETURN_KEY);
  return ret;
}

async function refresh(refreshToken: string): Promise<string | null> {
  const meta = await discover();
  const res = await fetch(meta.token_endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: refreshToken,
      client_id: CLIENT_ID,
    }).toString(),
  });
  if (!res.ok) return null;
  storeTokens(await res.json());
  return loadTokens()?.access_token ?? null;
}

/** Valid access token, refreshing if expired. Null when signed out / dev mode. */
export async function getAccessToken(): Promise<string | null> {
  if (!oidcConfigured) return null;
  const t = loadTokens();
  if (!t) return null;
  if (Date.now() < t.expires_at) return t.access_token;
  if (t.refresh_token) {
    const refreshed = await refresh(t.refresh_token).catch(() => null);
    if (refreshed) return refreshed;
  }
  clearTokens();
  return null;
}

/** Profile of the signed-in user, decoded from the id token. */
export function getProfile(): OidcProfile | null {
  const t = loadTokens();
  if (!t?.id_token) return null;
  const claims = decodeJwt(t.id_token);
  if (!claims) return null;
  const sub = typeof claims.sub === "string" ? claims.sub : null;
  if (!sub) return null;
  const name =
    (typeof claims.name === "string" && claims.name) ||
    (typeof claims.preferred_username === "string" && claims.preferred_username) ||
    null;
  const email = typeof claims.email === "string" ? claims.email : null;
  return { sub, email, name };
}

/** Sign out locally and, when supported, at the issuer (RP-initiated logout). */
export async function logout(): Promise<void> {
  const t = loadTokens();
  clearTokens();
  try {
    const meta = await discover();
    if (meta.end_session_endpoint) {
      const params = new URLSearchParams({
        client_id: CLIENT_ID,
        post_logout_redirect_uri: `${window.location.origin}/`,
      });
      if (t?.id_token) params.set("id_token_hint", t.id_token);
      window.location.assign(`${meta.end_session_endpoint}?${params.toString()}`);
      return;
    }
  } catch {
    /* fall through to a local redirect */
  }
  window.location.assign("/");
}
