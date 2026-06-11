import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Documentazione tecnica — OpenData AI",
  description:
    "Guide pratiche per integrare OpenData AI: server MCP (stdio/streamable-http), client AI (Claude Desktop, Cursor), Microsoft Agent Framework, LangGraph, protocollo A2A e rate limits.",
};

const SECTIONS: Array<{
  href: string;
  title: string;
  blurb: string;
  badge: string;
}> = [
  {
    href: "/docs/setup",
    title: "Setup locale — clone ed esecuzione",
    blurb:
      "Istruzioni passo-passo per clonare la repo, configurare .env.local e avviare l'intero stack (backend, 3 MCP, UI, Postgres, Redis, Ollama o Claude) con make up.",
    badge: "Quickstart",
  },
  {
    href: "/docs/mcp",
    title: "MCP — panoramica dei tre server",
    blurb:
      "CKAN, ISTAT e OSM esposti come server FastMCP. Stessa immagine per stdio (Claude Desktop) e streamable-http (Docker/Aruba VPS).",
    badge: "Panoramica",
  },
  {
    href: "/docs/clients",
    title: "Client AI — Claude Desktop, Cursor, host MCP",
    blurb:
      "Config JSON pronti all'uso per claude_desktop_config.json e per Cursor. Tutto via stdio in locale, senza chiavi cloud.",
    badge: "Config",
  },
  {
    href: "/docs/maf",
    title: "Microsoft Agent Framework (MAF)",
    blurb:
      "Stesso SDK usato dal backend. Connessione ai server MCP via streamable-http, ChatAgent + MCPStreamableHTTPTool.",
    badge: "Python",
  },
  {
    href: "/docs/langgraph",
    title: "LangGraph + langchain-mcp-adapters",
    blurb:
      "Graph minimale con StateGraph e ToolNode. I tool MCP vengono caricati a runtime e diventano nodi del grafo.",
    badge: "Python",
  },
  {
    href: "/docs/a2a",
    title: "A2A — Agent-to-Agent",
    blurb:
      "AgentCard pubblica su /.well-known, JSON-RPC su /a2a/. Esempi SDK 1.0 (SendMessage) e SDK 0.3 (message/send).",
    badge: "Protocollo",
  },
  {
    href: "/docs/rate-limits",
    title: "Rate limits e quota",
    blurb:
      "Finestra fissa al minuto, default 60 richieste/utente, header Retry-After in caso di 429. Cache 24h sul classify.",
    badge: "Operativo",
  },
];

export default function Page() {
  return (
    <article className="container py-5">
      <h1 className="mb-3">Documentazione tecnica</h1>
      <p className="lead text-muted">
        Tutto quello che serve per chiamare OpenData AI da un client MCP, da
        un agente MAF/LangGraph o da un altro agente via protocollo A2A. Gli
        esempi presuppongono il backend raggiungibile a{" "}
        <code>https://api.opendata-ai.it</code> e i server MCP esposti
        rispettivamente su <code>/mcp</code> di <code>ckan-mcp:8080</code>,{" "}
        <code>istat-mcp:8081</code> e <code>osm-mcp:8082</code> (in sviluppo
        locale).
      </p>

      <div className="row g-4 mt-2">
        {SECTIONS.map((s) => (
          <div key={s.href} className="col-md-6">
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
          </div>
        ))}
      </div>

      <section className="mt-5">
        <h2>Convenzioni</h2>
        <ul>
          <li>
            <strong>Autenticazione</strong>: ogni endpoint REST/A2A vuole un
            JWT Clerk in <code>Authorization: Bearer …</code>. In sviluppo
            locale puoi disabilitare il controllo con{" "}
            <code>AUTH_ENABLED=false</code> sul backend.
          </li>
          <li>
            <strong>Hostnames MCP</strong>: nei docker-compose i servizi si
            risolvono per nome (es. <code>http://ckan-mcp:8080/mcp</code>); da
            host puoi usare <code>http://localhost:8080/mcp</code> e simili.
          </li>
          <li>
            <strong>Transport MCP</strong>: <code>stdio</code> per i client
            desktop, <code>streamable-http</code> per agenti server-side. La
            stessa immagine supporta entrambi tramite la env{" "}
            <code>TRANSPORT</code>.
          </li>
          <li>
            <strong>Rate limit</strong>: fixed window al minuto, default 60
            richieste per utente. In caso di superamento ricevi{" "}
            <code>HTTP 429</code> con header <code>Retry-After</code>. Vedi{" "}
            <Link href="/docs/rate-limits">/docs/rate-limits</Link>.
          </li>
        </ul>
      </section>
    </article>
  );
}
