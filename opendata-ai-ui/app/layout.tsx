import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CKAN MCP Agent — Demo",
  description:
    "Chat UI demo for the CKAN MCP server + Microsoft Agent Framework agent",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="it">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
