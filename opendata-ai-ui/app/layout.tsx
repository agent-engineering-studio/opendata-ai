import type { Metadata } from "next";
import { AuthShell } from "@/components/AuthShell";
import { SiteHeader } from "@/components/SiteHeader";
import { SiteFooter } from "@/components/SiteFooter";

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
            Footer is a SIBLING of `main` (not inside it). The body is a
            100vh flex column: header (auto) + main (flex-1, its OWN scroll via
            overflow-y-auto) + footer (auto). So the footer is anchored just
            below `main` — at the viewport bottom on every page — while `main`
            scrolls its content ABOVE it. Full-bleed pages (esplora chat, mappa)
            fill `main` exactly via their `h-100` roots, so the footer sits
            below their chrome without overlapping it; long pages (territorio,
            maturità, landing) scroll inside `main`, never over the footer.
            Identical footer everywhere. (Putting the footer inside `main`
            broke this — the chat input and page bodies overlapped it.)
          */}
          <main
            id="main-content"
            className="flex flex-1 min-h-0 flex-col overflow-y-auto"
          >
            {children}
          </main>
          <SiteFooter />
        </AuthShell>
      </body>
    </html>
  );
}
