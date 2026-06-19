"use client";

import Link from "next/link";
import type { CSSProperties } from "react";
import { SignUpButton, SignedIn, SignedOut } from "@clerk/clerk-react";

const hasClerk = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

type Variant = "hero" | "final";

/**
 * CTA primaria auth-aware della landing.
 *
 * - `hero`  → pill gradiente brand. SignedOut apre il SignUp modale ("Analizza
 *   un territorio"); SignedIn linka direttamente a /territorio.
 * - `final` → pill bianca sul fondo gradiente della CTA conclusiva. SignedOut
 *   "Crea un account gratuito" (SignUp modale); SignedIn "Apri l'analisi".
 *
 * La secondaria (anchor "Guarda come funziona" / link "Sostieni il progetto")
 * è statica e vive in `app/page.tsx`. Senza Clerk configurato, fallback ai
 * link pubblici così il bundle statico compila comunque.
 */

const PILL: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 9,
  borderRadius: 999,
  textDecoration: "none",
  border: 0,
  cursor: "pointer",
};

function styleFor(variant: Variant): CSSProperties {
  if (variant === "hero") {
    return {
      ...PILL,
      padding: "15px 28px",
      fontSize: 17,
      fontWeight: 600,
      background: "var(--gradient-brand)",
      color: "#fff",
      boxShadow: "var(--shadow-brand)",
    };
  }
  return {
    ...PILL,
    padding: "15px 30px",
    fontSize: 17,
    fontWeight: 700,
    background: "#fff",
    color: "#0E47A1",
    boxShadow: "0 10px 28px rgba(0,0,0,.18)",
  };
}

export function AuthAwareCTAs({ variant }: { variant: Variant }) {
  const style = styleFor(variant);
  const signedOutLabel =
    variant === "hero" ? "Analizza un territorio" : "Crea un account gratuito";
  const signedInLabel =
    variant === "hero" ? "Analizza un territorio" : "Apri l'analisi";

  if (!hasClerk) {
    return (
      <Link href="/login" style={style}>
        {signedOutLabel}
      </Link>
    );
  }

  return (
    <>
      <SignedOut>
        <SignUpButton mode="modal">
          <button type="button" style={style}>
            {signedOutLabel}
          </button>
        </SignUpButton>
      </SignedOut>
      <SignedIn>
        <Link href="/territorio" style={style}>
          {signedInLabel}
        </Link>
      </SignedIn>
    </>
  );
}
