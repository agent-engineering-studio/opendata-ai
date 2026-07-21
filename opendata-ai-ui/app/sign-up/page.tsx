"use client";

import { useEffect } from "react";
import { authConfigured, useAuth } from "@/lib/auth";

// Registration is hosted by the OIDC issuer (Keycloak — SPID or the simple
// name/surname/email + email-code form). This page kicks off the redirect.
export default function Page() {
  const { signUp } = useAuth();
  useEffect(() => {
    if (authConfigured) signUp();
  }, [signUp]);
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <p className="text-sm text-slate-500">
        {authConfigured
          ? "Reindirizzamento alla registrazione…"
          : "Autenticazione non configurata in questa build (modalità sviluppo)."}
      </p>
    </div>
  );
}
