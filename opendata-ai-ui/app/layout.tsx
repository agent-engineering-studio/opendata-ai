import type { Metadata } from "next";
import { AuthShell } from "@/components/AuthShell";

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
        <AuthShell>{children}</AuthShell>
      </body>
    </html>
  );
}
