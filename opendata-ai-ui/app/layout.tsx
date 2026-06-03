import type { Metadata } from "next";
import { AuthShell } from "@/components/AuthShell";
import { SiteHeader } from "@/components/SiteHeader";
import { SiteFooter } from "@/components/SiteFooter";

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
      <body className="min-h-screen flex flex-col antialiased">
        <AuthShell>
          <a href="#main-content" className="visually-hidden-focusable">
            Vai al contenuto principale
          </a>
          <SiteHeader />
          <main id="main-content" className="flex flex-1 min-h-0 flex-col">
            {children}
          </main>
          <SiteFooter />
        </AuthShell>
      </body>
    </html>
  );
}
