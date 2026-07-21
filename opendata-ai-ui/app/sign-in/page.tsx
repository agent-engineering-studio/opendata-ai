"use client";

import { useEffect } from "react";
import { authConfigured, useAuth } from "@/lib/auth";

// Login is hosted by the OIDC issuer (Keycloak — SPID / email-OTP). This page
// just kicks off the redirect; there is no embedded form anymore.
export default function Page() {
  const { signIn } = useAuth();
  useEffect(() => {
    if (authConfigured) signIn();
  }, [signIn]);
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <p className="text-sm text-slate-500">
        {authConfigured
          ? "Reindirizzamento al login…"
          : "Autenticazione non configurata in questa build (modalità sviluppo)."}
      </p>
    </div>
  );
}
