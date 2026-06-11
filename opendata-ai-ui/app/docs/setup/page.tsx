import type { Metadata } from "next";
import Link from "next/link";
import { NextStepsCards } from "@/components/NextStepsCards";

export const metadata: Metadata = {
  title: "Setup locale — clonare ed eseguire il progetto — OpenData AI",
  description:
    "Istruzioni dettagliate per clonare opendata-ai da GitHub, configurare le variabili d'ambiente e avviare l'intero stack (backend FastAPI, 3 server MCP, UI Next.js, Postgres, Redis, opzionale Ollama o Claude) in locale.",
};

const REPO = "https://github.com/agent-engineering-studio/opendata-ai";

export default function Page() {
  return (
    <article className="container py-5">
      <p className="text-muted small mb-2">
        <Link href="/docs">← Documentazione</Link>
      </p>
      <h1>Setup locale — clone ed esecuzione</h1>
      <p className="lead">
        Questa pagina spiega passo per passo come avere l&apos;intero stack
        OpenData AI in esecuzione sulla tua macchina: backend FastAPI, tre
        server MCP (CKAN, ISTAT, OSM), UI Next.js statica, Postgres + Redis,
        più un provider LLM a scelta (Ollama in locale oppure Claude via
        Anthropic API). Per i dettagli completi del codice, dei test e
        dell&apos;infrastruttura di produzione consulta sempre la repo
        ufficiale su GitHub:{" "}
        <a href={REPO} target="_blank" rel="noopener noreferrer">
          {REPO.replace("https://", "")}
        </a>
        .
      </p>

      <section className="mt-4">
        <h2>Architettura in locale</h2>
        <p>
          Lo stack è orchestrato da <code>docker-compose.yml</code> nella
          root del repo. Quando dai <code>make up</code> vengono avviati 7
          container (8 col profilo Ollama):
        </p>
        <ul>
          <li>
            <code>ckan-mcp</code>, <code>istat-mcp</code>,{" "}
            <code>osm-mcp</code> — i tre server MCP in modalità{" "}
            <code>streamable-http</code>.
          </li>
          <li>
            <code>opendata-backend</code> — FastAPI sulla porta{" "}
            <code>18000</code> (host) → <code>8000</code> (container).
          </li>
          <li>
            <code>opendata-ai-ui</code> — nginx che serve l&apos;export
            statico di Next.js sulla porta <code>13000</code>.
          </li>
          <li>
            <code>postgres</code> (schema <code>opendata</code>) e{" "}
            <code>redis</code> — cache + rate limit.
          </li>
          <li>
            <code>opendata-ai-ollama</code> — opzionale; presente solo nel
            profilo <code>cpu</code>/<code>gpu</code>. Con{" "}
            <code>up-claude</code> non viene avviato.
          </li>
        </ul>
      </section>

      <section className="mt-4">
        <h2>Prerequisiti</h2>
        <div className="table-responsive">
          <table className="table table-bordered align-middle">
            <thead className="table-light">
              <tr>
                <th>Strumento</th>
                <th>Versione minima</th>
                <th>Quando serve</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <strong>git</strong>
                </td>
                <td>≥ 2.30</td>
                <td>clone + sottomoduli</td>
              </tr>
              <tr>
                <td>
                  <strong>Docker</strong> + Docker Compose v2
                </td>
                <td>Docker Desktop ≥ 4.30 / Engine ≥ 24</td>
                <td>
                  Sempre. Lo stack di default gira tutto in container.
                </td>
              </tr>
              <tr>
                <td>
                  <strong>make</strong>
                </td>
                <td>GNU Make ≥ 3.81</td>
                <td>Per i target del <code>Makefile</code> (opzionale).</td>
              </tr>
              <tr>
                <td>
                  <strong>Python</strong>
                </td>
                <td>≥ 3.11</td>
                <td>
                  Solo se vuoi sviluppare i pacchetti backend in editable
                  install (non strettamente necessario per <code>make up</code>).
                </td>
              </tr>
              <tr>
                <td>
                  <strong>Node.js</strong>
                </td>
                <td>≥ 20</td>
                <td>
                  Solo se vuoi sviluppare la UI con <code>npm run dev</code>{" "}
                  fuori da Docker.
                </td>
              </tr>
              <tr>
                <td>
                  <strong>ANTHROPIC_API_KEY</strong>
                </td>
                <td>—</td>
                <td>
                  Solo se scegli il provider <code>claude</code>. Generabile su{" "}
                  <a
                    href="https://console.anthropic.com/settings/keys"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    console.anthropic.com
                  </a>
                  .
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="alert alert-info" role="status">
          <strong>RAM e disco</strong>: con Ollama (modello{" "}
          <code>qwen2.5:32k</code>) servono ~24 GB di RAM e ~30 GB di disco.
          Su macchine modeste preferisci <code>make up-claude</code> con una
          API key Anthropic (il modello gira nel cloud).
        </div>
      </section>

      <section className="mt-4">
        <h2>1. Clone della repo</h2>
        <p>
          La repo include un sottomodulo (<code>vendor/agent-stack</code>) che
          contiene lo schema Postgres come fonte di verità. Non è
          obbligatorio per girare in locale (il backend ha uno stub di
          migration), ma è consigliato:
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`# Clone con sottomoduli in un colpo solo
git clone --recurse-submodules ${REPO}.git
cd opendata-ai

# Oppure, se hai già clonato senza sottomoduli:
git submodule update --init --depth=1`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>2. File di configurazione</h2>
        <p>
          Copia il template <code>.env.local.example</code> in{" "}
          <code>.env.local</code> e personalizzalo. I valori di default sono
          già funzionanti per uno sviluppo da zero — bastano un paio di
          override.
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`cp .env.local.example .env.local
$EDITOR .env.local`}
        </pre>

        <h3 className="h5 mt-4">Variabili più importanti</h3>
        <div className="table-responsive">
          <table className="table table-sm table-bordered">
            <thead className="table-light">
              <tr>
                <th>Variabile</th>
                <th>Default</th>
                <th>Cosa fa</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <code>LLM_PROVIDER</code>
                </td>
                <td>
                  <code>auto</code>
                </td>
                <td>
                  Risolve a <code>claude</code> se{" "}
                  <code>ANTHROPIC_API_KEY</code> è presente, altrimenti{" "}
                  <code>ollama</code>.
                </td>
              </tr>
              <tr>
                <td>
                  <code>ANTHROPIC_API_KEY</code>
                </td>
                <td>vuoto</td>
                <td>
                  Set per usare Claude. Necessaria anche se vuoi solo
                  l&apos;endpoint <code>/datasets/classify</code> (Haiku 4.5).
                </td>
              </tr>
              <tr>
                <td>
                  <code>AUTH_ENABLED</code>
                </td>
                <td>
                  <code>false</code>
                </td>
                <td>
                  Bypassa la verifica JWT Clerk in dev. La UI funziona senza
                  login.
                </td>
              </tr>
              <tr>
                <td>
                  <code>NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY</code>
                </td>
                <td>vuoto</td>
                <td>
                  Se vuoi testare il flusso login completo, mettici la chiave
                  pubblica dell&apos;app{" "}
                  <code>app_3EMALiLi0UTULl89JPMKtaLENoy</code>.
                </td>
              </tr>
              <tr>
                <td>
                  <code>RATE_LIMIT_PER_MINUTE</code>
                </td>
                <td>
                  <code>60</code>
                </td>
                <td>
                  Set a <code>0</code> per disabilitarlo in dev. Vedi{" "}
                  <Link href="/docs/rate-limits">/docs/rate-limits</Link>.
                </td>
              </tr>
              <tr>
                <td>
                  <code>ENABLE_EUROSTAT</code> / <code>ENABLE_OECD</code>
                </td>
                <td>
                  <code>false</code>
                </td>
                <td>
                  Aggiungi 1 specialist LLM call per query. Lascia off per
                  iterare veloce.
                </td>
              </tr>
              <tr>
                <td>
                  <code>BACKEND_PORT</code> / <code>UI_PORT</code>
                </td>
                <td>
                  <code>18000</code> / <code>13000</code>
                </td>
                <td>
                  Porte host. La UI parla a <code>http://localhost:18000</code>{" "}
                  via <code>NEXT_PUBLIC_API_URL</code>.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-4">
        <h2>3. Avvio dello stack</h2>

        <h3 className="h5">Opzione A — Claude (consigliata per iniziare)</h3>
        <p>
          Non avvia il container Ollama. Più veloce, meno risorse, e gli
          esempi della landing rispondono subito.
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`# in .env.local
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...

make up-claude
make logs   # tail dei log di tutti i servizi`}
        </pre>

        <h3 className="h5 mt-4">Opzione B — Ollama (locale, no chiavi cloud)</h3>
        <p>
          Avvia anche il container Ollama (immagine pre-baked
          <code> qwen2.5:32k</code>, ~7 GB). Profili:
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`# CPU-only (default su macOS / Windows / Linux senza GPU NVIDIA)
make up

# GPU (Linux + NVIDIA, supporta CUDA)
make up-gpu

# Su macOS con Apple Silicon, Ollama gira meglio sull'host (Metal):
ollama serve &              # in un altro terminale
make up-host-ollama         # collega lo stack all'host Ollama`}
        </pre>

        <h3 className="h5 mt-4">Verifica</h3>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`make ps                                    # tutti i servizi healthy
curl -s http://localhost:18000/health      # {"status":"ok"}

# UI: http://localhost:13000
# Backend OpenAPI: http://localhost:18000/docs
# A2A AgentCard: http://localhost:18000/.well-known/agent-card.json`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>4. Sanity-check dei server MCP</h2>
        <p>
          Una volta su, puoi verificare che ogni MCP risponda:
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`# Lista tool di ckan-mcp (porta host 18080)
curl -sX POST http://localhost:18080/mcp \\
  -H 'Content-Type: application/json' \\
  -H 'Accept: application/json, text/event-stream' \\
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}' | jq

# Round-trip stdio diretto (senza HTTP) — utile per debug
make mcp-stdio-ckan
make mcp-stdio-istat
make mcp-stdio-osm`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>5. Sviluppo dei singoli pacchetti</h2>
        <p>
          Per iterare sul codice Python senza ricostruire l&apos;immagine
          Docker, installa i pacchetti in modalità editable nella stessa
          venv. <strong>Importante</strong>: <code>opendata-backend</code>{" "}
          richiede <code>--pre</code> perché <code>agent-framework</code> è
          pubblicato come pre-release.
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`# Crea una venv (il progetto si aspetta /tmp/oda-venv nei test, ma usa quello che preferisci)
python -m venv /tmp/oda-venv
source /tmp/oda-venv/bin/activate

# Pacchetti senza --pre
pip install -e ./opendata_core[dev]
pip install -e ./ckan-mcp-server[dev]
pip install -e ./istat-mcp-server[dev]
pip install -e ./osm-mcp[dev]

# Backend con --pre (agent-framework è pre-release)
pip install --pre -e ./opendata-backend[dev,azure,claude]`}
        </pre>

        <h3 className="h5 mt-4">Eseguire il backend fuori da Docker</h3>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`cd opendata-backend

# Postgres + Redis devono comunque essere su (li offre lo stack docker)
make ps

DATABASE_URL=postgresql+asyncpg://opendata:opendata@localhost:15432/opendata \\
REDIS_URL=redis://localhost:16379/1 \\
AUTH_ENABLED=false \\
ANTHROPIC_API_KEY=sk-ant-... \\
CKAN_MCP_URL=http://localhost:18080/mcp \\
ISTAT_MCP_URL=http://localhost:18081/mcp \\
OSM_MCP_URL=http://localhost:18085/mcp \\
opendata-backend-api  # http://localhost:8000`}
        </pre>

        <h3 className="h5 mt-4">Eseguire la UI fuori da Docker</h3>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`cd opendata-ai-ui
npm install

# punta al backend su porta host
echo 'NEXT_PUBLIC_API_URL=http://localhost:18000' > .env.local

npm run dev    # http://localhost:3000`}
        </pre>
        <p className="small text-muted">
          Tieni presente la regola R6: <code>output: &apos;export&apos;</code>{" "}
          è abilitato in <code>next.config.ts</code>, quindi non puoi
          aggiungere route handler in <code>app/api/*</code>.
        </p>
      </section>

      <section className="mt-4">
        <h2>6. Lint e test</h2>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`# Tutti i pacchetti Python
make lint
make test

# UI
cd opendata-ai-ui
npm run typecheck
npm run lint
npm run build   # equivalente a "next build" con static export`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>7. Stop e reset</h2>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`make down              # ferma tutti i container (mantiene i volumi)
docker volume ls       # vedi i volumi del progetto (postgres_data, redis_data, ...)
docker compose --env-file .env.local down -v   # reset COMPLETO (perdi tutti i dati)`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Layout del repo (alto livello)</h2>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`opendata-ai/
├── opendata_core/          # client asincroni condivisi (CKAN, SDMX, OSM)
├── ckan-mcp-server/        # FastMCP wrapper CKAN (11 tool)
├── istat-mcp-server/       # FastMCP wrapper SDMX 2.1 (ISTAT/Eurostat/OECD)
├── osm-mcp/                # FastMCP wrapper OSM (geocoding, POI, routing, render)
├── opendata-backend/       # FastAPI + orchestrator + A2A + classify
├── opendata-ai-ui/         # Next.js 15 static export (questa interfaccia)
├── vendor/agent-stack/     # sottomodulo: schema Postgres opendata.*
├── infra/                  # config Ollama, Caddy (legacy single-tenant)
├── docker-compose.yml      # stack completo
├── Makefile                # tutti i comandi quotidiani
├── .env.local.example      # template configurazione dev
└── README.md`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Risorse di approfondimento</h2>
        <ul>
          <li>
            <strong>Repository GitHub</strong>:{" "}
            <a href={REPO} target="_blank" rel="noopener noreferrer">
              {REPO}
            </a>{" "}
            — codice sorgente, issue tracker, release.
          </li>
          <li>
            <strong>README principale</strong>:{" "}
            <a
              href={`${REPO}#readme`}
              target="_blank"
              rel="noopener noreferrer"
            >
              {REPO}#readme
            </a>{" "}
            — panoramica dell&apos;architettura, tabella delle fonti dati,
            elenco endpoint.
          </li>
          <li>
            <strong>CLAUDE.md</strong>:{" "}
            <a
              href={`${REPO}/blob/main/CLAUDE.md`}
              target="_blank"
              rel="noopener noreferrer"
            >
              opendata-ai/CLAUDE.md
            </a>{" "}
            — invarianti architetturali, gotcha, regole operative (R1–R13).
          </li>
          <li>
            <strong>docker-compose.yml</strong>:{" "}
            <a
              href={`${REPO}/blob/main/docker-compose.yml`}
              target="_blank"
              rel="noopener noreferrer"
            >
              definizione di tutti i servizi
            </a>{" "}
            — porte host, dipendenze e profili.
          </li>
          <li>
            <strong>Issue tracker</strong>:{" "}
            <a
              href={`${REPO}/issues`}
              target="_blank"
              rel="noopener noreferrer"
            >
              {REPO}/issues
            </a>{" "}
            — bug report e richieste feature.
          </li>
        </ul>
      </section>

      <NextStepsCards
        items={[
          {
            href: "/docs/clients",
            title: "Client AI desktop",
            blurb: "Collega i server MCP a Claude Desktop o Cursor con un file JSON.",
            badge: "Config",
          },
          {
            href: "/docs/maf",
            title: "Microsoft Agent Framework",
            blurb: "Agente Python che usa gli MCP locali via streamable-http.",
            badge: "Python",
          },
          {
            href: "/docs/langgraph",
            title: "LangGraph",
            blurb: "Grafo LangGraph + langchain-mcp-adapters per orchestrare i tool.",
            badge: "Python",
          },
          {
            href: "/docs/a2a",
            title: "Agent-to-Agent",
            blurb: "Chiama il backend OpenData AI da un altro agente via JSON-RPC.",
            badge: "Protocollo",
          },
        ]}
      />
    </article>
  );
}
