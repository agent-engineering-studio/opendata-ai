import type { Metadata } from "next";
import Link from "next/link";

import { SostieniButton } from "@/components/SostieniButton";

export const metadata: Metadata = {
  title: "Sostieni il progetto — OpenData AI",
  description:
    "OpenData AI è gratuito da esplorare e open source. Sostienilo con un contributo mensile a misura delle tue esigenze: ogni piano è calibrato sul costo reale dell'infrastruttura (server, banca dati, modelli linguistici) e tiene il progetto aperto e indipendente.",
};

const GITHUB_SPONSORS = "https://github.com/agent-engineering-studio";

// Stripe Payment Links — account "agentengineering", modalità LIVE (EUR/mese).
// Prodotti/prezzi annotati in docs/sostieni.md. Se un link è vuoto il pulsante
// ricade su GITHUB_SPONSORS.
const CONTRIBUTI = [
  {
    badge: "Sostenitore",
    badgeClass: "bg-secondary",
    nome: "Caffè mensile",
    prezzo: "8",
    periodo: "/mese",
    pitch: "Per chi usa OpenData AI ogni tanto e vuole tenerlo in vita.",
    copre: "Copre una fetta del server che fa girare il servizio.",
    voci: [
      "Quota di analisi più ampia del piano gratuito",
      "Badge sostenitore (riconoscimento pubblico)",
      "Aggiornamenti sulle nuove lenti e fonti dati",
    ],
    cardClass: "",
    link: "https://buy.stripe.com/fZu8wQ7Km4wY02O4oY3oA01", // Stripe Payment Link · Sostenitore €8/mese
  },
  {
    badge: "Pro",
    badgeClass: "bg-primary",
    nome: "Uso intensivo",
    prezzo: "19",
    periodo: "/mese",
    pitch:
      "Per professionisti, giornalisti e sviluppatori che integrano il servizio nei propri strumenti.",
    copre: "Da solo copre quasi per intero il costo mensile del server.",
    voci: [
      "Quota di analisi alta",
      "API key dedicata per CI/CD e agenti",
      "Priorità ed esportazioni avanzate",
    ],
    cardClass: "border-primary",
    link: "https://buy.stripe.com/dRm28s5Ce6F602O3kU3oA02", // Stripe Payment Link · Pro €19/mese
  },
  {
    badge: "Team / PA",
    badgeClass: "bg-success",
    nome: "Enti e redazioni",
    prezzo: "39",
    periodo: "/mese",
    pitch:
      "Per redazioni, associazioni e pubbliche amministrazioni che adottano il dato come bene comune.",
    copre: "Copre il server e una parte dei costi variabili dei modelli linguistici.",
    voci: [
      "Quota condivisa e più API key",
      "Supporto prioritario",
      "Base per convenzioni, deploy dedicati e formazione",
    ],
    cardClass: "",
    link: "https://buy.stripe.com/3cIfZi4ya0gI5n85t23oA03", // Stripe Payment Link · Team/PA €39/mese
  },
];

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
                Sostieni · bene comune · open source
              </p>
              <h1 className="display-5 fw-bold mb-3">
                Tieni vivo OpenData AI con un contributo mensile
              </h1>
              <p className="lead mb-0" style={{ opacity: 0.95 }}>
                Esplorare OpenData AI è e resta gratuito. Ma ogni analisi usa
                modelli linguistici a pagamento e gira su un server mantenuto a
                spese di chi sviluppa il progetto. Con un contributo mensile —
                grande o piccolo, a misura delle tue esigenze — copri una parte
                concreta dei costi e aiuti a tenere il servizio aperto,
                indipendente e open source.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* DOVE VANNO LE RISORSE */}
      <section className="container py-5">
        <div className="row g-4">
          <div className="col-lg-8 mx-auto text-center mb-2">
            <h2 className="mb-3">Dove va il tuo contributo</h2>
            <p className="lead text-muted">
              Trasparenza totale: i contributi non generano profitto, coprono i
              costi reali del servizio. L&apos;infrastruttura di base costa circa{" "}
              <strong>24 €/mese</strong> (VPS Aruba), a cui si somma il costo
              variabile dei modelli linguistici che cresce con l&apos;uso.
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
                  Server, banca dati e cache su cui gira il servizio: circa
                  24 €/mese di VPS, oggi a carico personale di chi mantiene il
                  progetto.
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

      {/* CONTRIBUTI MENSILI */}
      <section className="bg-white border-top border-bottom">
        <div className="container py-5">
          <div className="row">
            <div className="col-lg-8 mx-auto text-center mb-5">
              <h2 className="mb-3">Scegli il contributo giusto per te</h2>
              <p className="lead text-muted">
                Tre livelli pensati sul costo reale dell&apos;infrastruttura.
                Scegli quello più vicino al tuo utilizzo: ogni contributo, anche
                il più piccolo, fa la differenza.
              </p>
            </div>
          </div>
          <div className="row g-4">
            {CONTRIBUTI.map((c) => (
              <div className="col-lg-4" key={c.nome}>
                <div className={`card h-100 shadow-sm ${c.cardClass}`}>
                  <div className="card-body d-flex flex-column">
                    <span
                      className={`badge ${c.badgeClass} align-self-start mb-2`}
                    >
                      {c.badge}
                    </span>
                    <h4 className="card-title mb-1">{c.nome}</h4>
                    <p className="mb-2">
                      <span className="display-6 fw-bold">{c.prezzo} €</span>
                      <span className="text-muted">{c.periodo}</span>
                    </p>
                    <p className="text-muted small">{c.pitch}</p>
                    <ul className="small text-muted">
                      {c.voci.map((v) => (
                        <li key={v}>{v}</li>
                      ))}
                    </ul>
                    <p className="small text-muted mt-auto mb-3">{c.copre}</p>
                    <SostieniButton
                      link={c.link}
                      fallback={GITHUB_SPONSORS}
                      prezzo={c.prezzo}
                      primary={!!c.cardClass}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
          <p className="text-center text-muted small mt-4 mb-0">
            Pagamenti gestiti in modo sicuro tramite Stripe. Puoi disdire il
            contributo in qualsiasi momento.
          </p>
        </div>
      </section>

      {/* SPONSOR & CONVENZIONI */}
      <section className="container py-5">
        <div className="row">
          <div className="col-lg-8 mx-auto text-center">
            <h2 className="mb-3">Sei un ente, un&apos;associazione o una PA?</h2>
            <p className="lead text-muted mb-4">
              Oltre ai contributi mensili, sosteniamo il progetto con
              sponsorizzazioni open source, bandi e convenzioni: deploy dedicati,
              formazione e affiancamento sulla cultura del dato, per portare
              OpenData AI sul tuo territorio.
            </p>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-primary-900 text-white">
        <div className="container py-5 text-center">
          <h2 className="mb-3">Ogni contributo tiene il progetto in vita</h2>
          <p className="lead mb-4" style={{ opacity: 0.9 }}>
            Contributi mensili, sponsorizzazioni e convenzioni coprono
            l&apos;infrastruttura e mantengono OpenData AI open source e
            indipendente. Scegli come dare una mano.
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
        </div>
      </section>
    </div>
  );
}
