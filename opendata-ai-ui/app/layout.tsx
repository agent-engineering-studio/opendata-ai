import type { Metadata } from "next";
import { AuthShell } from "@/components/AuthShell";
import { SiteHeader } from "@/components/SiteHeader";
import { ConditionalFooter } from "@/components/ConditionalFooter";

import "./globals.css";

export const metadata: Metadata = {
  title: "OpenData AI",
  description:
    "Il tuo agente di intelligenza artificiale per gli open data — portali CKAN e statistiche ufficiali (ISTAT, Eurostat, OCSE)",
  icons: { icon: "/logo-mark.svg" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="it">
      <body className="min-h-screen flex flex-col antialiased">
        <AuthShell>
          <a href="#main-content" className="visually-hidden-focusable">
            Vai al contenuto principale
          </a>
          <SiteHeader />
          {/*
            `overflow-y-auto` is the key here: chat/mappa fill `main` exactly
            via internal `h-100` children (no overflow → no scrollbar shown),
            while long-form pages (landing, docs, /privacy…) scroll inside
            `main`. The footer lives INSIDE `main` (via ConditionalFooter) so it
            scrolls at the END of the page instead of being pinned to the
            viewport bottom — the previous sibling-of-`main` footer overlapped
            the landing. It's hidden on the full-bleed app pages.
          */}
          <main
            id="main-content"
            className="flex flex-1 min-h-0 flex-col overflow-y-auto"
          >
            {children}
            <ConditionalFooter />
          </main>
        </AuthShell>
      </body>
    </html>
  );
}
