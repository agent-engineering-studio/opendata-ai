"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { SignIn, SignedIn, SignedOut, useAuth } from "@clerk/clerk-react";

const hasClerk = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

function RedirectIfSignedIn() {
  const router = useRouter();
  const { isLoaded, isSignedIn } = useAuth();
  useEffect(() => {
    if (isLoaded && isSignedIn) router.replace("/esplora");
  }, [isLoaded, isSignedIn, router]);
  return null;
}

export default function Page() {
  return (
    <div className="container py-5">
      <div className="row g-5 align-items-start">
        <div className="col-lg-6">
          <h1 className="mb-3">Accedi a OpenData AI</h1>
          <p className="lead text-muted mb-4">
            Effettua l&apos;accesso per aprire la dashboard, salvare i dataset
            preferiti e scaricare risposte personalizzate.
          </p>

          {hasClerk ? (
            <>
              <SignedOut>
                <div className="d-flex justify-content-center justify-content-lg-start">
                  <SignIn
                    routing="hash"
                    signUpUrl="/sign-up"
                    afterSignInUrl="/esplora"
                    afterSignUpUrl="/esplora"
                  />
                </div>
              </SignedOut>
              <SignedIn>
                <RedirectIfSignedIn />
                <div className="alert alert-success" role="status">
                  <p className="mb-2">
                    <strong>Sei già autenticato.</strong> Reindirizzamento alla
                    dashboard in corso…
                  </p>
                  <Link href="/esplora" className="btn btn-primary btn-sm">
                    Vai a Esplora
                  </Link>
                </div>
              </SignedIn>
            </>
          ) : (
            <div className="alert alert-warning" role="alert">
              <h2 className="h5 alert-heading">Clerk non configurato in questa build</h2>
              <p className="mb-2">
                La variabile <code>NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY</code>{" "}
                non è impostata al build-time, quindi il form di login non
                può essere renderizzato. Per attivarlo in sviluppo locale
                segui uno dei due percorsi qui sotto.
              </p>

              <hr />

              <h3 className="h6 mt-3">Opzione A — Configura Clerk (login completo)</h3>
              <ol className="small mb-3">
                <li>
                  Recupera la <strong>publishable key</strong> dell&apos;app
                  Clerk <code>app_3EMALiLi0UTULl89JPMKtaLENoy</code> dalla
                  dashboard Clerk (
                  <a
                    href="https://dashboard.clerk.com/last-active?path=api-keys"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    dashboard.clerk.com → API Keys
                  </a>
                  ). Inizia con <code>pk_test_…</code>.
                </li>
                <li>
                  Crea il file{" "}
                  <code>opendata-ai-ui/.env.local</code> (è{" "}
                  <em>diverso</em> dall&apos;<code>.env.local</code> della
                  root del repo: Next.js legge solo da{" "}
                  <code>opendata-ai-ui/</code>):
                  <pre
                    className="bg-light border rounded p-2 small font-monospace mt-2 mb-2"
                    style={{ whiteSpace: "pre" }}
                  >
{`# opendata-ai-ui/.env.local
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_xxxxxxxxxxxxxxxxxxxx
NEXT_PUBLIC_API_URL=http://localhost:18000`}
                  </pre>
                </li>
                <li>
                  Rilancia il dev server: <code>npm run dev</code>{" "}
                  (oppure <code>npm run build &amp;&amp; npm start</code> se
                  stavi testando lo static export).
                </li>
              </ol>

              <h3 className="h6">Opzione B — Bypass auth (solo dev)</h3>
              <p className="small mb-2">
                Se vuoi solo vedere la dashboard senza configurare Clerk,
                disattiva l&apos;auth sul backend e usa un placeholder per la
                publishable key:
              </p>
              <pre
                className="bg-light border rounded p-2 small font-monospace mb-2"
                style={{ whiteSpace: "pre" }}
              >
{`# nel .env.local del backend (la root del repo)
AUTH_ENABLED=false

# nel opendata-ai-ui/.env.local
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_placeholder`}
              </pre>
              <p className="small mb-0">
                In questa modalità il backend tratta ogni request come
                <code> dev-user</code> e la UI mostra le route. Non usare in
                produzione. Vedi{" "}
                <Link href="/docs/setup">/docs/setup</Link> per il setup
                completo.
              </p>
            </div>
          )}
        </div>

        <div className="col-lg-6">
          <div className="card shadow-sm">
            <div className="card-body p-4">
              <h2 className="h4 mb-3">Cosa puoi fare in Esplora</h2>
              <ul className="list-unstyled mb-4">
                <li className="d-flex gap-3 mb-3">
                  <span className="badge bg-primary mt-1">1</span>
                  <div>
                    <strong>Chat + mappa nella stessa pagina</strong>
                    <p className="small text-muted mb-0">
                      Una domanda, l&apos;orchestrator fan-out su CKAN, ISTAT
                      ed Eurostat/OCSE con stato live. Le risorse geografiche
                      diventano automaticamente layer sulla mappa a destra.
                    </p>
                  </div>
                </li>
                <li className="d-flex gap-3 mb-3">
                  <span className="badge bg-primary mt-1">2</span>
                  <div>
                    <strong>Layer accumulati</strong>
                    <p className="small text-muted mb-0">
                      Le risorse Shapefile, GeoJSON, KML e WMS si sommano
                      sulla mappa di sessione in sessione. Un bottone
                      &ldquo;Pulisci layer&rdquo; resetta tutto.
                    </p>
                  </div>
                </li>
                <li className="d-flex gap-3 mb-3">
                  <span className="badge bg-primary mt-1">3</span>
                  <div>
                    <strong>Classify dataset</strong>
                    <p className="small text-muted mb-0">
                      Etichetta un dataset rispetto a una tassonomia
                      personalizzata. Cache 24h, costo bounded.
                    </p>
                  </div>
                </li>
                <li className="d-flex gap-3 mb-3">
                  <span className="badge bg-primary mt-1">4</span>
                  <div>
                    <strong>API keys per CI/CD</strong>
                    <p className="small text-muted mb-0">
                      Token a vita lunga per script, agenti A2A e quote
                      superiori (piano Pro <em>in arrivo</em>).
                    </p>
                  </div>
                </li>
              </ul>

              <hr />

              <h3 className="h6 text-uppercase text-muted mb-3" style={{ letterSpacing: "0.05em" }}>
                Non hai ancora un account?
              </h3>
              <p className="small mb-3">
                La registrazione avviene su Clerk. È gratuita e richiede solo
                un&apos;email valida.
              </p>
              <Link href="/sign-up" className="btn btn-outline-primary">
                Crea un account
              </Link>
            </div>
          </div>

          <div className="mt-4">
            <h3 className="h6 text-uppercase text-muted" style={{ letterSpacing: "0.05em" }}>
              Sei uno sviluppatore?
            </h3>
            <p className="small text-muted mb-2">
              Esplora la documentazione tecnica per integrare OpenData AI nel
              tuo stack agentico:
            </p>
            <div className="d-flex flex-wrap gap-2">
              <Link href="/docs/mcp" className="btn btn-sm btn-outline-secondary">
                MCP
              </Link>
              <Link href="/docs/a2a" className="btn btn-sm btn-outline-secondary">
                A2A
              </Link>
              <Link href="/docs/maf" className="btn btn-sm btn-outline-secondary">
                MAF
              </Link>
              <Link href="/docs/langgraph" className="btn btn-sm btn-outline-secondary">
                LangGraph
              </Link>
              <Link href="/docs/rate-limits" className="btn btn-sm btn-outline-secondary">
                Rate limits
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
