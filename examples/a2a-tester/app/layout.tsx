import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "A2A Tester — opendata-ai",
  description: "Client minimale per provare le skill A2A del backend OpenData AI.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="it">
      <body
        style={{
          margin: 0,
          fontFamily:
            "system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
          background: "#f6f8fa",
          color: "#0e2233",
        }}
      >
        {children}
      </body>
    </html>
  );
}
