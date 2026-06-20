import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Portale Sviluppatori — OpenData AI",
  description:
    "OpenData AI è open source (licenza MIT). Usalo in abbonamento integrando la piattaforma nel tuo framework di agenti via protocollo A2A, oppure in self-host con lo stack completo (backend, server MCP, UI) da GitHub.",
};

const GITHUB_URL = "https://github.com/agent-engineering-studio/opendata-ai";

const SECTIONS: Array<{
  href: string;
  external?: boolean;
  title: string;
  blurb: string;
  badge: string;
}> = [
  {
    href: "/docs/a2a",
    title: "A2A — integra OpenData AI nel tuo agente",
    blurb:
      "Il modo per usare la piattaforma in abbonamento: deleghi una domanda (“cerca questi open data”) al nostro orchestratore via JSON-RPC e ricevi sintesi + risorse. Compatibile con qualunque framework che parla Agent-to-Agent.",
    badge: "Abbonamento",
  },
  {
    href: "/docs/api-keys",
    title: "API key — autenticare le chiamate A2A",
    blurb:
      "Genera la tua chiave dal pannello account e usala come Authorization: Bearer od_… sull'endpoint A2A. È la sola credenziale necessaria per integrare la piattaforma hosted da codice.",
    badge: "Autenticazione",
  },
  {
    href: "/docs/mcp",
    title: "Server MCP — per progetti custom (self-host)",
    blurb:
      "I tre server FastMCP (CKAN, ISTAT, OSM) sono pubblicati come immagini su GHCR. Riusali nei tuoi progetti: stdio per i client desktop, streamable-http per gli agenti server-side.",
    badge: "Self-host",
  },
  {
    href: GITHUB_URL,
    external: true,
    title: "Self-host — stack completo su GitHub",
    blurb:
      "Clona la repo ed esegui l'intero stack (backend FastAPI, 3 server MCP, UI Next.js, Postgres, Redis, Ollama o Claude) con make up. Setup, configurazione e API REST completa sono documentati nel README.",
    badge: "GitHub",
  },
];

export default function Page() {
  return (
    <article className="container py-5">
      <h1 className="mb-3">Portale Sviluppatori</h1>
      <p className="lead text-muted">
        <strong>OpenData AI è open source</strong> (licenza MIT). Puoi usarlo in
        due modi: <strong>in abbonamento</strong>, integrando la piattaforma
        hosted nel tuo framework di agenti via protocollo <strong>A2A</strong>;
        oppure in <strong>self-host</strong>, eseguendo l&apos;intero stack — con
        backend REST e server MCP — a partire dalla{" "}
        <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
          repository GitHub
        </a>
        .
      </p>

      <div className="row g-3 mt-1">
        <div className="col-md-6">
          <div className="card h-100 border-primary">
            <div className="card-body">
              <span className="badge bg-primary mb-2">Abbonamento · hosted</span>
              <h2 className="h5">Integra via A2A</h2>
              <p className="text-muted mb-2">
                La piattaforma hosted espone <strong>un&apos;unica superficie
                pubblica</strong>: l&apos;endpoint <strong>A2A</strong>. Generi
                un&apos;API key, la usi per autenticare le chiamate JSON-RPC e
                deleghi all&apos;orchestratore la ricerca multi-fonte sugli open
                data. Nessun backend REST da gestire.
              </p>
              <Link href="/docs/a2a" className="btn btn-sm btn-primary">
                Guida A2A →
              </Link>
            </div>
          </div>
        </div>
        <div className="col-md-6">
          <div className="card h-100">
            <div className="card-body">
              <span className="badge bg-light text-dark mb-2">Self-host · open source</span>
              <h2 className="h5">Esegui il tuo stack</h2>
              <p className="text-muted mb-2">
                Vuoi il controllo completo o i singoli mattoni? Clona la repo ed
                esegui backend, server MCP e UI in locale. I server{" "}
                <strong>MCP</strong> sono anche immagini su GHCR riutilizzabili
                nei tuoi progetti custom.
              </p>
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-sm btn-outline-secondary"
              >
                Repository GitHub →
              </a>
            </div>
          </div>
        </div>
      </div>

      <div className="row g-4 mt-3">
        {SECTIONS.map((s) => (
          <div key={s.href} className="col-md-6">
            {s.external ? (
              <a
                href={s.href}
                target="_blank"
                rel="noopener noreferrer"
                className="card h-100 shadow-sm text-decoration-none text-reset"
              >
                <div className="card-body">
                  <span className="badge bg-light text-dark mb-2">{s.badge}</span>
                  <h3 className="h5">{s.title}</h3>
                  <p className="text-muted mb-0">{s.blurb}</p>
                </div>
              </a>
            ) : (
              <Link
                href={s.href}
                className="card h-100 shadow-sm text-decoration-none text-reset"
              >
                <div className="card-body">
                  <span className="badge bg-light text-dark mb-2">{s.badge}</span>
                  <h3 className="h5">{s.title}</h3>
                  <p className="text-muted mb-0">{s.blurb}</p>
                </div>
              </Link>
            )}
          </div>
        ))}
      </div>

      <section className="mt-5">
        <h2>Convenzioni</h2>
        <ul>
          <li>
            <strong>Hosted = solo A2A.</strong> L&apos;unica superficie pubblica
            in abbonamento è l&apos;endpoint A2A. Le funzionalità REST e i server
            MCP sono disponibili solo in self-host. Vedi{" "}
            <Link href="/docs/a2a">/docs/a2a</Link>.
          </li>
          <li>
            <strong>Autenticazione.</strong> Le chiamate A2A vogliono
            un&apos;API key (<code>Authorization: Bearer od_…</code> o{" "}
            <code>X-API-Key</code>) — vedi{" "}
            <Link href="/docs/api-keys">/docs/api-keys</Link>. La discovery della
            AgentCard (<code>/.well-known/agent-card.json</code>) resta pubblica.
          </li>
          <li>
            <strong>Server MCP per progetti custom.</strong> Le immagini sono su
            GHCR (<code>ghcr.io/agent-engineering-studio/…</code>): le riusi via{" "}
            <code>stdio</code> (client desktop) o <code>streamable-http</code>{" "}
            (agenti server-side). Vedi <Link href="/docs/mcp">/docs/mcp</Link>.
          </li>
          <li>
            <strong>Tutto il resto è su GitHub.</strong> Setup locale,
            configurazione, API REST completa e dettagli architetturali sono
            documentati nella{" "}
            <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
              repository
            </a>
            .
          </li>
        </ul>
      </section>
    </article>
  );
}
