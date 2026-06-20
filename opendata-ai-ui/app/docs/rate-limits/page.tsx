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
        <Link href="/docs">← Portale Sviluppatori</Link>
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
            Clerk. Più sessioni dallo stesso utente condividono il bucket. Le
            chiamate fatte con un&apos;<Link href="/docs/api-keys">API key</Link>{" "}
            condividono lo stesso bucket dell&apos;utente proprietario: CLI e UI
            attingono allo stesso budget.
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
{`# Limite base (tier "free") — vale per tutti finché non hanno un piano
RATE_LIMIT_PER_MINUTE=60

# Disabilita il rate limit (dev/test)
RATE_LIMIT_PER_MINUTE=0

# Override per piano (subscription tier): tier=limit, separati da virgola.
# Un tier non elencato — incluso "free" — ricade sul limite base sopra.
RATE_LIMIT_TIERS=pro=300,enterprise=1200`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Quota per piano (subscription tier)</h2>
        <p>
          Ogni utente ha un <code>subscription_tier</code> (default{" "}
          <code>free</code>). Il limite al minuto è risolto dal tier: i valori
          per piano si configurano con <code>RATE_LIMIT_TIERS</code>; un tier non
          elencato ricade sul limite base. Finché i piani non sono assegnati
          tutti restano <code>free</code>, quindi gli override sono inerti.
        </p>
        <div className="table-responsive">
          <table className="table table-bordered align-middle">
            <thead className="table-light">
              <tr>
                <th>Tier</th>
                <th>req/min (consigliato)</th>
                <th>Per chi</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><code>free</code></td>
                <td>60 (base)</td>
                <td>utente UI registrato</td>
              </tr>
              <tr>
                <td><code>pro</code></td>
                <td>300</td>
                <td>singolo integratore / agente, job batch</td>
              </tr>
              <tr>
                <td><code>enterprise</code></td>
                <td>1200</td>
                <td>PA / partner: più agenti, carichi pianificati</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="small text-muted">
          Per un tier &ldquo;illimitato&rdquo; usa un numero molto alto, non{" "}
          <code>0</code>: lo <code>0</code> disattiva del tutto il limitatore per
          quel tier. I valori sopra sono un punto di partenza prudente — si
          alzano da config, senza rideploy del codice.
        </p>
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
          Il limite base è pensato per uso esplorativo. Per integrazioni
          server-to-server o picchi noti (carichi batch, cron job) la strada è
          un <strong>tier più alto</strong> sul tuo account (vedi tabella sopra)
          e una <Link href="/docs/api-keys">API key</Link> dedicata, generabile
          con <code>POST /api-keys/generate</code>. La chiave eredita il tier e
          il bucket del tuo utente: alzare il piano alza il limite per UI, CLI e
          A2A insieme.
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
