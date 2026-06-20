import type { Metadata } from "next";
import Link from "next/link";
import { NextStepsCards } from "@/components/NextStepsCards";

export const metadata: Metadata = {
  title: "Client AI (Claude, Cursor, VS Code) — OpenData AI",
  description:
    "Come usare i server MCP CKAN, ISTAT e OSM da Claude Desktop, Claude Code, Cursor e VS Code: transport stdio (install da GitHub) o connessione a un server HTTP (immagini GHCR) via mcp-remote, con API key.",
};

const REPO = "https://github.com/agent-engineering-studio/opendata-ai";

export default function Page() {
  return (
    <article className="container py-5">
      <p className="text-muted small mb-2">
        <Link href="/docs">← Portale Sviluppatori</Link>
      </p>
      <h1>Usare i server MCP dai client AI</h1>
      <p className="lead">
        I tre server MCP di OpenData AI — <code>ckan-mcp</code>,{" "}
        <code>istat-mcp</code>, <code>osm-mcp</code> — funzionano con qualunque
        client che parla Model Context Protocol (Claude Desktop, Claude Code,
        Cursor, VS Code, e altri). Ci sono due modi per collegarli:
      </p>
      <ul>
        <li>
          <strong>A · stdio locale</strong> — il client lancia il server come
          sottoprocesso. Zero rete, ideale sul tuo computer.
        </li>
        <li>
          <strong>B · server HTTP</strong> — i server girano come servizio
          (Docker/compose) e i client si connettono via{" "}
          <code>streamable-http</code>. Adatto a setup condivisi o remoti.
        </li>
      </ul>
      <p className="text-muted small">
        Sorgenti e Dockerfile dei tre server:{" "}
        <a href={`${REPO}/tree/main/ckan-mcp-server`}>ckan-mcp-server</a>,{" "}
        <a href={`${REPO}/tree/main/istat-mcp-server`}>istat-mcp-server</a>,{" "}
        <a href={`${REPO}/tree/main/osm-mcp`}>osm-mcp</a> su GitHub.
      </p>

      {/* ───────────────────────── Install ───────────────────────── */}
      <section className="mt-5">
        <h2>Installazione da GitHub (per il transport stdio)</h2>
        <p>
          Per l&apos;opzione A serve avere i comandi sul <code>PATH</code>.
          Clona il repo e installa i tre pacchetti in una virtualenv:
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`git clone ${REPO}.git
cd opendata-ai
python -m venv .venv && source .venv/bin/activate
pip install -e ./ckan-mcp-server -e ./istat-mcp-server -e ./osm-mcp

# Verifica che i comandi rispondano (Ctrl-C per uscire):
which ckan-mcp istat-mcp osm-mcp`}
        </pre>
        <p className="small text-muted">
          Importante: i client desktop non ereditano la tua shell. Usa il{" "}
          <strong>path assoluto</strong> del comando nella venv (es.{" "}
          <code>/Users/tu/opendata-ai/.venv/bin/ckan-mcp</code>) nei file di
          config qui sotto, oppure installa i pacchetti con{" "}
          <code>pipx</code> per averli su un PATH stabile.
        </p>
      </section>

      {/* ───────────────────────── A · stdio ───────────────────────── */}
      <section className="mt-5">
        <h2>A · stdio locale</h2>

        <h3 className="h5 mt-4">Claude Desktop</h3>
        <p>
          Modifica <code>claude_desktop_config.json</code> (macOS:{" "}
          <code>~/Library/Application Support/Claude/</code>, Windows:{" "}
          <code>%APPDATA%\Claude\</code>) e riavvia l&apos;app.
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`{
  "mcpServers": {
    "opendata-ckan": {
      "command": "/ASSOLUTO/.venv/bin/ckan-mcp",
      "env": { "TRANSPORT": "stdio" }
    },
    "opendata-istat": {
      "command": "/ASSOLUTO/.venv/bin/istat-mcp",
      "env": { "TRANSPORT": "stdio" }
    },
    "opendata-osm": {
      "command": "/ASSOLUTO/.venv/bin/osm-mcp",
      "env": { "TRANSPORT": "stdio" }
    }
  }
}`}
        </pre>
        <p className="small text-muted">
          Nel menù MCP di Claude vedrai i tre server con i loro tool (es.{" "}
          <code>opendata-ckan / package_search</code>). Basta fare la domanda
          in chat: Claude sceglie il tool.
        </p>

        <h3 className="h5 mt-4">Claude Code (CLI)</h3>
        <p>Aggiungi i server con un comando per ciascuno:</p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`claude mcp add opendata-ckan  --env TRANSPORT=stdio -- ckan-mcp
claude mcp add opendata-istat --env TRANSPORT=stdio -- istat-mcp
claude mcp add opendata-osm   --env TRANSPORT=stdio -- osm-mcp

# Elenca / rimuovi
claude mcp list
claude mcp remove opendata-ckan`}
        </pre>

        <h3 className="h5 mt-4">Cursor</h3>
        <p>
          Cursor usa la stessa convenzione. Modifica{" "}
          <code>~/.cursor/mcp.json</code> (globale) o{" "}
          <code>.cursor/mcp.json</code> nel progetto, con lo stesso blocco{" "}
          <code>mcpServers</code> di Claude Desktop.
        </p>

        <h3 className="h5 mt-4">VS Code (GitHub Copilot / agent MCP)</h3>
        <p>
          In <code>.vscode/mcp.json</code> (o le User Settings) — nota la chiave{" "}
          <code>servers</code> e il campo <code>type</code>:
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`{
  "servers": {
    "opendata-ckan": {
      "type": "stdio",
      "command": "/ASSOLUTO/.venv/bin/ckan-mcp",
      "env": { "TRANSPORT": "stdio" }
    }
  }
}`}
        </pre>
      </section>

      {/* ───────────────────────── B · HTTP ───────────────────────── */}
      <section className="mt-5">
        <h2>B · server HTTP (Docker / GHCR)</h2>
        <p>
          Le immagini ufficiali su GHCR girano in <code>streamable-http</code>.
          Avviale (singola o via <code>docker compose</code>) e avrai gli
          endpoint <code>/mcp</code> su tre porte:
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`# Un server alla volta
docker run --rm -p 18080:8080 \\
  -e TRANSPORT=streamable-http -e PORT=8080 -e MCP_PATH=/mcp \\
  ghcr.io/agent-engineering-studio/ckan-mcp-server:main

# Oppure tutto lo stack dal repo
git clone ${REPO}.git && cd opendata-ai
make up        # ckan→:18080  istat→:18081  osm→:18085  (vedi Makefile/.env)`}
        </pre>

        <h3 className="h5 mt-4">Client che parlano HTTP nativamente</h3>
        <p>
          Cursor, VS Code e Claude Code supportano direttamente un server HTTP.
          Esempio per Claude Code:
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`claude mcp add --transport http opendata-ckan http://localhost:18080/mcp`}
        </pre>

        <h3 className="h5 mt-4">
          Client solo-stdio (es. Claude Desktop) → bridge{" "}
          <code>mcp-remote</code>
        </h3>
        <p>
          Claude Desktop oggi avvia solo processi locali: usa il bridge{" "}
          <code>mcp-remote</code> (via <code>npx</code>, serve Node 18+) per
          collegarti a un endpoint HTTP.
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`{
  "mcpServers": {
    "opendata-ckan": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:18080/mcp"]
    }
  }
}`}
        </pre>

        <div className="alert alert-info mt-3">
          <strong>Endpoint MCP ospitati e API key.</strong> I tre server non
          hanno autenticazione propria: in locale e in rete privata vanno usati
          così. Se invece esponi l&apos;endpoint HTTP pubblicamente dietro lo
          stesso gateway del backend, passa la tua{" "}
          <Link href="/docs/api-keys">API key</Link> come header — con{" "}
          <code>mcp-remote</code> si fa con <code>--header</code>:
          <pre
            className="bg-white border rounded p-3 small font-monospace mt-2 mb-0"
            style={{ overflowX: "auto", whiteSpace: "pre" }}
          >
{`"args": ["-y", "mcp-remote", "https://mcp.opendata-ai.it/ckan/mcp",
         "--header", "Authorization: Bearer od_…"]`}
          </pre>
        </div>
      </section>

      {/* ───────────────────────── Sanity check ───────────────────────── */}
      <section className="mt-5">
        <h2>Sanity check senza client (curl)</h2>
        <p>
          Per verificare che un server HTTP risponda, basta{" "}
          <code>tools/list</code> (non serve una sessione):
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`curl -sX POST http://localhost:18080/mcp \\
  -H 'Content-Type: application/json' \\
  -H 'Accept: application/json, text/event-stream' \\
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}' | jq '.result.tools[].name'`}
        </pre>
      </section>

      {/* ───────────────────────── Esempio sessione ───────────────────────── */}
      <section className="mt-5">
        <h2>Esempio di sessione</h2>
        <p>Domande tipiche che il client smista da solo ai tool MCP:</p>
        <ul>
          <li>
            &ldquo;Cerca su dati.gov.it dataset sulla qualità dell&apos;aria
            negli ultimi 12 mesi&rdquo; → <code>package_search</code>{" "}
            (ckan-mcp)
          </li>
          <li>
            &ldquo;Quali dataflow ISTAT riguardano il lavoro?&rdquo; →{" "}
            <code>search_dataflows</code> (istat-mcp)
          </li>
          <li>
            &ldquo;Trasforma queste coordinate in un indirizzo&rdquo; →{" "}
            <code>reverse_geocode</code> (osm-mcp)
          </li>
          <li>
            &ldquo;Disegna su mappa i confini comunali di questo GeoJSON&rdquo;
            → <code>render_map_html</code> (osm-mcp)
          </li>
        </ul>
      </section>

      {/* ───────────────────────── Troubleshooting ───────────────────────── */}
      <section className="mt-5">
        <h2>Troubleshooting</h2>
        <ul>
          <li>
            <strong>Il server non parte (stdio)</strong> → il client non vede il
            tuo PATH: usa il <em>path assoluto</em> del comando nella venv, o{" "}
            <code>pipx install</code>.
          </li>
          <li>
            <strong>Tool list vuota</strong> → aggiorna il client: serve un MCP
            recente (≥ 2025-03). Verifica con il curl <code>tools/list</code>{" "}
            qui sopra che il server di per sé risponda.
          </li>
          <li>
            <strong><code>mcp-remote</code> non si collega</strong> → controlla
            che l&apos;endpoint sia <code>…/mcp</code> (non la root) e che Node
            sia ≥ 18. In caso di 401, manca o è errata l&apos;API key
            nell&apos;header.
          </li>
          <li>
            <strong>Errori di rete dai tool</strong> → i tool fanno fetch verso
            i portali CKAN / SDMX / OSM: serve accesso a Internet senza proxy
            bloccante.
          </li>
        </ul>
      </section>

      <section className="mt-5">
        <NextStepsCards
          heading="Vai oltre"
          items={[
            {
              href: "/docs/mcp",
              title: "Panoramica dei server MCP",
              blurb: "I tre server, i tool esposti e le porte in compose.",
              badge: "Panoramica",
            },
            {
              href: "/docs/maf",
              title: "Microsoft Agent Framework",
              blurb: "Agente server-side che usa i tre MCP via streamable-http.",
              badge: "Python",
            },
            {
              href: "/docs/api-keys",
              title: "API key",
              blurb: "Credenziale per gli endpoint ospitati, REST e A2A.",
              badge: "Autenticazione",
            },
            {
              href: "/docs/a2a",
              title: "Agent-to-Agent (A2A)",
              blurb: "Delega l'intera query al backend OpenData AI.",
              badge: "Protocollo",
            },
          ]}
        />
      </section>
    </article>
  );
}
