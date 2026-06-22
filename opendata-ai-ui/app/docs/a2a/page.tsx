import type { Metadata } from "next";
import Link from "next/link";
import { NextStepsCards } from "@/components/NextStepsCards";

export const metadata: Metadata = {
  title: "A2A — Agent-to-Agent — OpenData AI",
  description:
    "Come parlare con il backend OpenData AI da un altro agente via protocollo A2A: AgentCard, SDK 1.0 (SendMessage), esempi Python e curl. L'API key è la credenziale per le chiamate headless.",
};

const GITHUB_URL = "https://github.com/agent-engineering-studio/opendata-ai";

export default function Page() {
  return (
    <article className="container py-5">
      <p className="text-muted small mb-2">
        <Link href="/docs">← Portale Sviluppatori</Link>
      </p>
      <h1>A2A — Agent-to-Agent</h1>
      <p className="lead">
        Il backend OpenData AI è un <strong>server A2A</strong>: pubblica una{" "}
        <em>AgentCard</em> e accetta chiamate JSON-RPC da qualunque agente
        che parla il protocollo Agent-to-Agent. È il modo giusto per
        delegare a un orchestratore esterno task come &ldquo;cerca questi
        dataset&rdquo; o &ldquo;classifica questo dataset&rdquo;.
      </p>

      <div className="alert alert-info">
        <strong>A2A è la superficie pubblica dell&apos;abbonamento.</strong> La
        discovery della AgentCard è pubblica; le invocazioni JSON-RPC su{" "}
        <code>/a2a/</code> richiedono la tua <strong>API key</strong> (
        <code>Authorization: Bearer od_…</code> oppure <code>X-API-Key</code>).
        Come generarla, ruotarla e revocarla è spiegato in{" "}
        <Link href="/docs/api-keys">/docs/api-keys</Link>.
      </div>

      <section className="mt-4">
        <h2>Cosa puoi fare con l&apos;API key</h2>
        <p>
          La stessa chiave <code>od_…</code> autentica due superfici diverse, a
          seconda di come usi la piattaforma:
        </p>
        <div className="table-responsive">
          <table className="table table-bordered align-middle">
            <thead className="table-light">
              <tr>
                <th>Superficie</th>
                <th>Cosa ti dà</th>
                <th>Dove</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <strong>A2A</strong> (abbonamento)
                </td>
                <td>
                  Deleghi l&apos;intera domanda all&apos;orchestratore hosted e
                  ricevi la sintesi pre-fatta. È l&apos;unica superficie
                  pubblica dell&apos;offerta in abbonamento.
                </td>
                <td>Questa pagina.</td>
              </tr>
              <tr>
                <td>
                  <strong>MCP</strong> (self-host)
                </td>
                <td>
                  In self-host la stessa chiave, messa dietro il gateway del
                  backend, autentica i tre server MCP (CKAN / ISTAT / OSM): chiami
                  i singoli <em>tool</em> dal tuo agente. In abbonamento gli MCP{" "}
                  <strong>non</strong> sono esposti.
                </td>
                <td>
                  <Link href="/docs/mcp">/docs/mcp</Link>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="small text-muted mb-0">
          In breve: <strong>A2A</strong> espone <em>l&apos;intero agente</em>{" "}
          OpenData AI (deleghi la domanda, ricevi la risposta); <strong>MCP</strong>{" "}
          espone <em>tool</em> a un LLM che orchestri tu (utile solo in
          self-host). Non sono alternative concorrenti: scegli A2A per l&apos;uso
          hosted, gli MCP se ti monti lo stack in casa.
        </p>
      </section>

      <section className="mt-4">
        <h2>Discovery — AgentCard</h2>
        <p>
          La AgentCard è esposta su <code>/.well-known/agent-card.json</code>{" "}
          (path standard SDK 1.0). Contiene metadata, skill esposte e versione.{" "}
          Questo endpoint <strong>non</strong> richiede autenticazione.
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`curl -s https://api.opendata-ai.it/.well-known/agent-card.json | jq

{
  "name": "opendata-ai",
  "version": "1.0.0",
  "skills": [
    { "id": "search_open_data",   "name": "Cerca open data multi-fonte" },
    { "id": "find_geo_resources", "name": "Cerca risorse geografiche" },
    { "id": "classify_dataset",   "name": "Classifica un dataset" },
    { "id": "assess_maturity",    "name": "Valuta la maturità di un ente" },
    { "id": "analyze_territory",  "name": "Analizza un territorio (SWOT + proposte)" },
    { "id": "data_quality",       "name": "Diagnosi e preparazione di un dato" }
  ],
  "endpoints": { "jsonrpc": "https://api.opendata-ai.it/a2a/" }
}`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Skill esposte</h2>
        <div className="table-responsive">
          <table className="table table-bordered align-middle">
            <thead className="table-light">
              <tr>
                <th>Skill</th>
                <th>Cosa fa</th>
                <th>Input principale</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <code>search_open_data</code>
                </td>
                <td>
                  Fan-out su CKAN + SDMX, sintesi narrativa + lista risorse.
                </td>
                <td>Una query in linguaggio naturale.</td>
              </tr>
              <tr>
                <td>
                  <code>find_geo_resources</code>
                </td>
                <td>
                  Stessa cosa ma bias geografico (Shapefile, GeoJSON, KML, WMS).
                </td>
                <td>Una query in linguaggio naturale.</td>
              </tr>
              <tr>
                <td>
                  <code>classify_dataset</code>
                </td>
                <td>
                  Classifica un dataset rispetto a una tassonomia data. Cache
                  Redis 24h + Postgres durable.
                </td>
                <td>
                  <code>source</code>, <code>dataset_id</code>,{" "}
                  <code>taxonomy[]</code>.
                </td>
              </tr>
              <tr>
                <td>
                  <code>assess_maturity</code>
                </td>
                <td>
                  Scorecard di maturità ODM 2025 di un ente: 4 dimensioni,
                  livello, raccomandazioni e leve di miglioramento.
                </td>
                <td>
                  Nome ente (testo) o{" "}
                  <code>{`{"entity":…,"istat_code"?}`}</code>.
                </td>
              </tr>
              <tr>
                <td>
                  <code>analyze_territory</code>
                </td>
                <td>
                  Scheda programmatica di un comune: sintesi, SWOT e
                  proposte/idee con citazioni risolvibili (fan-out multi-fonte).
                </td>
                <td>
                  <code>{`{"cod_comune":…,"modalita"?}`}</code> (scheda · idee
                  · completa · marketing).
                </td>
              </tr>
              <tr>
                <td>
                  <code>data_quality</code>
                </td>
                <td>
                  Data Quality Lab su un file inline (CSV/GeoJSON): diagnosi,
                  auto-fix, schema SQL, riepiloghi, consigli di scala, conversione
                  in GeoJSON, validazione DCAT-AP_IT + FAIR e pacchetto pronto da
                  pubblicare. Deterministico, nessun LLM.
                </td>
                <td>
                  <code>{`{"azione":…,"content":…}`}</code> (profile · fix ·
                  schema · summary · scale · to-geojson · validate · package).
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-4">
        <h2>Invocazione — <code>SendMessage</code></h2>
        <p className="text-muted small mb-2">
          JSON-RPC su <code>/a2a/</code>, metodo PascalCase{" "}
          <code>SendMessage</code> (SDK 1.0), autenticato con la tua API key:
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`curl -sX POST https://api.opendata-ai.it/a2a/ \\
  -H 'Content-Type: application/json' \\
  -H 'Authorization: Bearer od_…' \\
  -d '{
    "jsonrpc":"2.0","id":"1","method":"SendMessage",
    "params":{"message":{
      "messageId":"m-1",
      "role":"ROLE_USER",
      "parts":[{"text":"qualità aria a Milano"}],
      "metadata":{"skill":"search_open_data"}
    }}
  }'`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Python — A2A SDK ufficiale</h2>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`pip install a2a-sdk

# client.py
import os
from a2a.client import A2AClient

client = A2AClient(
    "https://api.opendata-ai.it/a2a/",
    headers={"Authorization": f"Bearer {os.environ['OPENDATA_API_KEY']}"},
)

reply = client.send_message(
    text="popolazione di Milano per età, ultimi 5 anni",
    metadata={"skill": "search_open_data"},
)

# Il primo artifact è la sintesi narrativa
print(reply.artifacts[0].parts[0].text)

# Il secondo è il payload strutturato {text, resources}
import json
data = json.loads(reply.artifacts[1].parts[0].data)
for r in data["resources"]:
    print("-", r["title"], "→", r["url"])`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Vincoli da rispettare</h2>
        <ul>
          <li>
            <strong>
              <code>messageId</code> obbligatorio
            </strong>{" "}
            — il SDK valida con pydantic strict.
          </li>
          <li>
            <strong>Solo SDK 1.0</strong> — i metodi sono PascalCase
            (<code>SendMessage</code>, <code>GetTask</code>,{" "}
            <code>CancelTask</code>). La vecchia compat v0.3 (slash-case{" "}
            <code>message/send</code>) non è più esposta.
          </li>
          <li>
            <strong>Skill</strong> si seleziona via{" "}
            <code>message.metadata.skill</code> (default{" "}
            <code>search_open_data</code>).
          </li>
          <li>
            <strong>Auth</strong>: le invocazioni <code>/a2a/</code> richiedono
            la tua API key <code>od_…</code> — dettagli su credenziali, quota e
            revoca in <Link href="/docs/api-keys">/docs/api-keys</Link>.
          </li>
        </ul>
      </section>

      <section className="mt-4">
        <h2>Shape della risposta</h2>
        <p>
          <code>result.task.status.state</code> ={" "}
          <code>TASK_STATE_COMPLETED</code>, più una lista di{" "}
          <code>artifacts</code>:
        </p>
        <ul>
          <li>
            <strong>artifact[0]</strong> — la sintesi narrativa testuale.
          </li>
          <li>
            <strong>artifact[1]</strong> — un JSON strutturato{" "}
            <code>{"{text, resources}"}</code> con la stessa shape di{" "}
            <code>POST /datasets/search</code>.
          </li>
        </ul>
      </section>

      <section className="mt-4">
        <NextStepsCards
          heading="Vai oltre"
          items={[
            {
              href: "/docs/api-keys",
              title: "API key",
              blurb: "Genera, usa e revoca la credenziale per le chiamate A2A.",
              badge: "Autenticazione",
            },
            {
              href: "/docs/mcp",
              title: "Server MCP",
              blurb: "I tre server FastMCP CKAN / ISTAT / OSM per progetti self-host.",
              badge: "Self-host",
            },
            {
              href: GITHUB_URL,
              title: "Repository GitHub",
              blurb: "Setup, API REST completa e codice sorgente (licenza MIT).",
              badge: "Open source",
            },
          ]}
        />
      </section>
    </article>
  );
}
