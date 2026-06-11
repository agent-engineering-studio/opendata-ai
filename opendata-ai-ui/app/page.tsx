import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { AuthAwareCTAs } from "@/components/AuthAwareCTAs";

export const metadata: Metadata = {
  title: "OpenData AI — orchestratore di agenti per gli open data italiani ed europei",
  description:
    "Una chat che interroga in parallelo CKAN, ISTAT, Eurostat e OCSE, restituisce sintesi narrativa e disegna le risorse geografiche su mappa. REST, MCP e A2A pronti per l'integrazione.",
};

export default function Page() {
  return (
    <div className="bg-bg-muted">
      {/* HERO */}
      <section className="bg-primary-900 text-white">
        <div className="container py-5">
          <div className="row align-items-center g-5 py-4">
            <div className="col-lg-7">
              <p className="mb-2 text-uppercase small fw-semibold" style={{ letterSpacing: "0.1em", opacity: 0.8 }}>
                Progetto sperimentale · Italian PA Design System
              </p>
              <h1 className="display-4 fw-bold mb-3">
                Un agente che parla la lingua degli open data italiani ed europei
              </h1>
              <p className="lead mb-4" style={{ opacity: 0.95 }}>
                OpenData AI è un orchestratore che interroga in parallelo i
                portali CKAN (dati.gov.it e portali municipali/regionali) e le
                statistiche ufficiali via SDMX 2.1 (ISTAT, Eurostat, OCSE),
                produce una sintesi narrativa in italiano e disegna le risorse
                geografiche su OpenStreetMap. Un unico endpoint per fare
                domande in linguaggio naturale — niente più caccia al dataset
                tra decine di cataloghi.
              </p>
              <div className="d-flex flex-wrap gap-3">
                <AuthAwareCTAs variant="hero" />
                <Link href="/docs" className="btn btn-outline-light btn-lg">
                  Documentazione
                </Link>
              </div>
            </div>
            <div className="col-lg-5">
              <div
                className="bg-white text-dark rounded shadow-lg p-4"
                style={{ fontFamily: "var(--font-mono)", fontSize: "0.85rem" }}
              >
                <div className="d-flex align-items-center gap-2 mb-3 text-muted small">
                  <span className="rounded-circle bg-danger" style={{ width: 10, height: 10 }} />
                  <span className="rounded-circle bg-warning" style={{ width: 10, height: 10 }} />
                  <span className="rounded-circle bg-success" style={{ width: 10, height: 10 }} />
                  <span className="ms-2">chat — opendata-ai</span>
                </div>
                <p className="mb-2"><span className="text-primary fw-bold">▸ tu:</span> qualità dell&apos;aria a Milano nel 2024</p>
                <p className="mb-2 small text-muted">Interrogo Catalogo CKAN…</p>
                <p className="mb-2 small text-muted">Interrogo ISTAT…</p>
                <p className="mb-2 small text-success">CKAN ha risposto · 7 dataset</p>
                <p className="mb-2 small text-success">ISTAT ha risposto · 2 cubi SDMX</p>
                <p className="mb-2 small text-muted">Sintesi finale in corso…</p>
                <p className="mb-0">
                  <span className="text-primary fw-bold">▸ agente:</span> Nel
                  2024 ARPA Lombardia ha pubblicato 7 dataset orari per le
                  centraline di Milano. Le serie PM2.5 e NO₂ mostrano…
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* IN UNA RIGA */}
      <section className="container py-5">
        <div className="row g-4 text-center">
          <div className="col-md-3">
            <h3 className="display-6 fw-bold text-primary mb-1">4</h3>
            <p className="text-muted mb-0">fonti dati ufficiali in parallelo</p>
          </div>
          <div className="col-md-3">
            <h3 className="display-6 fw-bold text-primary mb-1">3</h3>
            <p className="text-muted mb-0">server MCP componibili</p>
          </div>
          <div className="col-md-3">
            <h3 className="display-6 fw-bold text-primary mb-1">A2A</h3>
            <p className="text-muted mb-0">agent card pubblica</p>
          </div>
          <div className="col-md-3">
            <h3 className="display-6 fw-bold text-primary mb-1">REST</h3>
            <p className="text-muted mb-0">streaming NDJSON autenticato</p>
          </div>
        </div>
      </section>

      {/* COSA FA */}
      <section className="bg-white border-top border-bottom">
        <div className="container py-5">
          <div className="row">
            <div className="col-lg-8 mx-auto text-center mb-5">
              <h2 className="mb-3">Una domanda, quattro specialisti</h2>
              <p className="lead text-muted">
                Una sola query in linguaggio naturale viene smistata in
                parallelo. Ogni specialista risponde con la propria visione
                della stessa domanda; un agente di sintesi fonde i risultati in
                una narrativa coerente con riferimenti puntuali alle risorse.
              </p>
            </div>
          </div>

          <div className="row g-4">
            <div className="col-md-6 col-lg-3">
              <div className="card h-100 shadow-sm">
                <div className="card-body">
                  <span className="badge bg-primary mb-2">CKAN</span>
                  <h5 className="card-title">Cataloghi open</h5>
                  <p className="card-text small text-muted mb-0">
                    Interroga qualsiasi portale CKAN-compatibile. Default
                    <code> dati.gov.it</code>, ma con un parametro punta a
                    data.gov.uk, open.canada.ca, data.gov.au o a un portale
                    municipale.
                  </p>
                </div>
              </div>
            </div>
            <div className="col-md-6 col-lg-3">
              <div className="card h-100 shadow-sm">
                <div className="card-body">
                  <span className="badge bg-primary mb-2">SDMX 2.1</span>
                  <h5 className="card-title">Statistiche ufficiali</h5>
                  <p className="card-text small text-muted mb-0">
                    Stessa interfaccia per ISTAT, Eurostat e OCSE. Dataflows,
                    code lists e osservazioni filtrate per dimensione. Le
                    risposte vengono normalizzate in CSV scaricabile.
                  </p>
                </div>
              </div>
            </div>
            <div className="col-md-6 col-lg-3">
              <div className="card h-100 shadow-sm">
                <div className="card-body">
                  <span className="badge bg-primary mb-2">OSM</span>
                  <h5 className="card-title">Geocoding + mappa</h5>
                  <p className="card-text small text-muted mb-0">
                    Nominatim per il geocoding, Overpass per POI, OSRM per il
                    routing, Leaflet+OSM per il render finale. Le risorse
                    GeoJSON, KML e Shapefile diventano layer accendibili.
                  </p>
                </div>
              </div>
            </div>
            <div className="col-md-6 col-lg-3">
              <div className="card h-100 shadow-sm">
                <div className="card-body">
                  <span className="badge bg-secondary mb-2">Sintesi</span>
                  <h5 className="card-title">Risposta unica</h5>
                  <p className="card-text small text-muted mb-0">
                    Un LLM (Claude Haiku/Sonnet o Ollama locale) ricuce le
                    risposte degli specialisti in italiano, citando ogni
                    risorsa con il portale di origine.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* PER CHI */}
      <section className="container py-5">
        <div className="row g-5">
          <div className="col-lg-6">
            <h2 className="mb-3">Per chi è</h2>
            <ul className="list-unstyled">
              <li className="mb-3">
                <strong>Giornalisti di dati e ricercatori</strong> — un
                ricercatore può chiedere &ldquo;serie storica della spesa
                sanitaria pro capite in Italia&rdquo; e ricevere insieme il
                dataflow ISTAT, l&apos;equivalente Eurostat e — se esistono —
                dataset municipali correlati.
              </li>
              <li className="mb-3">
                <strong>Sviluppatori e integratori</strong> — REST autenticato
                con Clerk, MCP via stdio o streamable-http, A2A su JSON-RPC.
                Tre superfici programmabili pensate per essere componibili.
              </li>
              <li className="mb-3">
                <strong>Pubbliche amministrazioni</strong> — UI conforme al
                Design System italiano (Bootstrap Italia + Design React Kit),
                WCAG 2.1 AA, deployment on-prem o cloud sovrano.
              </li>
              <li className="mb-3">
                <strong>Builder di agenti</strong> — i tre MCP server
                (CKAN, ISTAT, OSM) si collegano a Claude Desktop, Cursor,
                Microsoft Agent Framework, LangGraph o qualsiasi client MCP.
              </li>
            </ul>
          </div>
          <div className="col-lg-6">
            <h2 className="mb-3">Come si integra</h2>
            <p className="text-muted">
              Tre superfici, un solo backend. Scegli quella più adatta al tuo
              caso d&apos;uso.
            </p>
            <div className="list-group">
              <Link href="/docs/mcp" className="list-group-item list-group-item-action">
                <div className="d-flex justify-content-between align-items-start">
                  <div>
                    <h6 className="mb-1">MCP — Model Context Protocol</h6>
                    <p className="small text-muted mb-0">
                      3 server (CKAN, ISTAT, OSM) usabili da qualunque client MCP
                    </p>
                  </div>
                  <span className="badge bg-light text-dark">stdio · http</span>
                </div>
              </Link>
              <Link href="/docs/a2a" className="list-group-item list-group-item-action">
                <div className="d-flex justify-content-between align-items-start">
                  <div>
                    <h6 className="mb-1">A2A — Agent-to-Agent</h6>
                    <p className="small text-muted mb-0">
                      AgentCard pubblica + JSON-RPC SendMessage
                    </p>
                  </div>
                  <span className="badge bg-light text-dark">SDK 1.0 + 0.3</span>
                </div>
              </Link>
              <Link href="/docs" className="list-group-item list-group-item-action">
                <div className="d-flex justify-content-between align-items-start">
                  <div>
                    <h6 className="mb-1">REST diretto</h6>
                    <p className="small text-muted mb-0">
                      <code>/datasets/search/stream</code> NDJSON,{" "}
                      <code>/datasets/classify</code> con cache 24h
                    </p>
                  </div>
                  <span className="badge bg-light text-dark">JWT Clerk</span>
                </div>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ARCHITETTURA */}
      <section className="bg-white border-top">
        <div className="container py-5">
          <h2 className="mb-4">Architettura in 30 secondi</h2>
          <div className="row g-4 align-items-center">
            <div className="col-lg-8">
              <div className="bg-light border rounded p-3">
                <Image
                  src="/architecture.svg"
                  alt="Mind map dell'architettura di OpenData AI: il backend al centro è connesso alla UI Next.js, all'auth Clerk, agli agenti A2A esterni, ai provider LLM, a Postgres+Redis e ai tre server MCP (CKAN, ISTAT, OSM) che parlano con i portali open data."
                  width={960}
                  height={560}
                  style={{ width: "100%", height: "auto" }}
                  priority
                />
              </div>
            </div>
            <div className="col-lg-4">
              <h5>Punti chiave</h5>
              <ul>
                <li>Frontend statico, nessun runtime server-side.</li>
                <li>
                  Autenticazione Clerk: ogni endpoint REST/A2A è dietro JWT,
                  eccetto <code>/health</code>.
                </li>
                <li>
                  Cache a tre livelli per classify: Redis 24h → Postgres
                  durable → Anthropic Haiku 4.5.
                </li>
                <li>
                  Rate limit a finestra fissa per minuto, basato su Redis
                  (default 60 req/min/utente). Vedi{" "}
                  <Link href="/docs/rate-limits">/docs/rate-limits</Link>.
                </li>
                <li>
                  MCP server e backend buildati con context al repo root, una
                  sola immagine per ambiente.
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ESEMPI CODICE */}
      <section className="container py-5">
        <h2 className="mb-4">Mostrami il codice</h2>
        <div className="row g-4">
          <div className="col-md-6">
            <h5>
              <span className="badge bg-dark me-2">cURL</span>
              REST streaming
            </h5>
            <pre
              className="bg-light border rounded p-3 small font-monospace"
              style={{ overflowX: "auto", whiteSpace: "pre" }}
            >
{`curl -N -X POST https://api.opendata-ai.it/datasets/search/stream \\
  -H 'Authorization: Bearer <clerk_jwt>' \\
  -H 'Content-Type: application/json' \\
  -d '{"query":"popolazione di Milano per età"}'`}
            </pre>
          </div>
          <div className="col-md-6">
            <h5>
              <span className="badge bg-dark me-2">Python</span>
              A2A SendMessage
            </h5>
            <pre
              className="bg-light border rounded p-3 small font-monospace"
              style={{ overflowX: "auto", whiteSpace: "pre" }}
            >
{`from a2a.client import A2AClient

client = A2AClient("https://api.opendata-ai.it/a2a/")
reply = client.send_message(
    "qualità dell'aria a Milano",
    metadata={"skill": "search_open_data"},
)
print(reply.artifacts[0].parts[0].text)`}
            </pre>
          </div>
        </div>
        <div className="text-center mt-4">
          <Link href="/docs" className="btn btn-outline-primary">
            Tutta la documentazione →
          </Link>
        </div>
      </section>

      {/* CTA FINALE */}
      <section className="bg-primary-900 text-white">
        <div className="container py-5 text-center">
          <h2 className="mb-3">Pronto a fare la prima domanda?</h2>
          <p className="lead mb-4" style={{ opacity: 0.9 }}>
            La dashboard è gratuita per l&apos;uso esplorativo. Bastano un
            account e un secondo per il primo prompt. In futuro un piano
            abbonamento sbloccherà rate limit superiori.
          </p>
          <div className="d-flex flex-wrap justify-content-center gap-3">
            <AuthAwareCTAs variant="footer" />
          </div>
          <p className="mt-4 small" style={{ opacity: 0.7 }}>
            Le risposte dell&apos;agente dipendono da modelli LLM esterni e
            possono contenere errori — verifica sempre i dati consultando la
            fonte indicata.
          </p>
        </div>
      </section>
    </div>
  );
}
