"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { authConfigured, useAuth } from "@/lib/auth";

/**
 * Login entry point. Authentication is delegated to the OIDC issuer (Keycloak —
 * SPID or the simple name/surname/email + email-code registration), so this
 * page redirects: signed-in → /esplora; signed-out → start the login redirect.
 * In dev (no OIDC configured) it shows a short setup hint instead.
 */
export default function Page() {
  const router = useRouter();
  const { isLoaded, isSignedIn, signIn } = useAuth();

  useEffect(() => {
    if (!authConfigured || !isLoaded) return;
    if (isSignedIn) {
      router.replace("/esplora");
    } else {
      signIn();
    }
  }, [isLoaded, isSignedIn, signIn, router]);

  return (
    <div className="container py-5 text-center">
      {authConfigured ? (
        <p className="text-muted">Reindirizzamento…</p>
      ) : (
        <div className="mx-auto" style={{ maxWidth: 640 }}>
          <h1 className="h4 mb-3">Autenticazione non configurata</h1>
          <p className="text-muted">
            Questa build è in modalità sviluppo (nessun IdP OIDC). Per abilitare
            login e registrazione (SPID o email con codice) imposta{" "}
            <code>NEXT_PUBLIC_OIDC_AUTHORITY</code> e{" "}
            <code>NEXT_PUBLIC_OIDC_CLIENT_ID</code> verso il tuo Keycloak.
          </p>
        </div>
      )}
    </div>
  );
}
