import type { Metadata } from "next";
import Link from "next/link";
import { NextStepsCards } from "@/components/NextStepsCards";

export const metadata: Metadata = {
  title: "API key — autenticare le chiamate A2A — OpenData AI",
  description:
    "Genera, usa e revoca le API key di OpenData AI per autenticare le chiamate A2A. In abbonamento, l'endpoint A2A è l'unica superficie pubblica: la chiave è l'unica credenziale necessaria per integrare la piattaforma nel tuo framework di agenti.",
};

const GITHUB_URL = "https://github.com/agent-engineering-studio/opendata-ai";

export default function Page() {
  return (
    <article className="container py-5">
      <p className="text-muted small mb-2">
        <Link href="/docs">← Portale Sviluppatori</Link>
      </p>
      <h1>API key — autenticare le chiamate A2A</h1>
      <p className="lead">
        Le <strong>API key</strong> sono la credenziale per integrare OpenData AI
        nel tuo framework di agenti. Nell&apos;offerta in{" "}
        <strong>abbonamento</strong> la piattaforma espone una sola superficie
        pubblica — l&apos;endpoint <strong>A2A</strong> — e la chiave è tutto ciò
        che serve per autenticare le chiamate <em>headless</em>, dove non c&apos;è
        una sessione browser. La chiave è legata al tuo account e al tuo{" "}
        <strong>piano di abbonamento</strong>: cronologia e rate limit restano
        attribuiti al tuo utente.
      </p>

      <div className="alert alert-info">
        <strong>Hosted = solo A2A.</strong> In abbonamento non è esposto un
        backend REST pubblico: usi l&apos;API key esclusivamente
        sull&apos;endpoint A2A (<code>/a2a/</code>). Vuoi l&apos;API REST
        completa e i server MCP? Esegui il progetto in{" "}
        <strong>self-host</strong> — è open source (licenza MIT), vedi la{" "}
        <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
          repository GitHub
        </a>
        .
      </div>

      <div className="alert alert-warning">
        Il token in chiaro viene mostrato <strong>una sola volta</strong>, alla
        creazione. Il backend ne conserva solo l&apos;hash SHA-256 e non può più
        recuperarlo: salvalo subito in un gestore di segreti. Se lo perdi, revoca
        la chiave e generane una nuova.
      </div>

      <section className="mt-4">
        <h2>1. Genera una chiave</h2>
        <p>
          Crea e gestisci le tue chiavi dal pannello account, in{" "}
          <Link href="/account/api-keys">Account → API key</Link>. Dai a ogni
          chiave un&apos;etichetta che indichi l&apos;integrazione (
          <code>my-agent</code>, <code>ci</code>, …) così potrai revocarla
          singolarmente. Il token (prefisso <code>od_</code>) compare una sola
          volta: copialo subito.
        </p>
      </section>

      <section className="mt-4">
        <h2>2. Usa la chiave sull&apos;endpoint A2A</h2>
        <p>
          Passa il token come <code>Bearer</code> (i token API iniziano per{" "}
          <code>od_</code>) oppure nell&apos;header dedicato{" "}
          <code>X-API-Key</code>. È la credenziale per le invocazioni JSON-RPC su{" "}
          <code>/a2a/</code>.
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`export OPENDATA_API_KEY="od_3pQ…"

# A2A — invocazione JSON-RPC autenticata con l'API key
curl -sX POST https://api.opendata-ai.it/a2a/ \\
  -H "Authorization: Bearer $OPENDATA_API_KEY" \\
  -H 'Content-Type: application/json' \\
  -d '{
    "jsonrpc":"2.0","id":"1","method":"SendMessage",
    "params":{"message":{
      "messageId":"m-1","role":"ROLE_USER",
      "parts":[{"text":"qualità aria a Milano"}],
      "metadata":{"skill":"search_open_data"}
    }}
  }'

# In alternativa: header dedicato X-API-Key (equivalente)
curl -sX POST https://api.opendata-ai.it/a2a/ \\
  -H "X-API-Key: $OPENDATA_API_KEY" \\
  -H 'Content-Type: application/json' \\
  -d '{ … }'`}
        </pre>
        <p className="small text-muted">
          La discovery A2A (<code>/.well-known/agent-card.json</code>) resta
          pubblica: solo le invocazioni su <code>/a2a/</code> richiedono la
          chiave. Per gli esempi completi (skill, SDK Python, shape della
          risposta) vedi <Link href="/docs/a2a">/docs/a2a</Link>.
        </p>
      </section>

      <section className="mt-4">
        <h2>3. Elenca e revoca</h2>
        <p>
          Dal pannello <Link href="/account/api-keys">Account → API key</Link>{" "}
          vedi l&apos;elenco delle chiavi (mai il token, solo i metadati:{" "}
          <code>last_used_at</code>, <code>revoked_at</code>) e puoi revocarne
          una in qualunque momento. La revoca è immediata e definitiva.
        </p>
      </section>

      <section className="mt-4">
        <h2>Abbonamento e quota</h2>
        <p>
          Ogni utente ha un <code>subscription_tier</code> (default{" "}
          <code>free</code>) che determina la quota di richieste al minuto. Le
          chiamate fatte con un&apos;API key condividono il budget del tuo
          account: superata la soglia ricevi <code>HTTP 429</code> con header{" "}
          <code>Retry-After</code> (finestra fissa al minuto). I piani di
          abbonamento e i relativi massimali sono in via di definizione.
        </p>
      </section>

      <section className="mt-4">
        <h2>Self-host: REST + MCP</h2>
        <p>
          Se esegui il progetto in self-host hai accesso anche all&apos;API REST
          completa (<code>/datasets/search</code>, <code>/maturity/*</code>,{" "}
          <code>/territory/*</code>, …) e ai tre server MCP, oltre ad A2A. In
          quel caso l&apos;API key autentica <em>tutti</em> gli endpoint. Setup e
          riferimento REST sono nella{" "}
          <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
            repository GitHub
          </a>
          ; per i server MCP vedi <Link href="/docs/mcp">/docs/mcp</Link>.
        </p>
      </section>

      <section className="mt-4">
        <h2>Buone pratiche</h2>
        <ul>
          <li>
            <strong>Una chiave per integrazione</strong>: nomina le chiavi per
            servizio (<code>ci</code>, <code>etl-nightly</code>, …) così puoi
            revocarne una senza toccare le altre.
          </li>
          <li>
            <strong>Mai nel codice</strong>: tienile in variabili
            d&apos;ambiente / secret manager, non nei repository.
          </li>
          <li>
            <strong>Ruota periodicamente</strong>: genera la nuova chiave,
            aggiorna l&apos;integrazione, poi revoca la vecchia.
          </li>
        </ul>
      </section>

      <section className="mt-4">
        <NextStepsCards
          heading="Vai oltre"
          items={[
            {
              href: "/docs/a2a",
              title: "Agent-to-Agent",
              blurb: "Invoca l'orchestratore via JSON-RPC con la tua API key.",
              badge: "Abbonamento",
            },
            {
              href: "/docs/mcp",
              title: "Server MCP",
              blurb: "I tre server FastMCP CKAN / ISTAT / OSM per progetti custom.",
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
