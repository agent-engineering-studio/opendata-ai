import type { Metadata } from "next";
import Link from "next/link";

import { BuyMeACoffeeButton } from "@/components/BuyMeACoffeeButton";
import { SostieniButton } from "@/components/SostieniButton";

export const metadata: Metadata = {
  title: "Sostieni il progetto — OpenData AI",
  description:
    "OpenData AI è gratuito da esplorare e open source. Con il tuo sostegno aiuti a tenere il servizio aperto, indipendente e a disposizione di tutti.",
};

const GITHUB_SPONSORS = "https://github.com/agent-engineering-studio";
const OLLAMA_URL = "https://ollama.com";
const SPONSOR_EMAIL = "gzileni@agentengineering.it";

// Logo Ollama (monocromatico, eredita currentColor) per il credito "powered by".
function OllamaMark({ size = 18 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="currentColor" aria-hidden="true">
      <path d="M7.1 2.2c-1 0-1.7.9-1.9 2-.2.9-.1 1.9.2 2.8-1 1-1.6 2.4-1.6 4.1 0 1.3.4 2.4 1 3.4-.5.8-.8 1.8-.8 2.9 0 .9.2 1.7.5 2.4.2.4.6.6 1 .5.4-.1.6-.5.5-.9-.2-.6-.3-1.2-.3-1.9 0-.5.1-1 .2-1.4.5.4 1.1.7 1.7.9-.1.4-.2.9-.2 1.4 0 .6.1 1.2.4 1.7.2.4.6.5 1 .4.4-.2.5-.6.4-1-.1-.3-.2-.6-.2-1 0-.3 0-.5.1-.7.5.1 1.1.1 1.6.1s1.1 0 1.6-.1c.1.2.1.4.1.7 0 .4-.1.7-.2 1-.1.4 0 .8.4 1 .4.1.8 0 1-.4.3-.5.4-1.1.4-1.7 0-.5-.1-1-.2-1.4.6-.2 1.2-.5 1.7-.9.1.4.2.9.2 1.4 0 .7-.1 1.3-.3 1.9-.1.4.1.8.5.9.4.1.8-.1 1-.5.3-.7.5-1.5.5-2.4 0-1.1-.3-2.1-.8-2.9.6-1 1-2.1 1-3.4 0-1.7-.6-3.1-1.6-4.1.3-.9.4-1.9.2-2.8-.2-1.1-.9-2-1.9-2-.9 0-1.6.7-2 1.7-.9-.3-1.8-.3-2.7 0-.4-1-1.1-1.7-2-1.7zm1.4 7.1c.6 0 1 .6 1 1.3s-.4 1.3-1 1.3-1-.6-1-1.3.4-1.3 1-1.3zm7 0c.6 0 1 .6 1 1.3s-.4 1.3-1 1.3-1-.6-1-1.3.4-1.3 1-1.3zM12 13c.8 0 1.5.4 1.5.9 0 .3-.3.6-.7.8.2.1.4.4.4.6 0 .5-.5.8-1.2.8s-1.2-.3-1.2-.8c0-.2.2-.5.4-.6-.4-.2-.7-.5-.7-.8 0-.5.7-.9 1.5-.9z" />
    </svg>
  );
}

// Medaglia colorata (immagine dei livelli sponsor): nastro + disco + stella.
function Medal({ color }: { color: string }) {
  return (
    <svg viewBox="0 0 64 64" width={72} height={72} aria-hidden="true">
      <path d="M22 4 L30 30 L24 32 L16 8 Z" fill="#9aa7b4" />
      <path d="M42 4 L34 30 L40 32 L48 8 Z" fill="#7d8a98" />
      <circle cx="32" cy="42" r="18" fill={color} stroke="rgba(0,0,0,0.18)" strokeWidth="2" />
      <circle cx="32" cy="42" r="12" fill="none" stroke="rgba(255,255,255,0.55)" strokeWidth="1.5" />
      <path
        d="M32 33 l2.6 5.3 5.8 .8 -4.2 4.1 1 5.8 -5.2 -2.7 -5.2 2.7 1 -5.8 -4.2 -4.1 5.8 -.8 Z"
        fill="rgba(255,255,255,0.9)"
      />
    </svg>
  );
}

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
];

