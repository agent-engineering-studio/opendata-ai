import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Sostenibilità — OpenData AI",
  description:
    "Come si sostiene OpenData AI: uso esplorativo gratuito con limiti, abbonamenti per usi intensivi, sponsor e convenzioni con associazioni e PA. Un progetto open source al servizio del bene comune.",
};

const GITHUB_SPONSORS = "https://github.com/agent-engineering-studio";

export default function Page() {
  return (
    <div className="bg-bg-muted">
      {/* HERO */}
      <section className="bg-primary-900 text-white">
        <div className="container py-5">
          <div className="row">
            <div className="col-lg-9">
              <p
                className="mb-2 text-uppercase small fw-semibold"
                style={{ letterSpacing: "0.1em", opacity: 0.8 }}
              >
                Sostenibilità · bene comune · open source
              </p>
              <h1 className="display-5 fw-bold mb-3">
                Un progetto open source che ha bisogno di sostegno
              </h1>
              <p className="lead mb-0" style={{ opacity: 0.95 }}>
                OpenData AI è gratuito da esplorare, ma non è gratis da mandare
                avanti: ogni analisi usa modelli linguistici a pagamento e gira
                su un server mantenuto a spese di chi sviluppa il progetto. Per
                restare aperto e indipendente — al servizio del bene comune — ha
                bisogno di entrate che coprano l&apos;infrastruttura e
                reinvestano nell&apos;open source.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* PERCHÉ SERVE SOSTEGNO */}
      <section className="container py-5">
        <div className="row g-4">
          <div className="col-lg-8 mx-auto text-center mb-2">
            <h2 className="mb-3">Dove vanno le risorse</h2>
            <p className="lead text-muted">
              Trasparenza sui costi: le entrate servono a coprire questi capitoli
              e a far crescere il progetto come bene comune, non a generare
              profitto.
            </p>
          </div>
        </div>
        <div className="row g-4">
          <div className="col-md-4">
            <div className="card h-100 shadow-sm">
              <div className="card-body">
                <h5 className="card-title">Modelli linguistici</h5>
                <p className="card-text small text-muted mb-0">
                  Ogni analisi del territorio richiede più chiamate a modelli LLM
                  (Anthropic Claude): è la voce di costo che cresce con
                  l&apos;uso.
                </p>
              </div>
            </div>
          </div>
          <div className="col-md-4">
            <div className="card h-100 shadow-sm">
              <div className="card-body">
                <h5 className="card-title">Infrastruttura</h5>
                <p className="card-text small text-muted mb-0">
                  Server, banca dati e cache su cui gira il servizio, oggi a
                  carico personale di chi mantiene il progetto.
                </p>
              </div>
            </div>
          </div>
          <div className="col-md-4">
            <div className="card h-100 shadow-sm">
              <div className="card-body">
                <h5 className="card-title">Sviluppo open source</h5>
                <p className="card-text small text-muted mb-0">
                  Nuove fonti dati, lenti analitiche e miglioramenti, rilasciati
                  pubblicamente per la comunità.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* MODALITÀ DI SOSTEGNO */}
      <section className="bg-white border-top border-bottom">
        <div className="container py-5">
          <div className="row">
            <div className="col-lg-8 mx-auto text-center mb-5">
              <h2 className="mb-3">Come sostenere il progetto</h2>
              <p className="lead text-muted">
                Tre modalità complementari. I piani a pagamento sono{" "}
                <strong>in arrivo</strong>: i numeri qui sotto sono una proposta
                in evoluzione, non ancora attivabili.
              </p>
            </div>
          </div>
          <div className="row g-4">
            {/* Esplorativo */}
            <div className="col-lg-4">
              <div className="card h-100 shadow-sm">
                <div className="card-body d-flex flex-column">
                  <span className="badge bg-secondary align-self-start mb-2">
                    Esplorativo
                  </span>
                  <h4 className="card-title">Gratuito, con limiti</h4>
                  <p className="text-muted small">
                    Per provare il servizio e analizzare qualche territorio.
                  </p>
                  <ul className="small text-muted">
                    <li>Quota mensile di analisi limitata</li>
                    <li>Limite di richieste al minuto</li>
                    <li>Risultati in cache condivisa</li>
                  </ul>
                  <p className="small text-muted mt-auto mb-0">
                    Limiti pensati per contenere i costi e tenere il servizio
                    aperto a tutti.
                  </p>
                </div>
              </div>
            </div>
            {/* Abbonamento */}
            <div className="col-lg-4">
              <div className="card h-100 shadow-sm border-primary">
                <div className="card-body d-flex flex-column">
                  <span className="badge bg-primary align-self-start mb-2">
                    Abbonamento · in arrivo
                  </span>
                  <h4 className="card-title">Limiti superiori</h4>
                  <p className="text-muted small">
                    Per chi usa il servizio in modo intensivo o lo integra nei
                    propri strumenti.
                  </p>
                  <ul className="small text-muted">
                    <li>Quota di analisi più alta</li>
                    <li>API key dedicata per CI/CD e agenti</li>
                    <li>Priorità ed esportazioni avanzate</li>
                  </ul>
                  <p className="small text-muted mt-auto mb-0">
                    Le sottoscrizioni coprono direttamente i costi di LLM e
                    server.
                  </p>
                </div>
              </div>
            </div>
            {/* Sponsor & bandi */}
            <div className="col-lg-4">
              <div className="card h-100 shadow-sm">
                <div className="card-body d-flex flex-column">
                  <span className="badge bg-success align-self-start mb-2">
                    Sponsor &amp; convenzioni
                  </span>
                  <h4 className="card-title">Enti, associazioni, PA</h4>
                  <p className="text-muted small">
                    Per chi crede nella cultura del dato come bene comune.
                  </p>
                  <ul className="small text-muted">
                    <li>Sponsorizzazioni open source</li>
                    <li>Bandi e convenzioni con associazioni e PA</li>
                    <li>Deploy dedicati, formazione, affiancamento</li>
                  </ul>
                  <p className="small text-muted mt-auto mb-0">
                    Un modo per finanziare lo sviluppo e portarlo sul proprio
                    territorio.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-primary-900 text-white">
        <div className="container py-5 text-center">
          <h2 className="mb-3">Vuoi sostenere OpenData AI?</h2>
          <p className="lead mb-4" style={{ opacity: 0.9 }}>
            Sponsorizzazioni, convenzioni e abbonamenti aiutano a mantenere
            l&apos;infrastruttura e a tenere il progetto open source e
            indipendente.
          </p>
          <div className="d-flex flex-wrap justify-content-center gap-3">
            <a
              href={GITHUB_SPONSORS}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-light btn-lg"
            >
              Diventa sponsor
            </a>
            <Link href="/docs" className="btn btn-outline-light btn-lg">
              Scopri il progetto
            </Link>
          </div>
          <p className="mt-4 small" style={{ opacity: 0.7 }}>
            I piani a pagamento sono in fase di definizione: nessun addebito è
            attivo al momento. Per proposte di sponsor o convenzione, contattaci
            tramite il repository del progetto.
          </p>
        </div>
      </section>
    </div>
  );
}
