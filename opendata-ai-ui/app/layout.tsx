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
            `overflow-y-auto` is the key here: chat/mappa fill `main` exactly
            via internal `flex-1` children (no overflow → no scrollbar shown),
            while long-form pages like /info or /privacy scroll inside `main`
            instead of pushing their <article> visually over the footer.
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
