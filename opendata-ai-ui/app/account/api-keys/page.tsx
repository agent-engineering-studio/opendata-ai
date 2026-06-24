"use client";

import Image from "next/image";
import Link from "next/link";
import { DashboardGate } from "@/components/DashboardGate";

function Inner() {
  return (
    <div className="container py-5">
      <p className="text-muted small mb-2">
        <Link href="/esplora">← Torna a Esplora</Link>
      </p>
      <h1 className="mb-3">API keys</h1>
      <p className="lead text-muted">
        Le API keys ti permettono di chiamare il backend OpenData AI da script,
        CI/CD e agenti A2A senza dover gestire il JWT utente. In futuro
        sbloccheranno anche rate limit superiori (oggi: 60 richieste/min su
        finestra fissa per ogni utente Clerk).
      </p>

      <div className="text-center mt-4">
        <Image
          src="/coming-soon.svg"
          alt="Coming soon…"
          width={800}
          height={340}
          priority
          className="img-fluid"
          style={{ maxWidth: 560, height: "auto" }}
        />
        <p className="text-muted small mt-3 mb-0">
          La generazione e gestione di API keys dal pannello utente è in
          sviluppo. Per ora puoi usare l&apos;endpoint{" "}
          <code>POST /api-keys/generate</code> via JWT Clerk — vedi{" "}
          <Link href="/docs/api-keys">/docs/api-keys</Link> per uso, quota e
          buone pratiche.
        </p>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <DashboardGate>
      <Inner />
    </DashboardGate>
  );
}
