import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Roadmap — OpenData AI",
  description:
    "La roadmap di sviluppo di OpenData AI: dove cresce la piattaforma. Sette punti — qualità del dato, maturità open data, ottimizzazione, pubblicazione secondo gli standard, nuove fonti e automazione, nuove lenti per l'analisi del territorio e la riconciliazione tra mappa e stato reale del suolo. Niente scadenze, solo direzioni utili.",
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
    wip: true,
    voci: [
      { titolo: "Pagella in quattro aree", stato: "now", testo: "Quanto è aperto e ben tenuto il patrimonio dati dell'ente. C'è già: va resa più “azionabile”." },
      { titolo: "Le mosse che contano di più", stato: "wip", testo: "Le azioni che migliorano di più la situazione, separate tra quelle facili e rapide (correzioni sui dati già pubblicati) e quelle più strategiche (pubblicare nuovi dati). Disponibile, in fase di test." },
      { titolo: "Un percorso su misura", stato: "wip", testo: "Quanti punti mancano al livello successivo e qual è il “collo di bottiglia” su cui conviene concentrarsi: una strada chiara verso il passo successivo. Disponibile, in fase di test." },
      { titolo: "Confronto con enti simili", stato: "wip", testo: "Come si posiziona rispetto agli enti dello stesso tipo: posizione nel gruppo e confronto, area per area, con la mediana dei pari. Disponibile, in fase di test." },
      { titolo: "Controllo nel tempo e avvisi", stato: "explore", testo: "Segnala dati non aggiornati, collegamenti che non funzionano e peggioramenti, appena succedono. Tracciata nelle issue #103 (avvisi di maturità) e #88 (monitoraggio schedulato)." },
    ],
  },
  {
    n: "03",
    icon: "⚙️",
    titolo: "Rendere il dato più ordinato e veloce da usare",
    perche:
      "Trasformare un elenco disordinato in qualcosa di ben organizzato e facile da consultare, anche quando i dati sono davvero tanti.",
    issue: 51,
    wip: true,
    voci: [
      { titolo: "Mettere ordine", stato: "wip", testo: "Dal file ricava una tabella ben organizzata: tipi delle colonne, chiave primaria e indici utili, con il comando pronto da eseguire (CREATE TABLE). Disponibile, in fase di test." },
      { titolo: "Riepiloghi pronti", stato: "wip", testo: "Crea sintesi utili dal file: statistiche delle colonne numeriche, totali per categoria e andamenti nel tempo, pronti da consultare o pubblicare. Disponibile, in fase di test." },
      { titolo: "Veloce anche quando è grande", stato: "wip", testo: "In base a dimensione e contenuto del file, suggerisce come tenerlo veloce: formato compresso (Parquet), indici, suddivisione e pubblicazione via API. Disponibile, in fase di test." },
      { titolo: "Cambio formato con un clic", stato: "wip", testo: "Trasforma una tabella con coordinate in una mappa (GeoJSON) pronta da pubblicare, riconoscendo da solo le colonne di latitudine e longitudine. Disponibile, in fase di test. Convertitori avanzati (Excel, Shapefile, Parquet) tracciati nell'issue #101." },
    ],
  },
  {
    n: "04",
    icon: "🔗",
    titolo: "Pubblicare bene, seguendo gli standard",
    perche:
      "Rendere il dato facile da trovare e riusare per tutti, seguendo le regole comuni europee e italiane per i dati aperti.",
    issue: 52,
    wip: true,
    voci: [
      { titolo: "Controllo della scheda dati", stato: "wip", testo: "Verifica che la scheda del dato rispetti lo standard europeo (DCAT-AP_IT), segnala i campi obbligatori mancanti e calcola un punteggio FAIR (trovabile, accessibile, interoperabile, riutilizzabile). Disponibile, in fase di test." },
      { titolo: "Pacchetto pronto da pubblicare", stato: "wip", testo: "Scarichi in un clic un unico pacchetto (.zip) con dato pulito, scheda dei metadati, licenza e una guida con i passi per pubblicarlo sul portale. Disponibile, in fase di test." },
      { titolo: "I dati che “contano di più”", stato: "explore", testo: "Verifica quali dei dataset più importanti (quelli indicati a livello europeo) l'ente già pubblica e quali mancano; a livello di singolo file, stima se rientra tra gli High-Value Dataset UE. Tracciata nell'issue #102." },
      { titolo: "La licenza giusta", stato: "wip", testo: "Riconosce se la licenza dichiarata è davvero aperta e, in caso contrario, suggerisce quella corretta (es. CC-BY-4.0). Disponibile, in fase di test." },
    ],
  },
  {
    n: "05",
    icon: "🤖",
    titolo: "Più fonti collegate e processi che lavorano da soli",
    perche:
      "Collegare nuove banche dati pubbliche e far girare i controlli in automatico, così il lavoro ripetitivo lo fa la piattaforma.",
    issue: 53,
    wip: true,
    voci: [
      { titolo: "Nuove fonti collegate", stato: "wip", testo: "Più portali e banche dati pubbliche: aggiunto il connettore per i portali OpenDataSoft (molti enti regionali e comunali), già collegato alla ricerca. Prossimi connettori tracciati: Socrata #98, ANAC appalti #99, BDAP bilanci #100." },
      { titolo: "Funzioni usabili da altri strumenti", stato: "wip", testo: "Le capacità della piattaforma rese disponibili ad altri software e assistenti: il Data Quality Lab (diagnosi, schema, riepiloghi, validazione DCAT-AP_IT, pacchetto di pubblicazione) è ora richiamabile da agenti esterni via API. Disponibile, in fase di test." },
      { titolo: "Tutte le funzioni come strumenti per altri assistenti (MCP)", stato: "near", testo: "Un connettore unico che mette le quattro modalità — Esplora, Territorio, Maturità e Qualità — a disposizione di assistenti e agenti esterni (es. OpenClaw, Claude Desktop) come strumenti pronti all'uso, riusando l'orchestrazione e l'accesso già esistenti. Issue #131." },
      { titolo: "Controlli automatici programmati", stato: "explore", testo: "La piattaforma verifica da sola lo stato dei dati (aggiornamento, qualità, link rotti) e avvisa quando qualcosa cambia o si rompe. Progettata in dettaglio (issue #88), da sviluppare nelle prossime sessioni." },
    ],
  },
  {
    n: "06",
    icon: "🗺️",
    titolo: "Leggere un comune da più punti di vista",
    perche:
      "L'analisi del territorio legge un comune attraverso “lenti”: incroci tra dati pubblici e ciò che è stato fatto, per far emergere punti di forza, bisogni e idee. Oggi sono attive otto lenti; il passo avanti è aggiungerne di nuove, sempre con dati comunali e fonti citate.",
    issue: 94,
    voci: [
      { titolo: "Le 8 lenti di oggi", stato: "now", testo: "Commercio, Turismo & cultura, Lavoro, Trasporti & mobilità, Welfare, Istruzione, Ambiente e Sanità: tutte a livello di comune, con le fonti sempre indicate." },
      { titolo: "Casa e abitazioni", stato: "near", testo: "Affollamento, case non occupate, proprietà o affitto: le condizioni abitative del comune, dal Censimento ISTAT." },
      { titolo: "Reddito e benessere economico", stato: "explore", testo: "Reddito medio dichiarato e fasce di reddito per comune (dati del Ministero dell'Economia): un'àncora socio-economica accanto a lavoro e welfare." },
      { titolo: "Finanza del comune", stato: "explore", testo: "I conti del comune — entrate, spese, capacità di spesa — da SIOPE e dalla banca dati dei bilanci pubblici: trasparenza sui soldi pubblici." },
      { titolo: "Connettività digitale", stato: "explore", testo: "Copertura della rete veloce (fibra) nel comune: il divario digitale, da verificare sulla disponibilità dei dati aperti." },
    ],
  },
  {
    n: "07",
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
