import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Roadmap — OpenData AI",
  description:
    "La roadmap di sviluppo di OpenData AI: dove cresce la piattaforma. Cinque punti — qualità del dato, maturità open data, ottimizzazione, pubblicazione secondo gli standard, nuove fonti e automazione. Niente scadenze, solo direzioni utili.",
};

const ISSUES_BASE = "https://github.com/agent-engineering-studio/opendata-ai/issues";

type Stato = "now" | "wip" | "near" | "explore";

const STATO: Record<Stato, { label: string; cls: string }> = {
  now: { label: "già attivo", cls: "bg-success-subtle text-success-emphasis" },
  wip: { label: "in test", cls: "bg-warning-subtle text-warning-emphasis" },
  near: { label: "a portata", cls: "bg-primary-subtle text-primary-emphasis" },
  explore: { label: "da esplorare", cls: "bg-secondary-subtle text-secondary-emphasis" },
};

type Punto = {
  n: string;
  icon: string;
  titolo: string;
  perche: string;
  issue: number;
  wip?: boolean; // funzionalità implementate, in fase di test
  voci: { titolo: string; testo: string; stato?: Stato }[];
};

const ROADMAP: Punto[] = [
  {
    n: "01",
    icon: "🩺",
    titolo: "Porta un file di dati, ti diciamo come migliorarlo",
    perche:
      "Carichi un file (un foglio di calcolo, un elenco, una mappa) e ricevi un controllo automatico, la versione già sistemata e la scheda descrittiva pronta. Così il dato diventa più pulito, comprensibile e facile da riusare.",
    issue: 49,
    wip: true,
    voci: [
      { titolo: "Controllo automatico", stato: "wip", testo: "Trova gli errori più comuni — celle vuote, date scritte in modi diversi, accenti sbagliati, doppioni — e dice quanto è “in salute” il dato, prima e dopo. Disponibile nella pagina Qualità, in fase di test." },
      { titolo: "Versione corretta da scaricare", stato: "wip", testo: "Intestazioni più chiare, formato uniforme, date ISO, separatore standard: riscarichi il file già sistemato, con l'elenco delle modifiche. Disponibile, in fase di test." },
      { titolo: "Dati sulla mappa sempre al posto giusto", stato: "explore", testo: "Se le posizioni sono indicate in modo diverso, le rimette a posto perché compaiano correttamente sulla mappa." },
      { titolo: "Scheda descrittiva pronta", stato: "explore", testo: "Titolo, descrizione, licenza, ogni quanto si aggiorna: già compilata, da incollare sul portale dei dati." },
      { titolo: "Suggerimenti per arricchire", stato: "explore", testo: "Collega il dato ad altre informazioni utili (il comune di riferimento, la posizione sulla mappa) per renderlo più completo." },
    ],
  },
  {
    n: "02",
    icon: "📊",
    titolo: "Quanto è “aperto” il tuo ente, e cosa fare per migliorare",
    perche:
      "Già oggi misuriamo quanto bene un ente pubblica i suoi dati. Il passo avanti è dire, in modo concreto, cosa conviene fare per primo e in quale direzione crescere.",
    issue: 50,
    voci: [
      { titolo: "Pagella in quattro aree", stato: "now", testo: "Quanto è aperto e ben tenuto il patrimonio dati dell'ente. C'è già: va resa più “azionabile”." },
      { titolo: "Le mosse che contano di più", testo: "Le azioni che migliorano di più la situazione: quelle facili e rapide, separate da quelle più strategiche." },
      { titolo: "Un percorso su misura", testo: "“Pubblica questi dati che oggi mancano e sali di livello”: una strada chiara verso il passo successivo." },
      { titolo: "Confronto con enti simili", testo: "Come si posiziona rispetto a comuni della stessa dimensione o regione, e come cambia nel tempo." },
      { titolo: "Controllo nel tempo e avvisi", stato: "explore", testo: "Segnala dati non aggiornati, collegamenti che non funzionano e peggioramenti, appena succedono." },
    ],
  },
  {
    n: "03",
    icon: "⚙️",
    titolo: "Rendere il dato più ordinato e veloce da usare",
    perche:
      "Trasformare un elenco disordinato in qualcosa di ben organizzato e facile da consultare, anche quando i dati sono davvero tanti.",
    issue: 51,
    voci: [
      { titolo: "Mettere ordine", stato: "near", testo: "Suggerisce come organizzare il dato — cosa raggruppare, quali informazioni tenere — per renderlo più chiaro e coerente." },
      { titolo: "Riepiloghi pronti", testo: "Crea sintesi utili: andamenti nel tempo, totali per categoria, viste pronte da consultare o pubblicare." },
      { titolo: "Veloce anche quando è grande", testo: "Consigli pratici per gestire dataset voluminosi senza rallentamenti, e per servirli online in modo fluido." },
      { titolo: "Cambio formato con un clic", testo: "Converte un file da un formato all'altro (es. da foglio di calcolo a formato aperto, da una mappa all'altra) senza lavoro manuale." },
    ],
  },
  {
    n: "04",
    icon: "🔗",
    titolo: "Pubblicare bene, seguendo gli standard",
    perche:
      "Rendere il dato facile da trovare e riusare per tutti, seguendo le regole comuni europee e italiane per i dati aperti.",
    issue: 52,
    voci: [
      { titolo: "Controllo della scheda dati", testo: "Verifica che la descrizione del dato rispetti gli standard e suggerisce le correzioni mancanti." },
      { titolo: "Pacchetto pronto da pubblicare", testo: "Dato pulito + descrizione + licenza: tutto insieme, pronto da caricare sul portale." },
      { titolo: "I dati che “contano di più”", testo: "Verifica quali dei dataset più importanti (quelli indicati a livello europeo) l'ente già pubblica e quali mancano." },
      { titolo: "La licenza giusta", stato: "explore", testo: "Suggerisce la licenza aperta corretta, così chiunque può riusare il dato senza dubbi." },
    ],
  },
  {
    n: "05",
    icon: "🤖",
    titolo: "Più fonti collegate e processi che lavorano da soli",
    perche:
      "Collegare nuove banche dati pubbliche e far girare i controlli in automatico, così il lavoro ripetitivo lo fa la piattaforma.",
    issue: 53,
    voci: [
      { titolo: "Nuove fonti collegate", stato: "near", testo: "Più portali e banche dati pubbliche: appalti, bilanci degli enti, portali regionali, catasto e altro." },
      { titolo: "Funzioni usabili da altri strumenti", testo: "Le capacità della piattaforma rese disponibili anche a software e assistenti esterni." },
      { titolo: "Controlli automatici programmati", testo: "La piattaforma verifica da sola lo stato dei dati e avvisa quando qualcosa cambia o si rompe." },
    ],
  },
];

