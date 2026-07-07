import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Roadmap — OpenData AI",
  description:
    "La roadmap di sviluppo di OpenData AI: dove cresce la piattaforma da qui. Il Data Quality Lab, la maturità open data e il monitoraggio automatico sono già attivi; restano aperti gli avvisi di maturità nel tempo, i dataset ad alto valore, nuove fonti collegate, nuove lenti per il territorio e la riconciliazione tra mappa e stato reale del suolo. Niente scadenze, solo direzioni utili.",
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
    icon: "📊",
    titolo: "Avvisi di maturità nel tempo",
    perche:
      "La pagella in quattro aree, il piano su misura per salire di livello e il confronto con enti simili sono già attivi. Resta l'ultimo passo: avvisare in automatico quando la maturità di un ente peggiora, non solo mostrarne l'andamento.",
    issue: 103,
    voci: [
      { titolo: "Regressioni di maturità", stato: "explore", testo: "Confronta la pagella tra una valutazione e la successiva e segnala i cali di punteggio o di livello, appena succedono — si appoggia all'agente di monitoraggio automatico già attivo (freshness/qualità/link). Issue #103." },
    ],
  },
  {
    n: "02",
    icon: "⚙️",
    titolo: "Convertitori avanzati per i formati più diffusi",
    perche:
      "Mettere ordine in una tabella, i riepiloghi pronti, i consigli per i file grandi e la conversione in mappa (GeoJSON) sono già attivi nella pagina Qualità. Resta da leggere i formati più \"pesanti\": fogli Excel e mappe Shapefile.",
    issue: 101,
    voci: [
      { titolo: "Excel e Shapefile", stato: "explore", testo: "Convertitori dedicati per i formati più diffusi negli enti ma non ancora supportati: fogli Excel (XLSX→CSV), mappe Shapefile (→GeoJSON) ed esportazione in formato compresso (Parquet). Issue #101." },
    ],
  },
  {
    n: "03",
    icon: "🔗",
    titolo: "I dati che contano di più, dataset per dataset",
    perche:
      "Il controllo della scheda descrittiva (in due standard: DCAT-AP_IT e schema.org), il pacchetto pronto da pubblicare e il controllo della licenza sono già attivi nella pagina Qualità. Resta da capire, file per file, quali dataset rientrano tra quelli ad alto valore per l'Europa.",
    issue: 102,
    voci: [
      { titolo: "High-Value Dataset per singolo file", stato: "explore", testo: "Oggi la copertura degli High-Value Dataset UE si vede a livello di ente, nella pagina Maturità. Resta da stimarla anche per il singolo file caricato in Qualità, con priorità di pubblicazione. Issue #102." },
    ],
  },
  {
    n: "04",
    icon: "🤖",
    titolo: "Più fonti collegate e un accesso unico per gli assistenti",
    perche:
      "I connettori OpenDataSoft e Socrata, le funzioni richiamabili da altri programmi via API e il monitoraggio automatico (aggiornamento, qualità, link) sono già attivi. Restano da collegare altre banche dati pubbliche e un punto d'accesso unico per gli assistenti esterni.",
    issue: 147,
    voci: [
      { titolo: "Nuovi connettori", stato: "explore", testo: "Il connettore Socrata (portali open data USA/EU su piattaforma Socrata) è attivo come server MCP standalone — #98. Gli appalti ANAC sono già accessibili come portale CKAN (dataset e metadati) senza connettore dedicato — #99; la ricerca puntuale per CIG/ente non è costruibile, richiede accreditamento istituzionale PDND. I bilanci comunali BDAP/SIOPE (entrate/spese per titolo, dato corrente) sono anch'essi attivi come server MCP standalone — #100. Resta da definire il catasto #147 (per ora senza una fonte open data generalista ovvia)." },
      { titolo: "Tutte le funzioni come strumenti per altri assistenti (MCP)", stato: "near", testo: "Un connettore unico che mette le quattro modalità — Esplora, Territorio, Maturità e Qualità — a disposizione di assistenti e agenti esterni (es. OpenClaw, Claude Desktop) come strumenti pronti all'uso, riusando l'orchestrazione e l'accesso già esistenti. Issue #131." },
    ],
  },
  {
    n: "05",
    icon: "🗺️",
    titolo: "Leggere un comune da più punti di vista",
    perche:
      "L'analisi del territorio legge un comune attraverso “lenti”: incroci tra dati pubblici e ciò che è stato fatto, per far emergere punti di forza, bisogni e idee. Oggi sono attive dieci lenti; il passo avanti è aggiungerne di nuove, sempre con dati comunali e fonti citate.",
    issue: 94,
    voci: [
      { titolo: "Le 10 lenti di oggi", stato: "now", testo: "Commercio, Turismo & cultura, Lavoro, Trasporti & mobilità, Welfare, Istruzione, Casa & abitazioni, Reddito, Ambiente e Sanità: tutte a livello di comune, con le fonti sempre indicate." },
      { titolo: "Finanza del comune", stato: "explore", testo: "Il blocco sui dati veri (entrate/spese) è superato: BDAP espone i movimenti SIOPE cumulati per titolo di bilancio, interrogabili per comune senza download bulk — attivo come server MCP standalone (#100). Resta da costruire la lente vera e propria in /programma (connettore già pronto, manca l'iniezione nell'aggregatore). Issue #92." },
      { titolo: "Connettività digitale", stato: "explore", testo: "Verificato: né Infratel né AGCOM pubblicano la copertura fibra/FWA per comune come dataset aperto — solo mappe interattive senza esportazione, o un endpoint non ufficiale che copre solo lo stato dei cantieri, non le percentuali di copertura. Issue #93." },
    ],
  },
  {
    n: "06",
    icon: "🏗️",
    titolo: "Dal dato alla realtà: cosa c'è davvero su quel terreno",
    perche:
      "Una mappa dice che un'area è “zona industriale” o “parco”, ma spesso la realtà è diversa: un capannone dismesso, un terreno agricolo, un'area privata o sotto vincolo. La piattaforma incrocia la mappa con le fonti ufficiali per capire lo stato reale del suolo — dichiarando sempre quanto è sicura ogni conclusione e cosa resta da verificare. Mai dare per pubblica una proprietà che non lo è.",
    issue: 127,
    voci: [
      { titolo: "Mappa contro realtà", stato: "near", testo: "Per ogni area, confronta ciò che è mappato (OpenStreetMap) con le fonti ufficiali già collegate (rischio idrogeologico ISPRA, progetti finanziati) e dice lo stato reale: attiva, dismessa, vincolata, da bonificare. Ogni conclusione ha un livello di sicurezza — alta, media, bassa — e i campi non verificabili restano esplicitamente “da verificare”. Issue #127." },
      { titolo: "Più fonti ufficiali, più certezza", stato: "explore", testo: "Aggiunge fonti consultabili dal vivo che alzano la sicurezza dell'analisi: siti contaminati (SIN-SIR), vincoli del paesaggio (PPTR), consumo di suolo (ISPRA). Solo fonti realmente interrogabili, nessun documento caricato a mano. Issue #128." },
      { titolo: "Il piano urbanistico come dato aperto", stato: "explore", testo: "Per sapere se un'area è davvero edificabile serve il piano urbanistico (PUG/PRG). La piattaforma lo consulta quando il comune lo pubblica come dato aperto; se manca, non lo inventa: lo segnala come dato importante da aprire. Il piano diventa parte della politica open data del comune. Issue #129." },
      { titolo: "Zone industriali e parchi", stato: "explore", testo: "Due letture pratiche: recuperare le aree produttive dismesse prima di consumare nuovo suolo, e misurare se i parchi sono davvero verde pubblico raggiungibile a piedi. Con il consiglio sullo strumento giusto per agire. Issue #130." },
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
              Oggi la piattaforma permette di <strong>esplorare i dati pubblici parlando</strong>,
              misura <strong>quanto bene un ente li pubblica</strong>, aiuta a{" "}
              <strong>migliorarne la qualità</strong> e <strong>controlla da sola</strong> che
              tutto resti in ordine nel tempo. Da qui si cresce ancora: nuove fonti, nuovi
              controlli, nuove lenti per leggere il territorio. Niente scadenze: sono direzioni,
              non promesse con una data — e ogni punto è tracciato pubblicamente su GitHub.
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
