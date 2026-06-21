import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Note legali — OpenData AI",
  description:
    "Termini d'uso del progetto sperimentale OpenData AI: natura del servizio, licenza MIT del codice sorgente, limitazione di responsabilità, attribuzione dei dataset e contatti.",
};

export default function Page() {
  const LAST_UPDATED = "11 giugno 2026";

  return (
    <article className="container py-5" style={{ maxWidth: 880 }}>
      <h1>Note legali</h1>
      <p className="text-muted small">
        Ultimo aggiornamento: {LAST_UPDATED} · Versione 1.0
      </p>
      <p className="lead">
        Condizioni d&apos;uso del progetto sperimentale OpenData AI gestito
        da Agent Engineering Studio.
      </p>

      <section className="mt-4">
        <h2>1. Natura del servizio</h2>
        <p>
          OpenData AI è un <strong>progetto sperimentale di ricerca</strong>{" "}
          che aggrega tramite un agente conversazionale i dati pubblicati sui
          portali italiani CKAN (es. <code>dati.gov.it</code>) e sulle fonti
          statistiche ufficiali (ISTAT, Eurostat, OCSE) accessibili via SDMX.
          Le risposte generate hanno <strong>valore puramente informativo</strong>{" "}
          e non sostituiscono i dati ufficiali pubblicati dalle rispettive
          fonti, che restano l&apos;unica versione autoritativa.
        </p>
        <p>
          Le risposte sono prodotte da un Large Language Model (Anthropic
          Claude) e possono contenere errori, omissioni o interpretazioni
          imprecise. <strong>Verifica sempre i dati</strong> consultando la
          fonte indicata nelle risorse citate dall&apos;agente.
        </p>
      </section>

      <section className="mt-4">
        <h2>2. Limitazione di responsabilità</h2>
        <p>
          Il servizio è fornito &ldquo;as is&rdquo; e &ldquo;as available&rdquo;,
          senza garanzie esplicite o implicite di accuratezza, completezza,
          aggiornamento o adeguatezza a uno scopo specifico. In nessun caso
          Agent Engineering Studio sarà responsabile per danni diretti,
          indiretti, incidentali o consequenziali derivanti dall&apos;uso o
          dall&apos;impossibilità di usare il servizio o le informazioni
          fornite.
        </p>
        <p>
          L&apos;uso del servizio per finalità professionali, mediche, legali,
          finanziarie o di sicurezza è{" "}
          <strong>esplicitamente sconsigliato</strong> in questa fase
          sperimentale.
        </p>
      </section>

      <section className="mt-4">
        <h2>3. Licenza del codice sorgente</h2>
        <p>
          Il codice sorgente di OpenData AI è pubblicato con licenza{" "}
          <strong>MIT</strong> ed è disponibile su GitHub:
        </p>
        <p>
          <a
            href="https://github.com/agent-engineering-studio/opendata-ai"
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-outline-primary btn-sm"
          >
            github.com/agent-engineering-studio/opendata-ai
          </a>
        </p>
        <p>
          La licenza MIT consente l&apos;uso, copia, modifica e distribuzione
          del software con la sola condizione di mantenere l&apos;avviso di
          copyright. Il testo completo della licenza è nel file{" "}
          <code>LICENSE</code> del repository.
        </p>
      </section>

      <section className="mt-4">
        <h2>4. Diritti sui dataset</h2>
        <p>
          OpenData AI <strong>non possiede né ridistribuisce</strong> i
          dataset interrogati. Le risorse mostrate restano pubblicate dalle
          rispettive fonti e sono soggette alle licenze indicate dai portali
          di origine, tipicamente:
        </p>
        <ul>
          <li>
            <strong>CKAN italiani</strong> (dati.gov.it, portali regionali e
            municipali): tipicamente CC BY 4.0 o IODL 2.0.
          </li>
          <li>
            <strong>ISTAT</strong>: CC BY 3.0 IT salvo diversa indicazione.
          </li>
          <li>
            <strong>Eurostat</strong>: riuso libero con citazione della fonte
            (
            <a
              href="https://ec.europa.eu/eurostat/about-us/policies/copyright"
              target="_blank"
              rel="noopener noreferrer"
            >
              policy Eurostat
            </a>
            ).
          </li>
          <li>
            <strong>OCSE</strong>: termini OECD (riutilizzabili con
            citazione).
          </li>
          <li>
            <strong>OpenStreetMap</strong>: ODbL 1.0 (i layer mappa includono
            l&apos;attribuzione obbligatoria).
          </li>
        </ul>
        <p>
          È responsabilità dell&apos;utente verificare e rispettare la
          licenza specifica di ciascun dataset prima di riutilizzarlo.
        </p>
      </section>

      <section className="mt-4">
        <h2>5. Marchi e identità</h2>
        <p>
          &ldquo;OpenData AI&rdquo; è un nome di progetto sperimentale
          gestito da Agent Engineering Studio. Il marchio &ldquo;Claude&rdquo;
          è di Anthropic PBC. Il nome &ldquo;ISTAT&rdquo;, &ldquo;Eurostat&rdquo;,
          &ldquo;OCSE&rdquo; e i loghi sono dei rispettivi enti, citati
          solamente a fini informativi per identificare la fonte dati.
        </p>
      </section>

      <section className="mt-4">
        <h2>6. Modifiche e cessazione del servizio</h2>
        <p>
          Trattandosi di un progetto sperimentale, Agent Engineering Studio
          si riserva di modificare, sospendere o cessare il servizio in
          qualsiasi momento, anche senza preavviso. In caso di cessazione, gli
          utenti registrati potranno esportare i propri dati (cronologia e
          favoriti) entro 30 giorni dalla comunicazione, secondo i diritti
          previsti dal GDPR — vedi <Link href="/privacy">privacy policy</Link>.
        </p>
      </section>

      <section className="mt-4">
        <h2>7. Legge applicabile e foro competente</h2>
        <p>
          Il presente rapporto è regolato dalla legge italiana. Per qualunque
          controversia derivante dall&apos;uso del servizio è competente in via
          esclusiva il foro del luogo di residenza dell&apos;utente
          consumatore, ai sensi del Codice del Consumo, ove applicabile;
          altrimenti il foro di Milano.
        </p>
      </section>

      <section className="mt-4">
        <h2>8. Contatti</h2>
        <p>
          Per ogni questione legale o segnalazione apri una issue sul{" "}
          <a
            href="https://github.com/agent-engineering-studio/opendata-ai/issues"
            target="_blank"
            rel="noopener noreferrer"
          >
            repository GitHub del progetto
          </a>
          . Per richieste relative al trattamento dei dati personali vedi la{" "}
          <Link href="/privacy">privacy policy</Link>.
        </p>
      </section>
    </article>
  );
}