const PRINCIPI = [
  "Solo dati pubblici",
  "Fonti sempre citate",
  "Standard aperti europei e italiani",
  "Mai numeri inventati: se manca il dato, lo diciamo",
  "Codice aperto e gratuito",
];

export default function Page() {
  return (
    <div className="bg-bg-muted">
      {/* HERO */}
      <section className="bg-primary-900 text-white">
        <div className="container py-5">
          <div className="col-lg-9">
            <p
              className="mb-2 text-uppercase small fw-semibold"
              style={{ letterSpacing: "0.1em", opacity: 0.8 }}
            >
              Roadmap di sviluppo
            </p>
            <h1 className="display-5 fw-bold mb-3">Dove può crescere OpenData AI</h1>
            <p className="lead mb-0" style={{ opacity: 0.95 }}>
              Oggi la piattaforma permette di <strong>esplorare i dati pubblici parlando</strong>.
              Domani può aiutare gli enti a capire <strong>quanto bene li pubblicano</strong>, a{" "}
              <strong>migliorarne la qualità</strong> e a <strong>renderli più utili</strong> a
              tutti. Niente scadenze: sono direzioni, non promesse con una data — e ogni punto è
              tracciato pubblicamente su GitHub.
            </p>
          </div>
        </div>
      </section>

      {/* PUNTI */}
      <section className="container py-5">
        <div className="d-flex flex-wrap gap-3 mb-4 small text-muted">
          <span><span className={`badge ${STATO.now.cls} me-1`}>{STATO.now.label}</span> c&apos;è già, va ampliato</span>
          <span><span className={`badge ${STATO.wip.cls} me-1`}>{STATO.wip.label}</span> implementato, in fase di test</span>
          <span><span className={`badge ${STATO.near.cls} me-1`}>{STATO.near.label}</span> si costruisce su ciò che esiste</span>
          <span><span className={`badge ${STATO.explore.cls} me-1`}>{STATO.explore.label}</span> richiede studio e prove</span>
        </div>

        <div className="d-flex flex-column gap-4">
          {ROADMAP.map((p) => (
            <article key={p.n} className="card shadow-sm">
              <div className="card-body p-4">
                <div className="d-flex align-items-start gap-3 mb-2">
                  <span style={{ fontSize: "1.8rem", lineHeight: 1 }} aria-hidden>
                    {p.icon}
                  </span>
                  <div className="flex-grow-1">
                    <div className="text-muted small fw-semibold d-flex align-items-center gap-2" style={{ letterSpacing: "0.08em" }}>
                      PUNTO {p.n}
                      {p.wip && (
                        <span className="badge bg-warning-subtle text-warning-emphasis" style={{ letterSpacing: "normal" }}>
                          ● work in progress
                        </span>
                      )}
                    </div>
                    <h2 className="h4 mb-0">{p.titolo}</h2>
                  </div>
                  <a
                    href={`${ISSUES_BASE}/${p.issue}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-sm btn-outline-primary flex-shrink-0"
                  >
                    Segui su GitHub #{p.issue} →
                  </a>
                </div>
                <p className="text-muted">{p.perche}</p>
                <div className="row g-3">
                  {p.voci.map((v) => (
                    <div className="col-md-6" key={v.titolo}>
                      <div className="border rounded p-3 h-100">
                        <div className="fw-semibold mb-1">
                          {v.titolo}
                          {v.stato ? (
                            <span className={`badge ${STATO[v.stato].cls} ms-2 align-middle`}>
                              {STATO[v.stato].label}
                            </span>
                          ) : null}
                        </div>
                        <div className="small text-muted">{v.testo}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* PRINCIPI */}
      <section className="bg-white border-top border-bottom">
        <div className="container py-5">
          <h2 className="h4 mb-3">I principi che guidano ogni punto della roadmap</h2>
          <div className="d-flex flex-wrap gap-2">
            {PRINCIPI.map((c) => (
              <span key={c} className="badge bg-light text-dark border fw-normal px-3 py-2">
                {c}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="container py-5 text-center">
        <h2 className="h4 mb-3">Hai un&apos;idea o vuoi sostenere uno di questi sviluppi?</h2>
        <p className="text-muted mb-4">
          La roadmap è aperta: proponi un punto o commenta quelli esistenti su GitHub, oppure
          aiuta a realizzarli sostenendo il progetto.
        </p>
        <div className="d-flex flex-wrap justify-content-center gap-3">
          <a
            href={`${ISSUES_BASE}?q=is%3Aissue+label%3Aroadmap`}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-primary btn-lg"
          >
            Proponi un punto su GitHub
          </a>
          <Link href="/sostieni" className="btn btn-outline-secondary btn-lg">
            Sostieni lo sviluppo
          </Link>
        </div>
      </section>
    </div>
  );
}
