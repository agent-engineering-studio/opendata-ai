import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Informazioni — OpenData AI",
  description:
    "Cos'è OpenData AI, come funziona la chat e la mappa, fonti dati interrogate, integrazione via REST e A2A.",
};

export default function Page() {
  return (
    <article className="container py-5">
      <h1>Informazioni</h1>
      <p className="lead">
        OpenData AI è un orchestratore di agenti che interroga in parallelo i
        principali cataloghi italiani ed europei di dati aperti e produce una
        sintesi narrativa con le risorse trovate.
      </p>

      <section>
        <h2>Cosa fa</h2>
        <p>
          Una sola domanda in linguaggio naturale viene smistata in parallelo a
          tre specialisti: un agente CKAN per i portali open data
          (dati.gov.it e i portali municipali / regionali), un agente
          SDMX&nbsp;2.1 per le statistiche ufficiali (ISTAT, e — opzionalmente
          — Eurostat e OCSE), e un agente di sintesi che fonde le risposte in
          una narrativa unica. Le risorse geografiche vengono convertite in
          GeoJSON e disegnate su OpenStreetMap.
        </p>
      </section>

      <section>
        <h2>Come usarlo</h2>
        <ul>
          <li>
            <strong>
              <Link href="/">Chat</Link>
            </strong>{" "}
            — interfaccia conversazionale. Fai una domanda
            (&ldquo;popolazione di Milano per età&rdquo;, &ldquo;qualità
            dell&apos;aria nelle città italiane&rdquo;) e ricevi un testo di
            sintesi più la lista dei dataset coinvolti, con anteprima del
            contenuto quando possibile (CSV, JSON, GeoJSON, KML, PDF).
          </li>
          <li>
            <strong>
              <Link href="/mappa">Mappa</Link>
            </strong>{" "}
            — variante geografica. La query è biasata verso risorse
            cartografiche (Shapefile, GeoJSON, KML, WMS); i layer compatibili
            appaiono come overlay accendibili sulla mappa OSM.
          </li>
        </ul>
        <p>
          Durante l&apos;elaborazione vedi lo stato in tempo reale degli
          specialisti (&ldquo;Interrogo ISTAT…&rdquo;, &ldquo;CKAN ha
          risposto&rdquo;, &ldquo;Sintesi in corso…&rdquo;) e gli heartbeat
          con i secondi trascorsi sulle chiamate lunghe.
        </p>
      </section>

      <section>
        <h2>Fonti dati</h2>
        <ul>
          <li>
            <strong>CKAN</strong> — qualsiasi portale CKAN-compatibile.
            Default: <code>dati.gov.it</code>. Altri portali supportati:
            data.gov.uk, data.gov, open.canada.ca, data.gov.au.
          </li>
          <li>
            <strong>ISTAT</strong> — endpoint SDMX&nbsp;2.1 di esploradati.istat.it.
          </li>
          <li>
            <strong>Eurostat</strong> e <strong>OCSE</strong> — opzionali, da
            abilitare via configurazione lato backend.
          </li>
          <li>
            <strong>OpenStreetMap</strong> — geocoding (Nominatim), routing
            (OSRM) e rendering Leaflet per i layer della pagina mappa.
          </li>
        </ul>
      </section>

      <section>
        <h2>Per sviluppatori e integratori</h2>
        <p>OpenData AI espone due superfici programmabili:</p>

        <h3>REST</h3>
        <p>
          Endpoint autenticati tramite Clerk JWT. I principali:
        </p>
        <ul>
          <li>
            <code>POST /datasets/search</code> — sincrono, ritorna{" "}
            <code>{"{text, resources}"}</code>.
          </li>
          <li>
            <code>POST /datasets/search/stream</code> — NDJSON con eventi di
            stato durante l&apos;elaborazione.
          </li>
          <li>
            <code>POST /datasets/classify</code> — classificazione di un
            dataset rispetto a una tassonomia, con cache 24h.
          </li>
          <li>
            <code>GET /datasets/proxy?url=…</code> — proxy server-side per
            scaricare risorse dai portali senza problemi CORS.
          </li>
        </ul>

        <h3>A2A (Agent-to-Agent)</h3>
        <p>
          Il backend pubblica una AgentCard secondo il{" "}
          <a
            href="https://a2a-protocol.org"
            target="_blank"
            rel="noopener noreferrer"
          >
            protocollo A2A
          </a>
          . Discovery su <code>/.well-known/agent-card.json</code> (SDK&nbsp;1.0,
          oppure <code>/.well-known/agent.json</code> come alias legacy 0.3),
          JSON-RPC su <code>/a2a/</code>. Tre skill esposte:
        </p>
        <ul>
          <li>
            <code>search_open_data</code> — fan-out multi-fonte come in chat.
          </li>
          <li>
            <code>find_geo_resources</code> — variante geografica.
          </li>
          <li>
            <code>classify_dataset</code> — classificatore di tassonomia.
          </li>
        </ul>

        <h4>Vincoli da rispettare</h4>
        <ul>
          <li>
            <code>messageId</code> è <strong>obbligatorio</strong>: il SDK
            valida il payload come pydantic strict.
          </li>
          <li>
            L&apos;header <code>A2A-Version</code> deve coincidere col metodo:{" "}
            <code>1.0</code> ↔ <code>SendMessage</code>, <code>0.3</code> ↔{" "}
            <code>message/send</code>. In alternativa puoi omettere
            l&apos;header: il server lo deduce dal nome del metodo.
          </li>
          <li>
            La skill si seleziona via <code>message.metadata.skill</code>{" "}
            (default <code>search_open_data</code>).
          </li>
        </ul>

        <h4>
          SDK 1.0 — <code>SendMessage</code>
        </h4>
        <p className="text-muted small mb-2">
          PascalCase, <code>role</code> come enum protobuf:
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
          <code>{`curl -sX POST http://localhost:18000/a2a/ \\
  -H 'Content-Type: application/json' \\
  -H 'A2A-Version: 1.0' \\
  -d '{
    "jsonrpc":"2.0","id":"1","method":"SendMessage",
    "params":{"message":{
      "messageId":"m-1",
      "role":"ROLE_USER",
      "parts":[{"text":"qualità aria a Milano"}],
      "metadata":{"skill":"search_open_data"}
    }}
  }'`}</code>
        </pre>

        <h4>
          SDK 0.3 (compat) — <code>message/send</code>
        </h4>
        <p className="text-muted small mb-2">
          slash-case, <code>role</code> lowercase, <code>kind: text</code>{" "}
          esplicito nei parts:
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
          <code>{`curl -sX POST http://localhost:18000/a2a/ \\
  -H 'Content-Type: application/json' \\
  -H 'A2A-Version: 0.3' \\
  -d '{
    "jsonrpc":"2.0","id":"1","method":"message/send",
    "params":{"message":{
      "messageId":"m-2",
      "role":"user",
      "parts":[{"kind":"text","text":"qualità aria a Milano"}],
      "metadata":{"skill":"search_open_data"}
    }}
  }'`}</code>
        </pre>

        <h4>Shape della risposta</h4>
        <p>
          <code>result.task.status.state</code> = <code>completed</code> /{" "}
          <code>TASK_STATE_COMPLETED</code> e una lista di{" "}
          <code>artifacts</code>: il primo <code>part</code> è la sintesi
          narrativa testuale, il secondo è un JSON strutturato{" "}
          <code>{"{text, resources}"}</code> con la stessa shape di{" "}
          <code>POST /datasets/search</code>.
        </p>

        <p className="small text-muted">
          In produzione gli endpoint A2A sono autenticati come il resto
          dell&apos;API: aggiungi{" "}
          <code>Authorization: Bearer &lt;clerk_jwt&gt;</code>{" "}
          all&apos;header.
        </p>
      </section>

      <section>
        <h2>Stato del progetto</h2>
        <p>
          Sperimentale. Il backend, i server MCP e l&apos;interfaccia web sono
          pubblicati con licenza open su GitHub:{" "}
          <a
            href="https://github.com/agent-engineering-studio/opendata-ai"
            target="_blank"
            rel="noopener noreferrer"
          >
            agent-engineering-studio/opendata-ai
          </a>
          . Le risposte dell&apos;agente dipendono da modelli LLM esterni
          (Claude o un modello locale via Ollama) e possono contenere errori —
          verifica sempre i dati consultando la fonte indicata nelle risorse.
        </p>
      </section>
    </article>
  );
}
