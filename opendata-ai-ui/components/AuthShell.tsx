"use client";

import { ClerkProvider } from "@clerk/clerk-react";

// `@clerk/clerk-react` is pulled in only from this client boundary, so the
// app/layout.tsx Server Component (which owns metadata) never evaluates SWR
// under the `react-server` export condition.
const clerkPublishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

// Italian PA Design System tokens — keep in sync with globals.css @theme.
const PA_PRIMARY = "#0066CC";
const PA_PRIMARY_HOVER = "#004080";
const PA_DANGER = "#D9364F";
const PA_TEXT = "#17324D";
const PA_FONT = '"Titillium Web", system-ui, -apple-system, sans-serif';

const clerkAppearance = {
  variables: {
    colorPrimary: PA_PRIMARY,
    colorDanger: PA_DANGER,
    colorText: PA_TEXT,
    fontFamily: PA_FONT,
    borderRadius: "4px",
  },
  elements: {
    formButtonPrimary: {
      backgroundColor: PA_PRIMARY,
      "&:hover, &:focus, &:active": {
        backgroundColor: PA_PRIMARY_HOVER,
      },
    },
    card: {
      borderRadius: "4px",
      boxShadow: "0 2px 8px rgba(0, 0, 0, 0.08)",
    },
  },
} as const;

export function AuthShell({ children }: { children: React.ReactNode }) {
  // Local builds (and the static prerender of /_not-found) run without a
  // Clerk key. Skip the provider in that case so the bundle still compiles;
  // CI/production always supply NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY.
  if (!clerkPublishableKey) {
    return <>{children}</>;
  }
  return (
    <ClerkProvider
      publishableKey={clerkPublishableKey}
      appearance={clerkAppearance}
    >
      {children}
    </ClerkProvider>
  );
}
