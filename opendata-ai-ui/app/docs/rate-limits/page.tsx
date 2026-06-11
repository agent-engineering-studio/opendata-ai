import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Rate limits e quota — OpenData AI",
  description:
    "Politica di rate limit del backend OpenData AI: finestra fissa al minuto, 60 richieste per utente di default, HTTP 429 con header Retry-After.",
};

export default function Page() {
  return (
    <article className="container py-5">
      <p className="text-muted small mb-2">
        <Link href="/docs">← Documentazione</Link>
      </p>
      <h1>Rate limits e quota</h1>
      <p className="lead">
        OpenData AI protegge il backend con un rate limit a <strong>finestra
        fissa al minuto</strong>, identificato per utente Clerk. Il valore di
        default è <strong>60 richieste/minuto/utente</strong>; quando lo
        sforamento avviene il backend risponde <code>HTTP 429</code> con un
        header <code>Retry-After</code>.
      </p>

      <section className="mt-4">
        <h2>Come funziona</h2>
        <ul>
          <li>
            <strong>Bucket</strong>: il minuto corrente (wall-clock). Tutte le
            richieste autenticate dello stesso utente nello stesso minuto
            colpiscono lo stesso contatore Redis.
          </li>
          <li>
            <strong>TTL</strong>: il contatore scade automaticamente dopo 70
            secondi per recuperare in caso di skew di clock.
          </li>
          <li>
            <strong>Identità</strong>: il limit è per <code>sub</code> del JWT
            Clerk. Più sessioni dallo stesso utente condividono il bucket.
          </li>
          <li>
            <strong>Failure-open</strong>: se Redis è irraggiungibile, le
            richieste vengono lasciate passare (l&apos;agente non si ferma per
            un problema infrastrutturale).
          </li>
          <li>
            <strong>Endpoint esenti</strong>: <code>/health</code> e gli
            asset statici. Tutti gli endpoint REST e A2A sono soggetti al
            limite.
          </li>
        </ul>
      </section>

      <section className="mt-4">
        <h2>Configurazione lato backend</h2>
        <p>
          Settabile via env <code>RATE_LIMIT_PER_MINUTE</code>. Valori ≤ 0
          disabilitano il controllo.
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`# Default (in pyproject.toml / Settings)
RATE_LIMIT_PER_MINUTE=60

# Disabilita il rate limit (dev/test)
RATE_LIMIT_PER_MINUTE=0

# Burst-tollerante (es. 5 req/sec medio)
RATE_LIMIT_PER_MINUTE=300`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Risposta in caso di sforamento</h2>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`HTTP/1.1 429 Too Many Requests
Retry-After: 23
Content-Type: application/json

{
  "detail": "rate limit exceeded; slow down"
}`}
        </pre>
        <p>
          <code>Retry-After</code> contiene i secondi mancanti al rollover
          del minuto corrente. Un client cortese aspetta esattamente quel
          tempo prima di ritentare.
        </p>
      </section>

      <section className="mt-4">
        <h2>Pattern di retry consigliato</h2>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`import time, httpx

def call_with_retry(client: httpx.Client, request: httpx.Request) -> httpx.Response:
    for attempt in range(3):
        r = client.send(request)
        if r.status_code != 429:
            return r
        wait = int(r.headers.get("Retry-After", "5"))
        time.sleep(wait + 0.5)  # tiny jitter
    r.raise_for_status()
    return r`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Endpoint particolari</h2>
        <ul>
          <li>
            <strong>
              <code>POST /datasets/classify</code>
            </strong>{" "}
            — soggetto al rate limit come gli altri, ma le risposte sono
            servite da una cache a tre livelli (Redis 24h → Postgres durable
            → Anthropic Haiku). I duplicati non &ldquo;consumano&rdquo;
            chiamate al provider, ma <em>contano</em> nel bucket per minuto.
          </li>
          <li>
            <strong>
              <code>POST /datasets/search/stream</code>
            </strong>{" "}
            — la connessione streaming NDJSON conta come una sola richiesta
            (gli eventi successivi sono parte della stessa).
          </li>
          <li>
            <strong>
              <code>POST /a2a/</code>
            </strong>{" "}
            — stesso bucket, stesso limit. Le delegate ad altri agenti A2A
            non rilanciano sul nostro bucket: l&apos;agente esterno è un
            client come gli altri.
          </li>
        </ul>
      </section>

      <section className="mt-4">
        <h2>Quote elevate o piani dedicati</h2>
        <p>
          Il limite di default è pensato per uso esplorativo. Per integrazioni
          server-to-server o picchi noti (carichi batch, cron job) puoi
          chiedere una quota più alta o una <em>API key</em> dedicata —
          generabile dal pannello (in arrivo) tramite{" "}
          <code>POST /api-keys/generate</code>. Le API key applicano lo
          stesso meccanismo di rate limit ma usano un bucket separato dal
          token utente, così CLI e UI non si rubano richieste a vicenda.
        </p>
      </section>

      <section className="mt-4">
        <h2>Stato e telemetria</h2>
        <p>
          Il backend logga gli sforamenti come{" "}
          <code>rate limit hit subject=… count=… limit=…</code>. Per
          monitorare l&apos;adozione, ogni response 429 finisce
          nell&apos;access log del reverse proxy (Traefik), filtrabile per
          status code.
        </p>
      </section>
    </article>
  );
}
