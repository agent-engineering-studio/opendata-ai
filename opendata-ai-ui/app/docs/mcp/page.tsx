import type { Metadata } from "next";
import Link from "next/link";
import { NextStepsCards } from "@/components/NextStepsCards";

export const metadata: Metadata = {
  title: "Server MCP — OpenData AI",
  description:
    "Panoramica dei tre server FastMCP esposti da OpenData AI: CKAN (11 tool), ISTAT/SDMX 2.1 e OSM (geocoding+routing+rendering). Supportano stdio e streamable-http dalla stessa immagine.",
};

export default function Page() {
  return (
    <article className="container py-5">
      <p className="text-muted small mb-2">
        <Link href="/docs">← Portale Sviluppatori</Link>
      </p>
      <h1>Server MCP — panoramica</h1>
      <p className="lead">
        OpenData AI distribuisce tre server FastMCP indipendenti. Possono
        essere usati dal backend OpenData AI, da Claude Desktop, da un agente
        MAF/LangGraph o da qualunque altro host MCP. Ogni server supporta sia{" "}
        <code>stdio</code> (per i client locali) sia{" "}
        <code>streamable-http</code> (per il deployment server-side), via la
        variabile d&apos;ambiente <code>TRANSPORT</code>.
      </p>

      <section className="mt-4">
        <h2>I tre server</h2>
        <div className="table-responsive">
          <table className="table table-bordered align-middle">
            <thead className="table-light">
              <tr>
                <th>Server</th>
                <th>Cosa espone</th>
                <th>Tool principali</th>
                <th>Host:porta (compose)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <strong>ckan-mcp</strong>
                </td>
                <td>
                  Qualunque portale CKAN-compatibile (default{" "}
                  <code>dati.gov.it</code>). Il <code>base_url</code> è
                  per-call.
                </td>
                <td>
                  <code>package_search</code>, <code>package_show</code>,{" "}
                  <code>group_list</code>, <code>organization_list</code>,{" "}
                  <code>tag_list</code>, <code>resource_show</code> + altri (11
                  totali)
                </td>
                <td>
                  <code>http://ckan-mcp:8080/mcp</code>
                </td>
              </tr>
              <tr>
                <td>
                  <strong>istat-mcp</strong>
                </td>
                <td>
                  SDMX 2.1 (default ISTAT). Stessi tool per Eurostat e OCSE
                  cambiando <code>agency</code> + <code>base_url</code>.
                </td>
                <td>
                  <code>list_dataflows</code>, <code>get_dataflow</code>,{" "}
                  <code>get_codelist</code>, <code>get_observations</code>,{" "}
                  <code>search_dataflows</code>
                </td>
                <td>
                  <code>http://istat-mcp:8081/mcp</code>
                </td>
              </tr>
              <tr>
                <td>
                  <strong>osm-mcp</strong>
                </td>
                <td>
                  OpenStreetMap: geocoding (Nominatim), POI (Overpass), routing
                  (OSRM), e render Leaflet di GeoJSON.
                </td>
                <td>
                  <code>geocode</code>, <code>reverse_geocode</code>,{" "}
                  <code>find_pois</code>, <code>route</code>,{" "}
                  <code>render_map_html</code>
                </td>
                <td>
                  <code>http://osm-mcp:8082/mcp</code>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-4">
        <h2>Avvio in locale (stdio)</h2>
        <p>
          Modalità tipica per i client desktop (Claude Desktop, Cursor). Il
          server viene avviato come sotto-processo dal client.
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`# CKAN MCP via stdio
pip install -e ./ckan-mcp-server
TRANSPORT=stdio ckan-mcp

# Equivalente per ISTAT
TRANSPORT=stdio istat-mcp

# Equivalente per OSM
TRANSPORT=stdio osm-mcp`}
        </pre>
        <p className="small text-muted">
          Per la configurazione concreta di Claude Desktop o Cursor vedi{" "}
          <Link href="/docs/clients">/docs/clients</Link>.
        </p>
      </section>

      <section className="mt-4">
        <h2>Avvio server-side (streamable-http)</h2>
        <p>
          Modalità tipica per agenti hostati (MAF, LangGraph, A2A). Espone un
          endpoint HTTP/JSON-RPC su un path configurabile (<code>/mcp</code>{" "}
          per default).
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`TRANSPORT=streamable-http \\
PORT=8080 MCP_PATH=/mcp \\
ckan-mcp

# Verifica rapida (tools/list senza session):
curl -sX POST http://localhost:8080/mcp \\
  -H 'Content-Type: application/json' \\
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}'`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Docker e docker-compose</h2>
        <p>
          Le immagini ufficiali sono pubblicate su GHCR (
          <code>ghcr.io/agent-engineering-studio/&lt;server&gt;:&lt;tag&gt;</code>).
          In compose:
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`services:
  ckan-mcp:
    image: ghcr.io/agent-engineering-studio/ckan-mcp-server:main
    environment:
      TRANSPORT: streamable-http
      MCP_PATH: /mcp
      PORT: 8080
    ports: ["8080:8080"]

  istat-mcp:
    image: ghcr.io/agent-engineering-studio/istat-mcp-server:main
    environment:
      TRANSPORT: streamable-http
      PORT: 8081
    ports: ["8081:8081"]

  osm-mcp:
    image: ghcr.io/agent-engineering-studio/osm-mcp:main
    environment:
      TRANSPORT: streamable-http
      PORT: 8082
    ports: ["8082:8082"]`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Esempio di chiamata grezza</h2>
        <p>
          La sessione streamable-http richiede di gestire l&apos;header{" "}
          <code>mcp-session-id</code>. Per un sanity-check serve solo{" "}
          <code>tools/list</code>:
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`# Lista tool disponibili
curl -sX POST http://localhost:8080/mcp \\
  -H 'Content-Type: application/json' \\
  -H 'Accept: application/json, text/event-stream' \\
  -d '{
    "jsonrpc":"2.0","id":"1","method":"tools/list"
  }' | jq

# Invocazione di package_search su dati.gov.it
curl -sX POST http://localhost:8080/mcp \\
  -H 'Content-Type: application/json' \\
  -H 'Accept: application/json, text/event-stream' \\
  -d '{
    "jsonrpc":"2.0","id":"2","method":"tools/call",
    "params":{
      "name":"package_search",
      "arguments":{
        "base_url":"https://www.dati.gov.it/opendata/api/3/action",
        "q":"qualità aria",
        "rows":5
      }
    }
  }' | jq`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Sicurezza</h2>
        <ul>
          <li>
            I server MCP <strong>non</strong> implementano autenticazione
            propria: girano dietro a Traefik / al backend OpenData AI, che
            espone le funzionalità via REST e A2A autenticati.
          </li>
          <li>
            In sviluppo locale, esporli sulla rete è sicuro solo se gli MCP
            target (CKAN, SDMX, OSM) sono già pubblici, perché i tool fanno
            fetch lato server.
          </li>
          <li>
            Per i casi multi-tenant, mettili dietro un reverse proxy con mTLS
            o un token statico nelle env (il client MCP lo riusa come header).
            Se esponi gli endpoint <code>streamable-http</code> sullo stesso
            gateway del backend, usa la tua{" "}
            <Link href="/docs/api-keys">API key</Link> <code>od_…</code> come
            header (<code>Authorization: Bearer</code> o <code>X-API-Key</code>)
            così l&apos;accesso è gestito con la stessa credenziale di REST e
            A2A. In locale via <code>stdio</code> non serve alcuna chiave.
          </li>
        </ul>
      </section>

      <section className="mt-4">
        <NextStepsCards
          heading="Vai oltre"
          items={[
            {
              href: "/docs/clients",
              title: "Client AI desktop",
              blurb: "Config JSON per Claude Desktop e Cursor — connessione stdio in locale.",
              badge: "Config",
            },
            {
              href: "/docs/maf",
              title: "Microsoft Agent Framework",
              blurb: "Agente Python che usa CKAN, ISTAT e OSM via MCPStreamableHTTPTool.",
              badge: "Python",
            },
            {
              href: "/docs/langgraph",
              title: "LangGraph",
              blurb: "Grafo LangGraph con langchain-mcp-adapters: ReAct e custom StateGraph.",
              badge: "Python",
            },
            {
              href: "/docs/a2a",
              title: "Agent-to-Agent",
              blurb: "Chiamare il backend OpenData AI come agente esterno via JSON-RPC.",
              badge: "Protocollo",
            },
          ]}
        />
      </section>
    </article>
  );
}