// Sponsorizzazioni per enti, associazioni e PA. Livelli "Coming Soon": il
// contatto è via email, senza quote pubblicate (si concordano sull'accordo).
const SPONSOR = [
  {
    badge: "Bronze",
    badgeClass: "bg-secondary",
    medal: "#CD7F32",
    pitch: "Per associazioni e piccoli enti che vogliono dare un segnale.",
    voci: [
      "Logo e nome nel README e nei ringraziamenti",
      "Newsletter sponsor con gli aggiornamenti del progetto",
    ],
    cardClass: "",
  },
  {
    badge: "Silver",
    badgeClass: "bg-primary",
    medal: "#9CA3AF",
    pitch: "Per enti e redazioni che integrano OpenData AI nei propri strumenti.",
    voci: [
      "Tutto ciò che offre Bronze + logo sul sito",
      "API key dell'ente per A2A e server MCP hosted",
      "Supporto prioritario",
    ],
    cardClass: "border-primary",
  },
  {
    badge: "Gold",
    badgeClass: "bg-warning text-dark",
    medal: "#FFC107",
    pitch: "Per PA e organizzazioni che portano il dato sul territorio.",
    voci: [
      "Tutto ciò che offre Silver + deploy/convenzione dedicata",
      "Formazione e affiancamento sulla cultura del dato",
      "Co-design di lenti e fonti per il tuo territorio",
    ],
    cardClass: "",
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
              <h1 className="display-5 fw-bold mb-3">Sostieni OpenData AI</h1>
              <p className="lead mb-0" style={{ opacity: 0.95 }}>
                OpenData AI è gratuito da esplorare e open source. Mantenerlo
                attivo e aggiornato ha dei costi: con il tuo sostegno aiuti a
                tenere il servizio aperto, indipendente e a disposizione di tutti.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* DOVE VA IL CONTRIBUTO — messaggio unico e generico */}
      <section className="container py-5">
        <div className="row">
          <div className="col-lg-8 mx-auto text-center">
            <h2 className="mb-3">Dove va il tuo contributo</h2>
            <p className="lead text-muted mb-0">
              Trasparenza totale: i contributi non generano profitto. Il tuo
              sostegno copre i costi del servizio — i{" "}
              <strong>modelli linguistici</strong> che elaborano le analisi,
              l&apos;<strong>infrastruttura</strong> che lo fa girare e lo{" "}
              <strong>sviluppo open source</strong> rilasciato per la comunità.
            </p>
          </div>
        </div>
      </section>

      {/* ABBONAMENTO PRIVATI */}
      <section className="bg-white border-top border-bottom">
        <div className="container py-5">
          <div className="row">
            <div className="col-lg-8 mx-auto text-center mb-5">
              <h2 className="mb-3">Abbonamento per privati</h2>
              <p className="lead text-muted">
                Due livelli per chi usa OpenData AI come persona. Sei un ente,
                un&apos;associazione o una PA? <a href="#sponsor">Diventa sponsor</a>.
              </p>
              <div className="alert alert-info text-start mt-4 mb-0" role="note">
                <strong>Cosa sblocca l&apos;abbonamento.</strong> Con un piano
                attivo le analisi useranno{" "}
                <a
                  href={OLLAMA_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="d-inline-flex align-items-center gap-1 fw-semibold text-decoration-none"
                >
                  <OllamaMark size={16} />
                  Ollama Cloud
                </a>
                , senza che tu debba gestire una chiave. In alternativa, puoi usare
                gratuitamente una <strong>tua chiave</strong> (Claude API,{" "}
                <a href={OLLAMA_URL} target="_blank" rel="noopener noreferrer">
                  Ollama Cloud
                </a>{" "}
                o un Ollama locale) dal <a href="/account/llm-key">tuo profilo</a>.
              </div>
            </div>
          </div>
          <div className="row g-4 justify-content-center">
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

      {/* SPONSOR (enti / associazioni / PA) — Coming Soon */}
      <section id="sponsor" className="container py-5">
        <div className="row">
          <div className="col-lg-8 mx-auto text-center mb-5">
            <h2 className="mb-3">Sei un ente, un&apos;associazione o una PA?</h2>
            <p className="lead text-muted">
              Le organizzazioni potranno sostenere OpenData AI come{" "}
              <strong>sponsor</strong>, su tre livelli. I programmi sono in
              arrivo: scrivici per ulteriori informazioni e per concordare i
              dettagli.
            </p>
          </div>
        </div>
        <div className="row g-4 justify-content-center">
          {SPONSOR.map((s) => (
            <div className="col-lg-4" key={s.badge}>
              <div className={`card h-100 shadow-sm text-center ${s.cardClass}`}>
                <div className="card-body d-flex flex-column align-items-center">
                  <Medal color={s.medal} />
                  <span className={`badge ${s.badgeClass} mt-2 mb-2`}>
                    {s.badge}
                  </span>
                  <p
                    className="fw-bold text-uppercase mb-3"
                    style={{ letterSpacing: "0.08em", color: "#6c757d" }}
                  >
                    Coming Soon
                  </p>
                  <p className="text-muted small">{s.pitch}</p>
                  <ul className="small text-muted text-start">
                    {s.voci.map((v) => (
                      <li key={v}>{v}</li>
                    ))}
                  </ul>
                  <a
                    href={`mailto:${SPONSOR_EMAIL}?subject=${encodeURIComponent(
                      `Sponsor ${s.badge} — OpenData AI`,
                    )}`}
                    className={`btn mt-auto ${
                      s.cardClass ? "btn-primary" : "btn-outline-primary"
                    }`}
                  >
                    Richiedi informazioni
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>

        <p className="text-center text-muted small mt-4 mb-0">
          Per ulteriori informazioni scrivici a{" "}
          <a href={`mailto:${SPONSOR_EMAIL}`}>{SPONSOR_EMAIL}</a>.
        </p>
      </section>

      {/* CTA */}
      <section className="bg-primary-900 text-white">
        <div className="container py-5 text-center">
          <h2 className="mb-3">Ogni contributo tiene il progetto in vita</h2>
          <p className="lead mb-4" style={{ opacity: 0.9 }}>
            Contributi e sponsorizzazioni mantengono OpenData AI open source e
            indipendente. Scegli come dare una mano.
          </p>
          <div className="d-flex flex-wrap justify-content-center align-items-center gap-3">
            <a href="#sponsor" className="btn btn-light btn-lg">
              Diventa sponsor
            </a>
            <Link href="/docs" className="btn btn-outline-light btn-lg">
              Scopri il progetto
            </Link>
          </div>
          <p className="mt-4 mb-2 small" style={{ opacity: 0.9 }}>
            Preferisci una donazione una-tantum? Offrici un caffè:
          </p>
          <div className="d-flex justify-content-center">
            <BuyMeACoffeeButton />
          </div>
        </div>
      </section>
    </div>
  );
}
