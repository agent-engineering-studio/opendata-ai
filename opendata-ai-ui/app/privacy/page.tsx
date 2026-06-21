import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy policy — OpenData AI",
  description:
    "Informativa privacy ai sensi del Regolamento UE 2016/679 (GDPR) per il servizio OpenData AI: titolare, dati trattati, base giuridica, sub-processor, retention, diritti dell'interessato.",
};

export default function Page() {
  const LAST_UPDATED = "21 giugno 2026";
  const ISSUES_URL = "https://github.com/agent-engineering-studio/opendata-ai/issues";

  return (
    <article className="container py-5" style={{ maxWidth: 880 }}>
      <h1>Privacy policy</h1>
      <p className="text-muted small">
        Ultimo aggiornamento: {LAST_UPDATED} · Versione 1.1
      </p>
      <p className="lead">
        Informativa privacy ai sensi degli articoli 13 e 14 del Regolamento UE
        2016/679 (di seguito &ldquo;GDPR&rdquo;) relativa al trattamento dei
        dati personali nell&apos;ambito del progetto sperimentale OpenData AI.
      </p>

      <div className="alert alert-warning" role="status">
        <strong>Natura sperimentale del servizio.</strong> OpenData AI è un
        progetto di ricerca e prototipazione. Non è destinato a un uso
        produttivo critico né al trattamento di dati personali di terzi. Se
        intendi usare il servizio professionalmente, contattaci prima tramite
        il repository GitHub del progetto.
      </div>

      <div className="alert alert-info" role="note">
        <strong>Trattiamo solo open data pubblici.</strong> Le fonti
        interrogate dal servizio sono esclusivamente <em>open data già
        pubblicati</em> da pubbliche amministrazioni ed enti (portali CKAN,
        statistiche ufficiali SDMX di ISTAT/Eurostat/OCSE, OpenCoesione, ISPRA,
        OpenStreetMap): dati pubblici e privi di dati personali. Il servizio
        <strong> non raccoglie né tratta dati personali di terzi</strong> da
        queste fonti. Gli unici dati personali trattati sono quelli del tuo
        account e delle tue interazioni, descritti di seguito.
      </div>

      <section className="mt-4">
        <h2>1. Titolare del trattamento</h2>
        <p>
          Il Titolare del trattamento è{" "}
          <strong>Agent Engineering Studio</strong>, con sede operativa in
          Italia. Per qualunque richiesta o segnalazione in materia di privacy
          apri una issue sul{" "}
          <a href={ISSUES_URL} target="_blank" rel="noopener noreferrer">
            repository GitHub del progetto
          </a>
          . Sito web del Titolare:{" "}
          <a
            href="https://www.agentengineering.it"
            target="_blank"
            rel="noopener noreferrer"
          >
            agentengineering.it
          </a>
          .
        </p>
        <p>
          Non è stato nominato un Responsabile della protezione dei dati (DPO)
          in quanto il trattamento non rientra nei casi obbligatori
          previsti dall&apos;art. 37 GDPR. Per qualunque comunicazione in
          materia di protezione dati usa il canale GitHub indicato sopra.
        </p>
      </section>

      <section className="mt-4">
        <h2>2. Categorie di dati personali trattati</h2>
        <p>Il servizio tratta le seguenti categorie di dati:</p>
        <ul>
          <li>
            <strong>Dati di account (forniti tramite Clerk)</strong>:
            indirizzo email, nome visualizzato, identificatore utente univoco
            (<code>sub</code> JWT), data di registrazione, eventuale immagine
            profilo. Forniti dall&apos;utente in fase di sign-up.
          </li>
          <li>
            <strong>Dati di interazione</strong>: query in linguaggio
            naturale inviate alla chat, risposte generate, risorse open data
            consultate. Conservate nella tabella <code>opendata.history</code>{" "}
            del database PostgreSQL.
          </li>
          <li>
            <strong>Dataset preferiti</strong>: insieme di dataset
            esplicitamente salvati dall&apos;utente tramite la funzione
            &ldquo;preferiti&rdquo;. Tabella <code>opendata.favorites</code>.
          </li>
          <li>
            <strong>API keys</strong>: token API generati dall&apos;utente per
            accesso server-to-server (in arrivo). Vengono memorizzati come
            hash, mai in chiaro. Tabella <code>opendata.api_keys</code>.
          </li>
          <li>
            <strong>Dati tecnici</strong>: indirizzo IP, user-agent, timestamp
            delle richieste, conservati nei log applicativi del backend e nei
            log del reverse proxy (Traefik) per finalità di sicurezza e
            debug.
          </li>
          <li>
            <strong>Cookie tecnici di sessione</strong>: gestiti da Clerk per
            mantenere la sessione autenticata. Nessun cookie di profilazione
            o di terze parti per fini di marketing.
          </li>
        </ul>
        <p className="small text-muted">
          Categorie particolari di dati (art. 9 GDPR) o dati relativi a
          condanne penali (art. 10) <strong>non sono richiesti</strong>. Se
          inserisci accidentalmente tali dati in una query, contattaci per la
          cancellazione.
        </p>
      </section>

      <section className="mt-4">
        <h2>3. Finalità e base giuridica</h2>
        <div className="table-responsive">
          <table className="table table-sm table-bordered align-middle">
            <thead className="table-light">
              <tr>
                <th>Finalità</th>
                <th>Base giuridica (GDPR)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Erogazione del servizio (chat, mappa, classify)</td>
                <td>art. 6(1)(b) — esecuzione di un contratto/servizio richiesto</td>
              </tr>
              <tr>
                <td>Autenticazione e gestione account</td>
                <td>art. 6(1)(b) — necessario per fornire il servizio</td>
              </tr>
              <tr>
                <td>Personalizzazione della cronologia/favoriti</td>
                <td>art. 6(1)(b)</td>
              </tr>
              <tr>
                <td>Sicurezza del servizio e prevenzione abusi</td>
                <td>art. 6(1)(f) — legittimo interesse del Titolare</td>
              </tr>
              <tr>
                <td>Rate limit e diagnostica errori</td>
                <td>art. 6(1)(f) — legittimo interesse</td>
              </tr>
              <tr>
                <td>Adempimenti di legge (es. richieste di autorità)</td>
                <td>art. 6(1)(c)</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>
          Il conferimento dei dati di account è facoltativo, ma la
          mancata fornitura impedisce l&apos;utilizzo del servizio (che è
          dietro autenticazione).
        </p>
      </section>

      <section className="mt-4">
        <h2>4. Sub-processor e trasferimenti extra-UE</h2>
        <p>
          Per erogare il servizio ci avvaliamo dei seguenti{" "}
          <strong>responsabili del trattamento</strong> (sub-processor) ai
          sensi dell&apos;art. 28 GDPR:
        </p>
        <div className="table-responsive">
          <table className="table table-sm table-bordered align-middle">
            <thead className="table-light">
              <tr>
                <th>Fornitore</th>
                <th>Servizio</th>
                <th>Sede</th>
                <th>Garanzie</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <strong>Clerk Inc.</strong>
                </td>
                <td>
                  Autenticazione, gestione utenti, sessioni (cookie tecnici),
                  emissione JWT
                </td>
                <td>Stati Uniti</td>
                <td>
                  SCC (
                  <a
                    href="https://clerk.com/legal/dpa"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    DPA Clerk
                  </a>
                  )
                </td>
              </tr>
              <tr>
                <td>
                  <strong>Anthropic PBC</strong>
                </td>
                <td>
                  Elaborazione delle query in linguaggio naturale tramite il
                  modello Claude (Sonnet/Haiku). Le query inviate ad
                  Anthropic <em>non vengono usate per addestrare i modelli</em>{" "}
                  (vedi commercial terms).
                </td>
                <td>Stati Uniti</td>
                <td>
                  SCC + commercial terms (
                  <a
                    href="https://www.anthropic.com/legal/commercial-terms"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Anthropic Commercial Terms
                  </a>
                  )
                </td>
              </tr>
              <tr>
                <td>
                  <strong>Aruba S.p.A.</strong>
                </td>
                <td>
                  Hosting del backend, del database PostgreSQL e della
                  cache Redis su VPS dedicato
                </td>
                <td>Italia (UE)</td>
                <td>Trattamento interno UE</td>
              </tr>
              <tr>
                <td>
                  <strong>GitHub Inc.</strong>
                </td>
                <td>
                  Hosting statico del frontend tramite GitHub Pages, hosting
                  del codice sorgente
                </td>
                <td>Stati Uniti</td>
                <td>SCC (DPA Microsoft/GitHub)</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>
          I trasferimenti verso paesi terzi (Stati Uniti) avvengono sulla base
          delle <em>Standard Contractual Clauses</em> approvate dalla
          Commissione Europea (Decisione 2021/914) integrate dalle policy dei
          singoli fornitori.
        </p>
      </section>

      <section className="mt-4">
        <h2>5. Periodi di conservazione</h2>
        <ul>
          <li>
            <strong>Account utente</strong>: per tutta la durata
            dell&apos;account. Alla cancellazione vengono eliminati entro 30
            giorni; copie di backup vengono purgate entro 90 giorni
            dalla rotazione.
          </li>
          <li>
            <strong>Cronologia (history)</strong>: conservata per 12 mesi
            dalla creazione, poi eliminata automaticamente. L&apos;utente può
            chiedere la cancellazione anticipata.
          </li>
          <li>
            <strong>Favoriti</strong>: per tutta la durata dell&apos;account.
          </li>
          <li>
            <strong>API keys</strong>: fino alla revoca esplicita
            dell&apos;utente o all&apos;eliminazione dell&apos;account.
          </li>
          <li>
            <strong>Log tecnici</strong>: 30 giorni rolling.
          </li>
          <li>
            <strong>Cache classify</strong>: 24 ore in Redis (dato
            aggregato/anonimizzato per chiave hash della tassonomia).
          </li>
        </ul>
      </section>

      <section className="mt-4">
        <h2>6. Diritti dell&apos;interessato</h2>
        <p>
          In qualità di interessato hai diritto di esercitare in qualsiasi
          momento i diritti previsti dagli artt. 15-22 GDPR:
        </p>
        <ul>
          <li>
            <strong>Accesso</strong> ai dati personali che ti riguardano.
          </li>
          <li>
            <strong>Rettifica</strong> di dati inesatti o incompleti.
          </li>
          <li>
            <strong>Cancellazione</strong> (&ldquo;diritto all&apos;oblio&rdquo;).
          </li>
          <li>
            <strong>Limitazione</strong> del trattamento.
          </li>
          <li>
            <strong>Portabilità</strong> dei dati in formato strutturato e
            leggibile da dispositivo automatico (JSON).
          </li>
          <li>
            <strong>Opposizione</strong> ai trattamenti basati sul legittimo
            interesse.
          </li>
          <li>
            <strong>Reclamo</strong> al Garante per la protezione dei dati
            personali (
            <a
              href="https://www.garanteprivacy.it"
              target="_blank"
              rel="noopener noreferrer"
            >
              garanteprivacy.it
            </a>
            ).
          </li>
        </ul>
        <p>
          Per esercitare i diritti apri una issue (anche privata) sul{" "}
          <a href={ISSUES_URL} target="_blank" rel="noopener noreferrer">
            repository GitHub del progetto
          </a>
          , indicando l&apos;account interessato. Risponderemo entro 30 giorni
          come previsto dal GDPR.
        </p>
      </section>

      <section className="mt-4">
        <h2>7. Decisioni automatizzate e profilazione</h2>
        <p>
          Le risposte della chat sono generate da modelli LLM (Anthropic
          Claude) sulla base della query inviata. Non vengono effettuate
          decisioni automatizzate che producano effetti giuridici o incidano
          significativamente sulla persona ai sensi dell&apos;art. 22 GDPR.
        </p>
        <p>
          Non viene effettuata profilazione né attività di marketing
          automatizzato.
        </p>
      </section>

      <section className="mt-4">
        <h2>8. Cookie</h2>
        <p>
          Il sito utilizza esclusivamente <strong>cookie tecnici</strong>{" "}
          impostati da Clerk per mantenere la sessione utente autenticata.
          Nessun cookie analitico o di marketing è impostato dal Titolare.
          Per il dettaglio dei cookie Clerk consulta la{" "}
          <a
            href="https://clerk.com/legal/cookies"
            target="_blank"
            rel="noopener noreferrer"
          >
            cookie policy di Clerk
          </a>
          .
        </p>
      </section>

      <section className="mt-4">
        <h2>9. Sicurezza dei dati</h2>
        <ul>
          <li>Tutto il traffico è cifrato in transito via TLS 1.2+ (Let&apos;s Encrypt via Traefik).</li>
          <li>I JWT Clerk sono verificati lato backend via JWKS firmato.</li>
          <li>Il database PostgreSQL è accessibile solo dal backend, su rete interna.</li>
          <li>Le API key sono memorizzate come hash crittografico, mai in chiaro.</li>
          <li>Rate limit a finestra fissa (60 richieste/min/utente) per mitigare abusi.</li>
          <li>Il codice sorgente è pubblico (
            <a
              href="https://github.com/agent-engineering-studio/opendata-ai"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub
            </a>
            ): segnalazioni di vulnerabilità sono benvenute via issue privata.
          </li>
        </ul>
      </section>

      <section className="mt-4">
        <h2>10. Modifiche all&apos;informativa</h2>
        <p>
          Eventuali modifiche sostanziali vengono segnalate su questa pagina
          (data di &ldquo;Ultimo aggiornamento&rdquo; e &ldquo;Versione&rdquo;)
          e nel repository del progetto. Continuare a usare
          il servizio dopo le modifiche costituisce accettazione della
          versione aggiornata.
        </p>
      </section>

      <section className="mt-4">
        <h2>11. Contatti</h2>
        <p>
          Domande, richieste o segnalazioni privacy: apri una issue sul{" "}
          <a href={ISSUES_URL} target="_blank" rel="noopener noreferrer">
            repository GitHub del progetto
          </a>
          . Per tematiche non privacy vedi le{" "}
          <Link href="/note-legali">note legali</Link> e la{" "}
          <Link href="/docs">documentazione tecnica</Link>.
        </p>
      </section>
    </article>
  );
}
