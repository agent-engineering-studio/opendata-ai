"use client";

/**
 * App-wide auth abstraction (#235, Fase 6) — decouples the UI from any specific
 * IdP. Backed by the dependency-free OIDC client (lib/oidc.ts) against a
 * self-hosted Keycloak; when OIDC is not configured it degrades to a no-auth
 * **dev mode** (mirrors backend `AUTH_ENABLED=false`): the visitor is treated
 * as an authenticated dev user and no token is sent.
 *
 * Replaces the previous vendor auth SDK. Components import `useAuth`, and the
 * declarative helpers `<SignedIn>` / `<SignedOut>` / `<SignInButton>` /
 * `<SignUpButton>` from here instead of a vendor SDK.
 */

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";

import { apiFetch } from "./api";
import * as oidc from "./oidc";

export const authConfigured = oidc.oidcConfigured;

type User = { sub: string; email: string | null; name: string | null } | null;

export interface AuthState {
  /** False until the initial session probe (callback / token load) settles. */
  isLoaded: boolean;
  isSignedIn: boolean;
  userId: string | null;
  user: User;
  /** RBAC role from the backend (`opendata.users.role`), null until resolved. */
  role: string | null;
  /** Just-in-time access token (auto-refreshes). Null in dev / when signed out. */
  getToken: () => Promise<string | null>;
  signIn: () => void;
  signUp: () => void;
  signOut: () => void;
}

const NO_AUTH: AuthState = {
  isLoaded: true,
  isSignedIn: false,
  userId: null,
  user: null,
  role: null,
  getToken: async () => null,
  signIn: () => {},
  signUp: () => {},
  signOut: () => {},
};

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [{ isLoaded, user, role }, setState] = useState<{
    isLoaded: boolean;
    user: User;
    role: string | null;
  }>({
    // In dev (no OIDC) we are immediately "loaded" with no session.
    isLoaded: !authConfigured,
    user: null,
    role: null,
  });

  useEffect(() => {
    let alive = true;
    (async () => {
      let profile: User = null;
      if (authConfigured) {
        try {
          if (oidc.hasCallbackParams()) {
            const ret = await oidc.handleRedirectCallback();
            window.history.replaceState({}, "", ret);
          }
          const token = await oidc.getAccessToken();
          profile = token ? oidc.getProfile() : null;
        } catch {
          profile = null;
        }
      }
      // Best-effort role from the backend. In dev (AUTH_ENABLED=false) the
      // backend returns the dev user as "admin"; when signed out, /me 401s and
      // role stays null. Never blocks rendering.
      let resolvedRole: string | null = null;
      try {
        const token = authConfigured ? await oidc.getAccessToken() : null;
        if (token || !authConfigured) {
          const res = await apiFetch("/me", { token });
          if (res.ok) resolvedRole = ((await res.json())?.role as string) ?? null;
        }
      } catch {
        /* ignore — role gating is a nicety, the backend still enforces */
      }
      if (alive) setState({ isLoaded: true, user: profile, role: resolvedRole });
    })();
    return () => {
      alive = false;
    };
  }, []);

  const getToken = useCallback(
    async () => (authConfigured ? await oidc.getAccessToken() : null),
    [],
  );

  const value: AuthState = {
    isLoaded,
    isSignedIn: !!user,
    userId: user?.sub ?? null,
    user,
    role,
    getToken,
    signIn: () => void oidc.login("login"),
    signUp: () => void oidc.login("register"),
    signOut: () => void oidc.logout(),
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  return useContext(Ctx) ?? NO_AUTH;
}

// ── Declarative helpers (replace Clerk's <SignedIn>/<SignedOut>/…) ──────────
//
// In dev mode (no OIDC configured) the app is fully open: <SignedIn> shows its
// children and <SignedOut> renders nothing. Callers that need a distinct
// marketing/keyless fallback branch on `authConfigured` themselves.

export function SignedIn({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn } = useAuth();
  if (!authConfigured) return <>{children}</>;
  return isLoaded && isSignedIn ? <>{children}</> : null;
}

export function SignedOut({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn } = useAuth();
  if (!authConfigured) return null;
  return isLoaded && !isSignedIn ? <>{children}</> : null;
}

/** Wraps a trigger element; clicking it starts the login redirect. */
export function SignInButton({ children }: { children: React.ReactNode; mode?: string }) {
  const { signIn } = useAuth();
  return (
    <span onClick={() => signIn()} style={{ display: "contents" }}>
      {children}
    </span>
  );
}

/** Wraps a trigger element; clicking it starts the registration redirect. */
export function SignUpButton({ children }: { children: React.ReactNode; mode?: string }) {
  const { signUp } = useAuth();
  return (
    <span onClick={() => signUp()} style={{ display: "contents" }}>
      {children}
    </span>
  );
}
