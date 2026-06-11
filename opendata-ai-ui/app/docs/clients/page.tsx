import type { Metadata } from "next";
import Link from "next/link";
import { NextStepsCards } from "@/components/NextStepsCards";

export const metadata: Metadata = {
  title: "Client AI (Claude Desktop, Cursor) — OpenData AI",
  description:
    "Configurazione per usare i server MCP CKAN, ISTAT e OSM da Claude Desktop e Cursor via transport stdio.",
};

export default function Page() {
  return (
    <article className="container py-5">
      <p className="text-muted small mb-2">
        <Link href="/docs">← Documentazione</Link>
      </p>
      <h1>Client AI desktop — Claude Desktop e Cursor</h1>
      <p className="lead">
        I tre server MCP di OpenData AI parlano direttamente con i client
        desktop che supportano il protocollo Model Context Protocol. La via
        più semplice è il transport <code>stdio</code>: il client lancia il
        server come sottoprocesso e i tool diventano disponibili nel prompt.
      </p>

      <section className="mt-4">
        <h2>Prerequisiti</h2>
        <ul>
          <li>Python 3.11+ disponibile sul PATH (i tre server sono Python).</li>
          <li>
            I tre pacchetti installati editabili o da PyPI (quando rilasciati):
            <code>ckan-mcp-server</code>, <code>istat-mcp-server</code>,{" "}
            <code>osm-mcp</code>.
          </li>
          <li>
            Per installare in locale:
            <pre
              className="bg-light border rounded p-3 small font-monospace mt-2"
              style={{ overflowX: "auto", whiteSpace: "pre" }}
            >
{`git clone https://github.com/agent-engineering-studio/opendata-ai.git
cd opendata-ai
pip install -e ./ckan-mcp-server -e ./istat-mcp-server -e ./osm-mcp`}
            </pre>
          </li>
        </ul>
      </section>

      <section className="mt-4">
        <h2>Claude Desktop</h2>
        <p>
          Modifica <code>claude_desktop_config.json</code> (su macOS:{" "}
          <code>~/Library/Application Support/Claude/claude_desktop_config.json</code>).
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`{
  "mcpServers": {
    "opendata-ckan": {
      "command": "ckan-mcp",
      "env": { "TRANSPORT": "stdio" }
    },
    "opendata-istat": {
      "command": "istat-mcp",
      "env": { "TRANSPORT": "stdio" }
    },
    "opendata-osm": {
      "command": "osm-mcp",
      "env": { "TRANSPORT": "stdio" }
    }
  }
}`}
        </pre>
        <p>
          Riavvia Claude Desktop. Nel selettore MCP vedrai i tre server con i
          loro tool (es. <code>opendata-ckan/package_search</code>). Per
          chiamarli basta fare la domanda in chat: Claude sceglie il tool.
        </p>
      </section>

      <section className="mt-4">
        <h2>Cursor</h2>
        <p>
          Cursor legge la stessa convenzione MCP. Modifica{" "}
          <code>~/.cursor/mcp.json</code> (o il file Project settings):
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`{
  "mcpServers": {
    "opendata-ckan": {
      "command": "ckan-mcp",
      "env": { "TRANSPORT": "stdio" }
    },
    "opendata-istat": {
      "command": "istat-mcp",
      "env": { "TRANSPORT": "stdio" }
    },
    "opendata-osm": {
      "command": "osm-mcp",
      "env": { "TRANSPORT": "stdio" }
    }
  }
}`}
        </pre>
        <p>
          Riapri Cursor: i tool MCP appaiono nel pannello laterale come
          chiamate disponibili all&apos;agent.
        </p>
      </section>

      <section className="mt-4">
        <h2>Esempio di sessione (Claude Desktop)</h2>
        <p>
          Una volta caricati i server, queste sono domande tipiche che
          Claude smista da solo ai tool MCP:
        </p>
        <ul>
          <li>
            &ldquo;Cerca su dati.gov.it dataset sulla qualità dell&apos;aria
            negli ultimi 12 mesi&rdquo; → <code>package_search</code>
          </li>
          <li>
            &ldquo;Quali sono i dataflow ISTAT sul lavoro?&rdquo; →{" "}
            <code>search_dataflows</code>
          </li>
          <li>
            &ldquo;Trasforma queste coordinate in un indirizzo&rdquo; →{" "}
            <code>reverse_geocode</code>
          </li>
          <li>
            &ldquo;Disegna su mappa i confini comunali di questo GeoJSON&rdquo;
            → <code>render_map_html</code>
          </li>
        </ul>
      </section>

      <section className="mt-4">
        <h2>Troubleshooting</h2>
        <ul>
          <li>
            <strong>Server non parte</strong> → controlla che{" "}
            <code>which ckan-mcp</code> restituisca il path giusto e che la
            venv contenente il pacchetto sia attiva nello stesso shell che
            avvia il client.
          </li>
          <li>
            <strong>Tool list vuota</strong> → il client deve usare il
            protocollo MCP recente (≥ 2025-03). Aggiorna Claude Desktop /
            Cursor all&apos;ultima versione.
          </li>
          <li>
            <strong>Errori di rete dal tool</strong> → i tool fanno fetch
            verso il portale CKAN o l&apos;endpoint SDMX. Verifica che la
            macchina abbia accesso a Internet senza proxy bloccante.
          </li>
        </ul>
      </section>

      <section className="mt-4">
        <NextStepsCards
          heading="Vai oltre"
          items={[
            {
              href: "/docs/maf",
              title: "Microsoft Agent Framework",
              blurb: "Costruisci un agente server-side che usa gli stessi tre MCP via streamable-http.",
              badge: "Python",
            },
            {
              href: "/docs/langgraph",
              title: "LangGraph",
              blurb: "Grafo ReAct (o custom) che carica i tool MCP via langchain-mcp-adapters.",
              badge: "Python",
            },
            {
              href: "/docs/a2a",
              title: "Agent-to-Agent (A2A)",
              blurb: "Delega l'intera query al backend OpenData AI da un altro agente.",
              badge: "Protocollo",
            },
            {
              href: "/docs/rate-limits",
              title: "Rate limits",
              blurb: "Quota di default, 429 + Retry-After, pattern di retry consigliato.",
              badge: "Operativo",
            },
          ]}
        />
      </section>
    </article>
  );
}
