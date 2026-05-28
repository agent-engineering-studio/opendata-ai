import type { Metadata } from "next";
import { ClerkProvider, SignInButton, SignUpButton, SignedIn, SignedOut, UserButton } from "@clerk/nextjs";

import "./globals.css";

export const metadata: Metadata = {
  title: "OpenData AI",
  description:
    "Il tuo agente di intelligenza artificiale per gli open data — portali CKAN e statistiche ufficiali (ISTAT, Eurostat, OCSE)",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="it">
      <body className="min-h-screen antialiased">
        <ClerkProvider>
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
      </body>
    </html>
  );
}
