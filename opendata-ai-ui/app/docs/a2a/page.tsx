import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "A2A — Agent-to-Agent — OpenData AI",
  description:
    "Come parlare con il backend OpenData AI da un altro agente via protocollo A2A: AgentCard, SDK 1.0 (SendMessage), SDK 0.3 (message/send), esempi Python e curl.",
};

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
        delegare task &ldquo;cerca questi dataset&rdquo; o &ldquo;classifica
        questo dataset&rdquo; da un orchestratore esterno.
      </p>

      <div className="alert alert-info">
        <strong>Autenticazione.</strong> La discovery della AgentCard è
        pubblica; le invocazioni JSON-RPC su <code>/a2a/</code> richiedono una
        credenziale, esattamente come la REST API: un JWT Clerk{" "}
        <em>oppure</em> un&apos;API key (<code>Authorization: Bearer od_…</code>{" "}
        o <code>X-API-Key</code>). Per agenti server-to-server usa un&apos;API
        key — vedi <Link href="/docs/api-keys">/docs/api-keys</Link>. Gli esempi
        qui sotto mostrano il JWT, ma la chiave <code>od_…</code> è
        interscambiabile.
      </div>

      <section className="mt-4">
        <h2>Discovery — AgentCard</h2>
        <p>
          La AgentCard è esposta su <code>/.well-known/agent-card.json</code>{" "}
          (SDK 1.0) e su <code>/.well-known/agent.json</code> come alias
          legacy 0.3. Contiene metadata, skill esposte e supported versions.{" "}
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
    { "id": "classify_dataset",   "name": "Classifica un dataset" }
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
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-4">
        <h2>SDK 1.0 — <code>SendMessage</code> (raccomandato)</h2>
        <p className="text-muted small mb-2">
          PascalCase, <code>role</code> come enum protobuf:
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`curl -sX POST https://api.opendata-ai.it/a2a/ \\
  -H 'Content-Type: application/json' \\
  -H 'Authorization: Bearer <clerk_jwt>' \\
  -H 'A2A-Version: 1.0' \\
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
        <h2>SDK 0.3 (compat) — <code>message/send</code></h2>
        <p className="text-muted small mb-2">
          slash-case, <code>role</code> lowercase, <code>kind: text</code>{" "}
          esplicito nei parts:
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`curl -sX POST https://api.opendata-ai.it/a2a/ \\
  -H 'Content-Type: application/json' \\
  -H 'Authorization: Bearer <clerk_jwt>' \\
  -H 'A2A-Version: 0.3' \\
  -d '{
    "jsonrpc":"2.0","id":"1","method":"message/send",
    "params":{"message":{
      "messageId":"m-2",
      "role":"user",
      "parts":[{"kind":"text","text":"qualità aria a Milano"}],
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
    headers={"Authorization": f"Bearer {os.environ['OPENDATA_JWT']}"},
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
            <strong>Header <code>A2A-Version</code></strong> deve coincidere col
            metodo (<code>1.0</code> ↔ <code>SendMessage</code>,{" "}
            <code>0.3</code> ↔ <code>message/send</code>). In alternativa
            puoi omettere l&apos;header: il server lo deduce dal nome del
            metodo.
          </li>
          <li>
            <strong>Skill</strong> si seleziona via{" "}
            <code>message.metadata.skill</code> (default{" "}
            <code>search_open_data</code>).
          </li>
          <li>
            <strong>Auth</strong>: in produzione le chiamate <code>/a2a/</code>{" "}
            vogliono un JWT Clerk o un&apos;API key <code>od_…</code> (header{" "}
            <code>Authorization: Bearer</code> o <code>X-API-Key</code>); la sola
            AgentCard resta pubblica. In dev locale con{" "}
            <code>AUTH_ENABLED=false</code> l&apos;header diventa opzionale.
          </li>
        </ul>
      </section>

      <section className="mt-4">
        <h2>Shape della risposta</h2>
        <p>
          <code>result.task.status.state</code> = <code>completed</code> /{" "}
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
        <h2>Quando usare A2A vs MCP</h2>
        <ul>
          <li>
            <strong>MCP</strong> espone <em>tool</em> a un singolo LLM. Sceglilo
            se vuoi costruire il tuo agente che chiama i nostri server CKAN /
            ISTAT / OSM uno per volta.
          </li>
          <li>
            <strong>A2A</strong> espone <em>l&apos;intero agente</em> OpenData
            AI a un altro agente. Sceglilo se vuoi delegare l&apos;intera
            domanda &ldquo;cerca tra gli open data&rdquo; al nostro
            orchestratore, ricevendo la sintesi pre-fatta.
          </li>
        </ul>
      </section>
    </article>
  );
}
