"use client";

import {
  ClerkProvider,
  SignInButton,
  SignUpButton,
  SignedIn,
  SignedOut,
  UserButton,
} from "@clerk/clerk-react";

// `@clerk/clerk-react` is pulled in only from this client boundary, so the
// app/layout.tsx Server Component (which owns metadata) never evaluates SWR
// under the `react-server` export condition.
const clerkPublishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export function AuthShell({ children }: { children: React.ReactNode }) {
  // Local builds (and the static prerender of /_not-found) run without a
  // Clerk key. Skip the provider in that case so the bundle still compiles;
  // CI/production always supply NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY.
  if (!clerkPublishableKey) {
    return <>{children}</>;
  }

  return (
    <ClerkProvider publishableKey={clerkPublishableKey}>
      <header className="flex items-center justify-end gap-2 px-6 py-3 text-sm">
        <SignedOut>
          <SignInButton mode="modal">
            <button className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-50">
              Accedi
            </button>
          </SignInButton>
          <SignUpButton mode="modal">
            <button className="rounded bg-slate-900 px-3 py-1 text-white hover:bg-slate-700">
              Registrati
            </button>
          </SignUpButton>
        </SignedOut>
        <SignedIn>
          <UserButton afterSignOutUrl="/" />
        </SignedIn>
      </header>
      {children}
    </ClerkProvider>
  );
}
