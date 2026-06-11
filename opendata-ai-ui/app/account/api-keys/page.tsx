"use client";

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

      <div className="alert alert-info mt-4" role="status">
        <h2 className="h5 alert-heading">In arrivo</h2>
        <p className="mb-0">
          La generazione e gestione di API keys dal pannello utente è in
          sviluppo. Per ora puoi usare l&apos;endpoint{" "}
          <code>POST /api-keys/generate</code> via JWT Clerk — vedi{" "}
          <Link href="/docs/rate-limits">/docs/rate-limits</Link> per i
          dettagli sulla quota.
        </p>
      </div>

      <div className="row g-3 mt-3">
        <div className="col-md-6">
          <div className="card h-100 shadow-sm">
            <div className="card-body">
              <span className="badge bg-light text-dark mb-2">Piano gratuito</span>
              <h3 className="h6">Esplorazione + sviluppo</h3>
              <ul className="small text-muted mb-0">
                <li>60 richieste/min/utente (finestra fissa)</li>
                <li>Cache classify 24h</li>
                <li>Accesso a tutte le superfici (REST, MCP, A2A)</li>
              </ul>
            </div>
          </div>
        </div>
        <div className="col-md-6">
          <div className="card h-100 shadow-sm border-primary">
            <div className="card-body">
              <span className="badge bg-primary mb-2">Piano Pro (in arrivo)</span>
              <h3 className="h6">Carichi server-to-server</h3>
              <ul className="small text-muted mb-0">
                <li>Quota personalizzata (es. 1000+ req/min)</li>
                <li>API key dedicate per CI/CD e bot A2A</li>
                <li>Bucket separato dal token utente</li>
                <li>SLA + supporto prioritario</li>
              </ul>
            </div>
          </div>
        </div>
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
