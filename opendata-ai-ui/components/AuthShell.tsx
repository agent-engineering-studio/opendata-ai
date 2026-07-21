"use client";

import { AuthProvider } from "@/lib/auth";

// Auth boundary for the app (#235, Fase 6). Wraps the tree in the OIDC-backed
// AuthProvider (self-hosted Keycloak). When OIDC is not configured the provider
// runs in no-auth dev mode, so the bundle still compiles and the static
// prerender (/_not-found) works without any IdP env.
export function AuthShell({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}
