"use client";

import Link from "next/link";
import { SignInButton, SignUpButton, SignedIn, SignedOut } from "@clerk/clerk-react";

const hasClerk = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

type Variant = "hero" | "footer";

/**
 * Auth-aware CTA cluster shown on the landing.
 *
 * - SignedOut → "Accedi" (modal) + "Registrati" (modal): the user has to
 *   authenticate first, no point pushing them to /dashboard which would
 *   just bounce back to /login.
 * - SignedIn  → "Apri la dashboard" + "Apri la mappa": one-click into the
 *   product.
 *
 * The `hero` variant uses light outline buttons over the dark primary-900
 * hero band; the `footer` variant uses solid primary buttons for the dark
 * final CTA band.
 *
 * Falls through to public links when Clerk isn't configured at build time
 * (local prerender, /_not-found export) so the bundle still compiles.
 */
export function AuthAwareCTAs({ variant }: { variant: Variant }) {
  const primary =
    variant === "hero" ? "btn btn-primary btn-lg" : "btn btn-primary btn-lg";
  const secondary =
    variant === "hero"
      ? "btn btn-outline-light btn-lg"
      : "btn btn-outline-light btn-lg";

  if (!hasClerk) {
    // Build-time fallback. Show the SignedOut shape — best default for a
    // first-time visitor in environments without Clerk wired up.
    return (
      <>
        <Link href="/login" className={primary}>
          Accedi
        </Link>
        <Link href="/sign-up" className={secondary}>
          Registrati
        </Link>
      </>
    );
  }

  return (
    <>
      <SignedOut>
        <SignInButton mode="modal">
          <button type="button" className={primary}>
            Accedi
          </button>
        </SignInButton>
        <SignUpButton mode="modal">
          <button type="button" className={secondary}>
            Registrati
          </button>
        </SignUpButton>
      </SignedOut>
      <SignedIn>
        <Link href="/esplora" className={primary}>
          Apri Esplora
        </Link>
      </SignedIn>
    </>
  );
}
