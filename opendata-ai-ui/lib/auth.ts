"use client";

import { useAuth as useClerkAuth } from "@clerk/clerk-react";

const hasClerk = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

function useNoAuth() {
  return { getToken: async () => null as string | null };
}

// Tiny indirection over Clerk's `useAuth` so prerender works when no key is
// configured (local builds, /_not-found export). `hasClerk` is a constant
// per build, so the chosen hook is stable for the lifetime of the bundle.
export const useAuth = hasClerk ? useClerkAuth : useNoAuth;
