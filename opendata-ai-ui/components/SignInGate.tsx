"use client";

import { SignedIn, SignedOut, SignInButton, SignUpButton } from "@clerk/clerk-react";

const hasClerk = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

/**
 * Renders `signedIn` to authenticated users and an inline sign-in CTA to
 * everyone else. Mirrors the existing pattern in `SiteHeader`: when Clerk
 * isn't configured at build time (local prerender, /_not-found), fall
 * straight through to `signedIn` so the bundle still compiles.
 *
 * The CTA replaces the chat input on `/` and the map controls on `/mappa`
 * — without it, logged-out users see a normal-looking textbox, submit, and
 * collect "Errore HTTP 401" with no hint that they need to authenticate.
 */
export function SignInGate({ signedIn }: { signedIn: React.ReactNode }) {
  if (!hasClerk) return <>{signedIn}</>;
  return (
    <>
      <SignedIn>{signedIn}</SignedIn>
      <SignedOut>
        <div className="border-t border-slate-200 bg-slate-50 px-4 py-5 text-center">
          <p className="mb-3 text-sm text-slate-600">
            Accedi per inviare domande all&apos;orchestrator.
          </p>
          <div className="flex items-center justify-center gap-2">
            <SignInButton mode="modal">
              <button type="button" className="btn btn-primary btn-sm">
                Accedi
              </button>
            </SignInButton>
            <SignUpButton mode="modal">
              <button type="button" className="btn btn-outline-primary btn-sm">
                Registrati
              </button>
            </SignUpButton>
          </div>
        </div>
      </SignedOut>
    </>
  );
}
