"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  SignedIn,
  SignedOut,
  useAuth as useClerkAuth,
} from "@clerk/clerk-react";

const hasClerk = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

/**
 * Client-side route gate for `/dashboard/*` and `/mappa`.
 *
 * Static export (R6) means we can't use Next middleware: the redirect has to
 * happen in the browser. While Clerk resolves the session we render a small
 * placeholder; once `<SignedOut>` matches we navigate to `/login` and the
 * SignIn form takes over. When the build is keyless (local prerender of
 * /_not-found, CI without Clerk env) the gate is a no-op.
 */
function GateRedirect() {
  const router = useRouter();
  const { isLoaded, isSignedIn } = useClerkAuth();

  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      router.replace("/login");
    }
  }, [isLoaded, isSignedIn, router]);

  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <p className="text-sm text-slate-500">Reindirizzamento al login…</p>
    </div>
  );
}

export function DashboardGate({ children }: { children: React.ReactNode }) {
  if (!hasClerk) return <>{children}</>;
  return (
    <>
      <SignedIn>{children}</SignedIn>
      <SignedOut>
        <GateRedirect />
      </SignedOut>
    </>
  );
}
