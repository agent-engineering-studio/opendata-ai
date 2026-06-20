import type { Metadata } from "next";
import Link from "next/link";
import { NextStepsCards } from "@/components/NextStepsCards";

export const metadata: Metadata = {
  title: "API key — accesso programmatico — OpenData AI",
  description:
    "Genera, elenca e revoca le API key di OpenData AI e usale per autenticare le chiamate REST, A2A e gli endpoint MCP ospitati. Le chiavi sono legate al tuo account e al tuo piano di abbonamento.",
};

export default function Page() {
  return (
    <article className="container py-5">
      <p className="text-muted small mb-2">
        <Link href="/docs">← Portale Sviluppatori</Link>
      </p>
      <h1>API key — accesso programmatico</h1>
      <p className="lead">
        Le <strong>API key</strong> sono la credenziale per chiamare OpenData AI
        da script, agenti e integrazioni <em>headless</em>, dove non c&apos;è
        una sessione browser Clerk. Una chiave è legata al tuo account: la usi al
        posto del JWT Clerk e tutto (cronologia, preferiti, rate limit) resta
        attribuito al tuo utente e al tuo <strong>piano di abbonamento</strong>.
      </p>

      <div className="alert alert-warning">
        Il token in chiaro viene mostrato <strong>una sola volta</strong>, alla
        creazione. Il backend ne conserva solo l&apos;hash SHA-256 e non può più
        recuperarlo: salvalo subito in un gestore di segreti. Se lo perdi, revoca
        la chiave e generane una nuova.
      </div>

      <section className="mt-4">
        <h2>1. Genera una chiave</h2>
        <p>
          La prima chiave si crea da una sessione autenticata (JWT Clerk dalla
          UI). <code>name</code> è un&apos;etichetta libera per riconoscerla.
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`curl -sX POST https://api.opendata-ai.it/api-keys/generate \\
  -H 'Authorization: Bearer <clerk_jwt>' \\
  -H 'Content-Type: application/json' \\
  -d '{"name":"my-cli"}'

# 201 Created — il token compare SOLO qui:
# {
#   "id": 42,
#   "name": "my-cli",
#   "token": "od_3pQ…<32-byte-urlsafe>",
#   "created_at": "2026-06-19T10:00:00+00:00"
# }`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>2. Usa la chiave</h2>
        <p>
          Passa il token come <code>Bearer</code> (i token API iniziano per{" "}
          <code>od_</code>, così il backend li distingue dai JWT Clerk) oppure
          nell&apos;header dedicato <code>X-API-Key</code>. Funziona su{" "}
          <strong>tutti</strong> gli endpoint REST e sull&apos;endpoint A2A.
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`# Equivalenti: usa l'uno o l'altro header.
export OPENDATA_API_KEY="od_3pQ…"

# REST — Authorization: Bearer
curl -s https://api.opendata-ai.it/datasets/search \\
  -H "Authorization: Bearer $OPENDATA_API_KEY" \\
  -G --data-urlencode 'q=qualità aria a Milano'

# REST — header X-API-Key
curl -s https://api.opendata-ai.it/datasets/search \\
  -H "X-API-Key: $OPENDATA_API_KEY" \\
  -G --data-urlencode 'q=qualità aria a Milano'

# A2A — stesso token sull'endpoint JSON-RPC
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
  }'`}
        </pre>
        <p className="small text-muted">
          La discovery A2A (<code>/.well-known/agent-card.json</code>) resta
          pubblica: solo le invocazioni su <code>/a2a/</code> richiedono la
          chiave. Per gli esempi completi vedi{" "}
          <Link href="/docs/a2a">/docs/a2a</Link>.
        </p>
      </section>

      <section className="mt-4">
        <h2>3. Elenca e revoca</h2>
        <p>
          L&apos;elenco non riespone mai il token, solo i metadati (compreso{" "}
          <code>last_used_at</code> e <code>revoked_at</code>). La revoca è
          immediata e definitiva.
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`# Elenco delle tue chiavi (attive + revocate, più recenti prima)
curl -s https://api.opendata-ai.it/api-keys \\
  -H "Authorization: Bearer $OPENDATA_API_KEY" | jq
# [ { "id":42, "name":"my-cli",
#     "created_at":"…", "last_used_at":"…", "revoked_at":null } ]

# Revoca una chiave per id → 204 No Content
curl -sX DELETE https://api.opendata-ai.it/api-keys/42 \\
  -H "Authorization: Bearer $OPENDATA_API_KEY"`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Server MCP ospitati</h2>
        <p>
          I tre server MCP (CKAN, ISTAT, OSM){" "}
          <strong>non implementano un&apos;autenticazione propria</strong>: sono
          componenti di infrastruttura, pensati per girare in rete privata
          dietro al backend / a Traefik. Se esponi gli endpoint{" "}
          <code>streamable-http</code> pubblicamente, mettili dietro lo stesso
          gateway e usa l&apos;API key come token statico negli header del
          client MCP. In locale via <code>stdio</code> (Claude Desktop, Cursor)
          non serve alcuna chiave: il client avvia il server come
          sotto-processo. Vedi <Link href="/docs/mcp">/docs/mcp</Link> e{" "}
          <Link href="/docs/clients">/docs/clients</Link>.
        </p>
      </section>

      <section className="mt-4">
        <h2>Abbonamento e quota</h2>
        <p>
          Ogni utente ha un <code>subscription_tier</code> (default{" "}
          <code>free</code>) che determina la quota di richieste al minuto. Le
          chiamate fatte con un&apos;API key condividono il budget del tuo
          account: superata la soglia ricevi <code>HTTP 429</code> con header{" "}
          <code>Retry-After</code>. I limiti per piano sono descritti in{" "}
          <Link href="/docs/rate-limits">/docs/rate-limits</Link>; i piani di
          abbonamento e i relativi massimali sono in via di definizione.
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
              badge: "Protocollo",
            },
            {
              href: "/docs/mcp",
              title: "Server MCP",
              blurb: "I tre server FastMCP CKAN / ISTAT / OSM e come esporli.",
              badge: "Panoramica",
            },
            {
              href: "/docs/rate-limits",
              title: "Rate limit e quota",
              blurb: "Finestra al minuto, limiti per piano e header Retry-After.",
              badge: "Operativo",
            },
          ]}
        />
      </section>
    </article>
  );
}
