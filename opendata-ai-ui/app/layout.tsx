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
            Sticky-footer layout, IDENTICAL on every page. `main` is the scroll
            container; inside it `children` sit in a `flex-1` wrapper that GROWS
            to fill the viewport, so the footer is pushed to the bottom on short
            pages and flows after the content (scroll) on long ones — never
            pinned/floating mid-page. Full-bleed pages (chat/mappa) fill the
            wrapper via their own `h-100` roots, and the footer sits just below
            their chrome — same footer everywhere.
          */}
          <main
            id="main-content"
            className="flex flex-1 min-h-0 flex-col overflow-y-auto"
          >
            <div className="flex flex-1 min-h-0 flex-col">{children}</div>
            <SiteFooter />
          </main>
        </AuthShell>
      </body>
    </html>
  );
}
