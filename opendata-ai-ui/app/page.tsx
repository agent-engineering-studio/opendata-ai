import type { Metadata } from "next";
import type { CSSProperties } from "react";
import Link from "next/link";
import { AuthAwareCTAs } from "@/components/AuthAwareCTAs";
import { LandingReveal } from "@/components/LandingReveal";

export const metadata: Metadata = {
  title: "OpenData AI — dal patrimonio di dati al valore per il territorio",
  description:
    "Misura la maturità del patrimonio di open data di un comune, scopri dove migliorare e trasformalo in progetti concreti per il territorio. Uno strumento per diffondere la cultura del dato nelle PA, al servizio del bene comune.",
};

/* Stili firma riusati nelle sezioni (token @theme + valori esatti del design). */
const HERO_BG = "linear-gradient(160deg,#0E2233 0%,#0A1826 100%)";
const BRAND_BG = "linear-gradient(135deg,#1B6FE3,#0FA3A3)";

const eyebrow: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: "0.16em",
  textTransform: "uppercase",
  color: "var(--color-primary)",
};
const h2: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontWeight: 700,
  fontSize: "clamp(2rem,3.6vw,2.9rem)",
  lineHeight: 1.08,
  letterSpacing: "-0.02em",
  color: "var(--color-primary-900)",
  margin: "16px 0 14px",
};
const lead: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: 18,
  lineHeight: 1.6,
  color: "var(--color-text-muted)",
  margin: 0,
};
const cardBase: CSSProperties = {
  position: "relative",
  background: "#fff",
  border: "1px solid var(--color-border)",
  borderRadius: 16,
  padding: 26,
  boxShadow: "0 1px 3px rgba(14,34,51,.06)",
  height: "100%",
};
// Sotto-titolo delle sotto-sezioni di "Come funziona".
const comeSub: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontWeight: 700,
  fontSize: "clamp(1.4rem,2.4vw,1.9rem)",
  lineHeight: 1.15,
  letterSpacing: "-0.01em",
  color: "var(--color-primary-900)",
  margin: "44px 0 12px",
};

/* ── Icone line-style (stroke 2px, cap arrotondati). Niente emoji. ── */
function Icon({
  path,
  stroke,
  size = 22,
}: {
  path: string;
  stroke: string;
  size?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={stroke}
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      dangerouslySetInnerHTML={{ __html: path }}
    />
  );
}

const ICON = {
  bars: '<path d="M12 20v-6M6 20v-3M18 20v-9M3 21h18M4 7l6-3 5 3 4-2"/>',
  trend: '<path d="M3 3v18h18M7 14l4-4 3 3 5-6"/>',
  books:
    '<path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2zM22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z"/>',
  people:
    '<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8zM23 21v-2a4 4 0 00-3-3.87M16 3.13A4 4 0 0116 11"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  building:
    '<path d="M3 21h18M5 21V7l8-4v18M19 21V11l-6-4M9 9v.01M9 12v.01M9 15v.01M9 18v.01"/>',
  code: '<path d="M8 9l-4 3 4 3M16 9l4 3-4 3M14 4l-4 16"/>',
  arrow: '<path d="M5 12h14M12 5l7 7-7 7"/>',
};

export default function Page() {
  return (
    <div style={{ background: "#fff", overflow: "hidden" }}>
      <LandingReveal />

      {/* ============ HERO ============ */}
      <section
        id="top"
        style={{ position: "relative", background: HERO_BG, color: "#fff", overflow: "hidden" }}
      >
        {/* Marchio gigante drift in filigrana */}
        <div
          aria-hidden="true"
          className="od-drift d-none d-md-block"
          style={{ position: "absolute", right: -120, top: -80, width: 560, height: 560, opacity: 0.5, pointerEvents: "none" }}
        >
          <svg width="560" height="560" viewBox="0 0 48 48" fill="none">
            <circle cx="24" cy="24" r="15" stroke="#1B6FE3" strokeWidth="2" strokeLinecap="round" strokeDasharray="71 26" transform="rotate(-58 24 24)" opacity=".35" />
            <circle cx="32.8" cy="17.4" r="2.5" fill="#0FA3A3" opacity=".4" />
          </svg>
        </div>
        {/* Glow radiale teal */}
        <div
          aria-hidden="true"
          style={{ position: "absolute", inset: 0, background: "radial-gradient(900px 480px at 80% -10%,rgba(15,163,163,.28),transparent 60%)" }}
        />
        <div className="container" style={{ position: "relative" }}>
          <div className="row align-items-center g-5" style={{ paddingTop: 84, paddingBottom: 92 }}>
            {/* Colonna testo */}
            <div className="col-lg-6" data-reveal>
              <span
                className="d-inline-flex align-items-center gap-2"
                style={{ padding: "7px 14px", borderRadius: 999, border: "1px solid rgba(255,255,255,.18)", background: "rgba(255,255,255,.06)", ...eyebrow, color: "#AFC0CE" }}
              >
                <span className="od-pulse" style={{ width: 7, height: 7, borderRadius: "50%", background: "#1FA971", boxShadow: "0 0 0 4px rgba(31,169,113,.22)" }} />
                Open data · maturità · valore
              </span>
              <h1
                style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "clamp(2.7rem,4.7vw,4.5rem)", lineHeight: 1.02, letterSpacing: "-0.02em", color: "#fff", margin: "22px 0 0" }}
              >
                Dal patrimonio di dati
                <br />
                al{" "}
                <span className="text-gradient-brand" style={{ background: "linear-gradient(100deg,#4D9BFF,#16C4C4 55%,#2BD68C)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
                  valore per il territorio
                </span>
              </h1>
              <p style={{ maxWidth: "50ch", margin: "26px 0 0", fontFamily: "var(--font-sans)", fontSize: 18.5, lineHeight: 1.6, color: "#AFC0CE" }}>
                OpenData AI misura la <strong style={{ color: "#fff", fontWeight: 600 }}>maturità</strong> degli open data di un comune, mostra <strong style={{ color: "#fff", fontWeight: 600 }}>dove migliorare</strong> e li trasforma in <strong style={{ color: "#fff", fontWeight: 600 }}>progetti concreti</strong> — leggendo solo fonti ufficiali. Cultura del dato nella PA, al servizio del bene comune.
              </p>
              <div className="d-flex flex-wrap gap-3" style={{ marginTop: 34 }}>
                <AuthAwareCTAs variant="hero" />
                <a
                  href="#come"
                  className="d-inline-flex align-items-center gap-2"
                  style={{ padding: "15px 26px", borderRadius: 999, border: "1.5px solid rgba(255,255,255,.28)", color: "#fff", textDecoration: "none", fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: 17 }}
                >
                  Guarda come funziona
                  <Icon path={ICON.arrow} stroke="currentColor" size={17} />
                </a>
              </div>
              <div className="d-flex flex-wrap align-items-center gap-2" style={{ marginTop: 30, fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: 12.5, color: "#7E8F9C" }}>
                <span style={{ letterSpacing: "0.06em" }}>FONTI UFFICIALI</span>
                <span style={{ opacity: 0.4 }}>·</span><span>ISTAT</span>
                <span style={{ opacity: 0.4 }}>·</span><span>OpenCoesione</span>
                <span style={{ opacity: 0.4 }}>·</span><span>OpenStreetMap</span>
                <span style={{ opacity: 0.4 }}>·</span><span>CKAN dati.gov.it</span>
              </div>
            </div>

            {/* Colonna pannello chat */}
            <div className="col-lg-6" data-reveal data-delay="120">
              <div style={{ background: "#fff", borderRadius: 18, boxShadow: "0 24px 60px rgba(0,0,0,.42)", overflow: "hidden", color: "#42535F" }}>
                {/* Barra finestra */}
                <div className="d-flex align-items-center gap-2" style={{ padding: "14px 18px", borderBottom: "1px solid #EDF0F3", background: "#F6F8FA" }}>
                  <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#E0817A" }} />
                  <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#E3C06A" }} />
                  <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#88C07A" }} />
                  <span style={{ marginLeft: 8, fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: 12.5, color: "#7E8F9C" }}>opendata-ai · chat</span>
                </div>
                <div className="d-flex flex-column" style={{ padding: "20px 20px 22px", gap: 13 }}>
                  {/* Bolla utente */}
                  <div style={{ alignSelf: "flex-end", maxWidth: "88%", background: BRAND_BG, color: "#fff", padding: "11px 15px", borderRadius: "14px 14px 4px 14px", fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: 14, lineHeight: 1.5 }}>
                    Maturità degli open data del Comune di Gioia del Colle
                  </div>
                  {/* Pill sorgenti */}
                  <div className="d-flex flex-wrap" style={{ gap: 7 }}>
                    <SourcePill bg="#E7F0FD" color="#1959B8" check="#1B6FE3" label="CKAN · 7 dataset" />
                    <SourcePill bg="#E1F4F4" color="#0B7878" check="#0FA3A3" label="ISTAT · 2 cubi SDMX" />
                    <SourcePill bg="#E4F5EC" color="#147A52" check="#1FA971" label="OpenCoesione · 18" />
                  </div>
                  {/* Risposta agente */}
                  <div className="d-flex align-items-start" style={{ gap: 11 }}>
                    <span style={{ flex: "none", width: 28, height: 28, borderRadius: 8, background: BRAND_BG, display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
                      <svg width="16" height="16" viewBox="0 0 48 48" fill="none">
                        <circle cx="24" cy="24" r="15" stroke="#fff" strokeWidth="4.5" strokeLinecap="round" strokeDasharray="71 26" transform="rotate(-58 24 24)" />
                        <circle cx="32.8" cy="17.4" r="4" fill="#7BE7C4" />
                      </svg>
                    </span>
                    <div style={{ fontFamily: "var(--font-sans)", fontSize: 13.5, lineHeight: 1.55, color: "#42535F" }}>
                      Il patrimonio open data del comune è di <strong style={{ color: "#0E2233" }}>maturità buona</strong>: 23 dataset, ma 3 lacune chiave su mobilità e bilanci.
                      <span className="od-blink" style={{ display: "inline-block", width: 8, height: 15, background: "#1B6FE3", marginLeft: 2, verticalAlign: -2 }} />
                    </div>
                  </div>
                  {/* Mini-card risultato con donut */}
                  <div className="d-flex align-items-center" style={{ gap: 16, marginTop: 2, padding: 15, border: "1px solid #EDF0F3", borderRadius: 14, background: "#F6F8FA" }}>
                    <svg width="84" height="84" viewBox="0 0 120 120" style={{ flex: "none" }}>
                      <defs>
                        <linearGradient id="donutg" x1="0" y1="0" x2="1" y2="1">
                          <stop offset="0" stopColor="#1B6FE3" />
                          <stop offset="1" stopColor="#0FA3A3" />
                        </linearGradient>
                      </defs>
                      <circle cx="60" cy="60" r="52" fill="none" stroke="#E1E6EB" strokeWidth="12" />
                      <circle className="od-dash" cx="60" cy="60" r="52" fill="none" stroke="url(#donutg)" strokeWidth="12" strokeLinecap="round" strokeDasharray="327" strokeDashoffset="124" transform="rotate(-90 60 60)" />
                      <text x="60" y="58" textAnchor="middle" fontFamily="Space Grotesk,sans-serif" fontWeight="700" fontSize="30" fill="#0E2233">62</text>
                      <text x="60" y="78" textAnchor="middle" fontFamily="Titillium Web,sans-serif" fontWeight="600" fontSize="12" fill="#7E8F9C">/ 100</text>
                    </svg>
                    <div>
                      <div style={{ fontFamily: "var(--font-sans)", fontWeight: 700, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: "#1B6FE3" }}>Indice di maturità</div>
                      <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 19, lineHeight: 1.2, color: "#0E2233", marginTop: 6 }}>Buono · in crescita</div>
                      <div style={{ fontFamily: "var(--font-sans)", fontSize: 13, lineHeight: 1.4, color: "#7E8F9C", marginTop: 3 }}>3 gap da colmare · +14 in 12 mesi</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ============ TRUST STRIP ============ */}
      <section style={{ background: "#fff", borderBottom: "1px solid #EDF0F3" }}>
        <div className="container">
          <div className="row g-4" style={{ paddingTop: 38, paddingBottom: 38 }}>
            <Stat value="4" label="Fonti ufficiali in parallelo" delay={0} />
            <Stat value="3" label="Superfici · REST · MCP · A2A" delay={80} />
            <Stat value="100%" label="Risposte con fonte citata" delay={160} gradient />
            <Stat value="0" label="Punteggi inventati senza dati" delay={240} />
          </div>
        </div>
      </section>

      {/* ============ IL PERCORSO ============ */}
      <section id="percorso" style={{ background: "var(--color-bg-muted)", padding: "96px 0", scrollMarginTop: 80 }}>
        <div className="container">
          <div data-reveal style={{ maxWidth: 680 }}>
            <div style={eyebrow}>Il percorso</div>
            <h2 style={h2}>Dalla maturità al bene comune</h2>
            <p style={lead}>
              Gli open data sono un patrimonio pubblico spesso sottoutilizzato. OpenData AI accompagna le PA in quattro passi: misurare, valorizzare, diffondere cultura e generare servizi.
            </p>
          </div>

          <div className="row g-3" style={{ marginTop: 34 }}>
            <PercorsoCard n="01" tag="Maturità" tagColor="#1B6FE3" iconBg="#E7F0FD" icon={ICON.bars} iconStroke="#1B6FE3" title="Misura il patrimonio" body="Valuta quanto i dati sono completi, aggiornati e riusabili — e indica dove intervenire." delay={0} />
            <PercorsoCard n="02" tag="Valore" tagColor="#0B8E8E" iconBg="#E1F4F4" icon={ICON.trend} iconStroke="#0FA3A3" title="Progetti concreti" body="Lenti su commercio, turismo, lavoro e mobilità individuano gap, potenzialità e idee." delay={90} />
            <PercorsoCard n="03" tag="Cultura" tagColor="#147A52" iconBg="#E4F5EC" icon={ICON.books} iconStroke="#1FA971" title="Cultura del dato" body="Ogni analisi cita la fonte ufficiale: mostra perché un dato di qualità produce servizi migliori." delay={180} />
            {/* Card apex gradiente */}
            <div className="col-md-6 col-lg-3" data-reveal data-delay="270">
              <div className="od-card" style={{ ...cardBase, background: "linear-gradient(150deg,#1B6FE3,#0FA3A3)", border: 0, boxShadow: "0 12px 30px rgba(27,111,227,.32)" }}>
                <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 13, color: "rgba(255,255,255,.5)" }}>04</div>
                <div className="d-flex align-items-center justify-content-center" style={{ margin: "16px 0 10px", width: 42, height: 42, borderRadius: 11, background: "rgba(255,255,255,.18)" }}>
                  <Icon path={ICON.people} stroke="#fff" />
                </div>
                <div style={{ fontFamily: "var(--font-sans)", fontWeight: 700, fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase", color: "rgba(255,255,255,.85)" }}>Bene comune</div>
                <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: 18, lineHeight: 1.25, color: "#fff", margin: "8px 0" }}>Servizi per la comunità</h3>
                <p style={{ fontFamily: "var(--font-sans)", fontSize: 14, lineHeight: 1.55, color: "rgba(255,255,255,.92)", margin: 0 }}>Dati pubblici che diventano servizi per cittadini e territorio. Open source, per il bene comune.</p>
              </div>
            </div>
          </div>

          {/* Callout "Non è una pagella" */}
          <div data-reveal className="d-flex align-items-start gap-3" style={{ marginTop: 26, background: "#fff", border: "1px solid var(--color-border)", borderRadius: 16, padding: "26px 30px", position: "relative", overflow: "hidden" }}>
            <span style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 4, background: "linear-gradient(180deg,#1B6FE3,#0FA3A3)" }} />
            <span className="flex-shrink-0 d-flex align-items-center justify-content-center" style={{ width: 44, height: 44, borderRadius: 12, background: "#E7F0FD" }}>
              <Icon path={ICON.shield} stroke="#1B6FE3" />
            </span>
            <div>
              <h4 style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: 18, lineHeight: 1.3, color: "#0E2233", margin: "0 0 6px" }}>Non è una pagella sulle PA</h4>
              <p style={{ fontFamily: "var(--font-sans)", fontSize: 15, lineHeight: 1.6, color: "var(--color-text-muted)", margin: 0, maxWidth: "80ch" }}>
                È una <strong style={{ color: "#0E2233" }}>bussola che mostra dove migliorare</strong> per valorizzare il patrimonio pubblico. Sotto la soglia minima di dati l&apos;analisi dichiara <em style={{ color: "#1B6FE3", fontStyle: "normal", fontWeight: 600 }}>&ldquo;dato insufficiente&rdquo;</em> invece di assegnare punteggi fuorvianti.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ============ COME FUNZIONA — fan-out ============ */}
      <section id="come" style={{ background: "#fff", padding: "96px 0", scrollMarginTop: 80 }}>
        <div className="container">
          <div data-reveal className="text-center mx-auto" style={{ maxWidth: 760 }}>
            <div style={eyebrow}>Come funziona</div>
            <h2 style={h2}>Una domanda, tanti specialisti, una risposta con le fonti</h2>
            <p style={lead}>
              Una sola domanda in linguaggio naturale viene smistata <strong>in parallelo</strong> a più
              specialisti: ognuno è un agente che interroga, tramite il suo <strong>server MCP</strong>,
              una fonte ufficiale diversa. Un agente di <strong>sintesi</strong> fonde le risposte in una
              narrativa coerente in italiano, citando ogni risorsa con la sua origine. Niente numeri
              inventati: ogni dato proviene da una chiamata realmente eseguita in quel momento.
            </p>
          </div>

          {/* Diagramma fan-out */}
          <div data-reveal className="mx-auto" style={{ marginTop: 52, maxWidth: 1040 }}>
            <FanOut />
          </div>

          {/* Le fonti — un server MCP per ciascuna */}
          <h3 style={comeSub}>Le fonti: un server MCP per ciascuna</h3>
          <p style={{ ...lead, fontSize: 15, marginTop: -4, marginBottom: 18, maxWidth: "70ch" }}>
            Ogni fonte è incapsulata in un piccolo server <strong>MCP</strong> (Model Context Protocol)
            componibile: lo stesso mattone funziona nel backend e in qualsiasi client MCP (Claude
            Desktop, Cursor…). Le fonti attive dipendono dalla domanda.
          </p>
          <div className="row g-3">
            <SpecCard tag="CKAN" tagBg="#E7F0FD" tagColor="#1959B8" title="Cataloghi open" body={<>Qualunque portale CKAN-compatibile. Default <code style={{ fontSize: 12, color: "#1B6FE3" }}>dati.gov.it</code>, override per portale regionale/municipale.</>} delay={0} />
            <SpecCard tag="SDMX 2.1" tagBg="#E1F4F4" tagColor="#0B7878" title="Statistiche ufficiali" body="Una sola interfaccia per ISTAT, Eurostat e OCSE: dataflow, codelist e osservazioni normalizzate in CSV." delay={60} />
            <SpecCard tag="OpenCoesione" tagBg="#E4F5EC" tagColor="#147A52" title="Spesa di coesione" body="Progetti finanziati sul territorio: quanto finanziato vs speso, spend ratio e capacità di realizzazione." delay={120} />
            <SpecCard tag="OSM" tagBg="#E4F5EC" tagColor="#147A52" title="Accessibilità + mappe" body="Geocoding, POI, routing e profili di zona; GeoJSON, KML e Shapefile resi su mappa Leaflet." delay={180} />
            <SpecCard tag="ISPRA" tagBg="#FDE9D6" tagColor="#A35B12" title="Vincoli ambientali" body="Pericolosità frane e alluvioni ed esposti per comune (IdroGEO): vincoli di pianificazione, non giudizi." delay={0} />
            <SpecCard tag="Web" tagBg="#EEF1F4" tagColor="#5B6B7B" title="Iniziative analoghe" body="Ricerca web self-hosted (SearXNG) per best practice di altri enti — la lente del marketing territoriale." delay={60} />
            <SpecCard tag="Memoria" tagBg="#F3E8FD" tagColor="#7C3AED" title="Riuso delle analisi" body="Le analisi già prodotte vengono richiamate per non rifare lavoro — memoria di lavoro, non fonte ufficiale." delay={120} />
            <SpecCard tag="Sintesi" tagBg="#E7EEFE" tagColor="#1B6FE3" title="Risposta unica" body="Un LLM fonde le risposte in italiano, citando ogni risorsa con la fonte di origine." delay={180} rail />
          </div>

          {/* Maturità ODM 2025 */}
          <div data-reveal className="od-card" style={{ ...cardBase, marginTop: 40, padding: "30px 32px", overflow: "hidden" }}>
            <span style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 4, background: "linear-gradient(180deg,#1B6FE3,#0FA3A3)" }} />
            <h3 style={{ ...comeSub, marginTop: 0 }}>Maturità degli open data — modello ODM 2025</h3>
            <p style={{ ...lead, fontSize: 15, maxWidth: "75ch" }}>
              Oltre a cercare i dati, OpenData AI ne misura la <strong>maturità</strong>: raccoglie il
              patrimonio di un ente e lo valuta su <strong>quattro dimensioni</strong>, restituendo un
              punteggio 0–100, un livello e raccomandazioni concrete su dove intervenire.
            </p>
            <div className="row g-3" style={{ marginTop: 8 }}>
              <DimCard n="Policy" desc="Licenze aperte e metadati DCAT-AP_IT: la base legale per riusare e trovare i dati." />
              <DimCard n="Portale" desc="Quanti dataset l'ente espone e quanto sono indicizzati e accessibili." />
              <DimCard n="Qualità" desc="Formati aperti e machine-readable, aggiornamento regolare, completezza." />
              <DimCard n="Impatto" desc="Dataset ad alto valore (HVD) e domanda di riuso soddisfatta." />
            </div>
            <p style={{ ...lead, fontSize: 14, marginTop: 16, marginBottom: 0, color: "var(--color-text-faint)" }}>
              Quattro livelli crescenti — <strong>Beginner → Follower → Fast-tracker → Trend-setter</strong>.
              Sotto la soglia minima di dati l&apos;analisi dichiara <em style={{ color: "#1B6FE3", fontStyle: "normal", fontWeight: 600 }}>&ldquo;dato insufficiente&rdquo;</em> invece di inventare un punteggio.
            </p>
          </div>

          {/* A2A */}
          <div data-reveal className="od-card" style={{ ...cardBase, marginTop: 18, padding: "30px 32px" }}>
            <h3 style={{ ...comeSub, marginTop: 0 }}>Aperto ad altri agenti — protocollo A2A</h3>
            <p style={{ ...lead, fontSize: 15, maxWidth: "75ch" }}>
              Se <strong>MCP</strong> espone i singoli tool a un LLM, <strong>A2A</strong> espone l&apos;intero
              agente ad altri agenti. Il backend pubblica una <strong>AgentCard</strong> su{" "}
              <code style={{ fontSize: 12, color: "#1B6FE3" }}>/.well-known/agent-card.json</code> e accetta
              richieste JSON-RPC su <code style={{ fontSize: 12, color: "#1B6FE3" }}>/a2a/</code>: un altro
              agente può invocarne le skill senza conoscerne l&apos;implementazione.
            </p>
            <div className="row g-2" style={{ marginTop: 8 }}>
              <SkillRow id="search_open_data" desc="cerca dataset multi-fonte (CKAN + SDMX) con sintesi e risorse" />
              <SkillRow id="find_geo_resources" desc="come sopra, ma solo risorse geografiche mappabili" />
              <SkillRow id="classify_dataset" desc="classifica un dataset rispetto a una tassonomia" />
              <SkillRow id="assess_maturity" desc="scorecard di maturità ODM 2025 di un ente" />
              <SkillRow id="analyze_territory" desc="SWOT + proposte per un comune, con citazioni" />
            </div>
          </div>
        </div>
      </section>

      {/* ============ PER CHI ============ */}
      <section id="perchi" style={{ background: HERO_BG, color: "#fff", padding: "96px 0", position: "relative", overflow: "hidden", scrollMarginTop: 80 }}>
        <div aria-hidden="true" style={{ position: "absolute", inset: 0, background: "radial-gradient(700px 380px at 15% 110%,rgba(15,163,163,.22),transparent 60%)" }} />
        <div className="container" style={{ position: "relative" }}>
          <div data-reveal style={{ maxWidth: 680 }}>
            <div style={{ ...eyebrow, color: "#5FD3D3" }}>Per chi è</div>
            <h2 style={{ ...h2, color: "#fff", marginBottom: 0 }}>Tre pubblici, un solo backend</h2>
          </div>
          <div className="row g-4" style={{ marginTop: 32 }}>
            <PubblicoCard iconBg="rgba(27,111,227,.2)" icon={ICON.building} iconStroke="#6BA8FF" title="Pubbliche amministrazioni" body="Misura la maturità del proprio patrimonio dati, scopri le lacune e trasformale in progetti per il territorio. Conforme agli standard del Design System italiano." delay={0} />
            <PubblicoCard iconBg="rgba(31,169,113,.2)" icon={ICON.people} iconStroke="#5FE0A8" title="Cittadini e comunità" body="Un sito civico statico, leggibile e verificabile: ogni numero linkato alla fonte e alla licenza. Trasparenza su cosa è stato fatto e cosa manca." delay={120} />
            <PubblicoCard iconBg="rgba(15,163,163,.2)" icon={ICON.code} iconStroke="#5FD3D3" title="Sviluppatori e integratori" body="REST autenticato, tre server MCP (stdio o HTTP) e una AgentCard A2A. Tre superfici programmabili, pensate per essere componibili." delay={240} />
          </div>
        </div>
      </section>

      {/* ============ SVILUPPATORI ============ */}
      <section id="sviluppatori" style={{ background: "var(--color-bg-muted)", padding: "96px 0", scrollMarginTop: 80 }}>
        <div className="container">
          <div data-reveal className="row g-5 align-items-start">
            <div className="col-lg-6">
              <div style={eyebrow}>Sviluppatori</div>
              <h2 style={h2}>Tre superfici, un solo backend</h2>
              <p style={{ ...lead, fontSize: 17, marginBottom: 24 }}>
                Scegli l&apos;interfaccia più adatta al tuo caso d&apos;uso. Stessa fonte, stessi dati, autenticazione coerente.
              </p>
              <div className="d-flex flex-column gap-2">
                <SurfaceRow title="MCP — Model Context Protocol" sub="3 server (CKAN, ISTAT, OSM) per ogni client MCP" badge="stdio · http" />
                <SurfaceRow title="A2A — Agent-to-Agent" sub="AgentCard pubblica + JSON-RPC SendMessage" badge="SDK 1.0" />
                <SurfaceRow title="REST diretto" sub="/datasets/search/stream NDJSON · classify con cache 24h" badge="JWT" />
              </div>
            </div>
            <div className="col-lg-6 d-flex flex-column gap-3">
              <CodeBlock lang="cURL" langBg="rgba(27,111,227,.3)" caption="REST streaming">{`curl -N -X POST https://api.opendata-ai.it/datasets/search/stream \\
  -H 'Authorization: Bearer <jwt>' \\
  -H 'Content-Type: application/json' \\
  -d '{"query":"popolazione di Milano per età"}'`}</CodeBlock>
              <CodeBlock lang="Python" langBg="rgba(15,163,163,.32)" caption="A2A SendMessage">{`from a2a.client import A2AClient

client = A2AClient("https://api.opendata-ai.it/a2a/")
reply = client.send_message(
    "qualità dell'aria a Milano",
    metadata={"skill": "search_open_data"},
)
print(reply.artifacts[0].parts[0].text)`}</CodeBlock>
            </div>
          </div>
        </div>
      </section>

      {/* ============ CULTURA DEL DATO / APPROFONDIMENTI ============ */}
      <section id="approfondimenti" style={{ background: "#fff", padding: "96px 0", scrollMarginTop: 80 }}>
        <div className="container">
          <div data-reveal style={{ maxWidth: 720 }}>
            <div style={eyebrow}>Cultura del dato</div>
            <h2 style={h2}>Il valore degli open data senza esporre i cittadini</h2>
            <p style={lead}>
              Il patrimonio informativo della PA è un asset strategico, ma va valorizzato{" "}
              <strong>senza esporre le persone</strong>. OpenData AI lavora solo su dati già pubblici e
              aggregati, da fonti ufficiali — mai su dati personali dei cittadini.
            </p>
          </div>

          <div className="row g-3" style={{ marginTop: 34 }}>
            <SpecCard tag="Asset pubblico" tagBg="#E7F0FD" tagColor="#1959B8" title="Un tesoro di dati" body="Anagrafe, mobilità, ambiente, bilanci: aperti nel modo giusto diventano un bene comune che alimenta servizi, ricerca e trasparenza." delay={0} />
            <SpecCard tag="Tutela" tagBg="#E1F4F4" tagColor="#0B7878" title="Aprire senza esporre" body="Il rischio non è il nome, è la re-identificazione per incrocio di campi. Meglio rinunciare a un dato che pubblicarne uno riconducibile a una persona." delay={60} />
            <SpecCard tag="Tecniche" tagBg="#E4F5EC" tagColor="#147A52" title="Anonimizzazione e PET" body="Anonimizzazione, pseudonimizzazione, k-anonymity e dati sintetici: la cassetta degli attrezzi per estrarre valore riducendo l'esposizione." delay={120} />
            <SpecCard tag="Il nostro approccio" tagBg="#E7EEFE" tagColor="#1B6FE3" title="Solo dati già aperti" body="Nessun nuovo trattamento di dati personali, ogni numero tracciabile alla fonte, «dato insufficiente» al posto di punteggi falsi." delay={180} rail />
          </div>

          <div data-reveal className="d-flex flex-wrap gap-3" style={{ marginTop: 30 }}>
            <Link
              href="/approfondimenti"
              className="d-inline-flex align-items-center gap-2"
              style={{ padding: "13px 24px", borderRadius: 999, background: "#E7F0FD", color: "#1959B8", textDecoration: "none", fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: 16 }}
            >
              Leggi l&apos;approfondimento
              <Icon path={ICON.arrow} stroke="currentColor" size={16} />
            </Link>
            <Link
              href="/guida-open-data"
              className="d-inline-flex align-items-center gap-2"
              style={{ padding: "13px 24px", borderRadius: 999, border: "1.5px solid var(--color-border)", color: "#42535F", textDecoration: "none", fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: 16 }}
            >
              Guida open data per i Comuni
              <Icon path={ICON.arrow} stroke="currentColor" size={16} />
            </Link>
          </div>
        </div>
      </section>

      {/* ============ CTA FINALE ============ */}
      <section id="prova" style={{ position: "relative", background: BRAND_BG, color: "#fff", padding: "92px 0", overflow: "hidden", scrollMarginTop: 80 }}>
        <div aria-hidden="true" style={{ position: "absolute", left: -80, bottom: -120, width: 360, height: 360, opacity: 0.18, pointerEvents: "none" }}>
          <svg width="360" height="360" viewBox="0 0 48 48" fill="none">
            <circle cx="24" cy="24" r="15" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeDasharray="71 26" transform="rotate(-58 24 24)" />
          </svg>
        </div>
        <div className="container text-center" style={{ position: "relative", maxWidth: 760 }}>
          <h2 data-reveal style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "clamp(2.1rem,3.8vw,3rem)", lineHeight: 1.08, letterSpacing: "-0.02em", color: "#fff", margin: "0 0 16px" }}>
            Pronto a fare la prima domanda?
          </h2>
          <p data-reveal data-delay="80" className="mx-auto" style={{ fontFamily: "var(--font-sans)", fontSize: 18, lineHeight: 1.6, color: "rgba(255,255,255,.92)", margin: "0 auto 34px", maxWidth: "56ch" }}>
            Crea un account e prova l&apos;analisi di un territorio. L&apos;uso esplorativo è gratuito; abbonamenti, sponsor e convenzioni alzano i limiti e mantengono il progetto open source.
          </p>
          <div data-reveal data-delay="160" className="d-flex flex-wrap justify-content-center gap-3">
            <AuthAwareCTAs variant="final" />
            <Link href="/sostieni" className="d-inline-flex align-items-center" style={{ padding: "15px 28px", borderRadius: 999, border: "1.5px solid rgba(255,255,255,.55)", color: "#fff", textDecoration: "none", fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: 17 }}>
              Sostieni il progetto
            </Link>
          </div>
          <p data-reveal data-delay="220" className="mx-auto" style={{ margin: "30px auto 0", fontFamily: "var(--font-sans)", fontSize: 13, lineHeight: 1.5, color: "rgba(255,255,255,.72)", maxWidth: "60ch" }}>
            Le risposte dell&apos;agente dipendono da modelli LLM esterni e possono contenere errori — verifica sempre i dati consultando la fonte indicata.
          </p>
        </div>
      </section>
    </div>
  );
}

/* ─────────────────────────── sotto-componenti ─────────────────────────── */

function SourcePill({ bg, color, check, label }: { bg: string; color: string; check: string; label: string }) {
  return (
    <span className="d-inline-flex align-items-center gap-2" style={{ padding: "5px 11px", borderRadius: 999, background: bg, color, fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: 11.5 }}>
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke={check} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M20 6L9 17l-5-5" />
      </svg>
      {label}
    </span>
  );
}

function Stat({ value, label, delay, gradient }: { value: string; label: string; delay: number; gradient?: boolean }) {
  const numStyle: CSSProperties = {
    fontFamily: "var(--font-display)",
    fontWeight: 700,
    fontSize: "clamp(2rem,3vw,2.6rem)",
    lineHeight: 1,
    letterSpacing: "-0.02em",
    color: "#0E2233",
  };
  return (
    <div className="col-6 col-md-3" data-reveal data-delay={delay}>
      {gradient ? (
        <div className="text-gradient-brand" style={numStyle}>{value}</div>
      ) : (
        <div style={numStyle}>{value}</div>
      )}
      <div style={{ fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: 12.5, lineHeight: 1.3, letterSpacing: "0.08em", textTransform: "uppercase", color: "#7E8F9C", marginTop: 9 }}>{label}</div>
    </div>
  );
}

function PercorsoCard({ n, tag, tagColor, iconBg, icon, iconStroke, title, body, delay }: { n: string; tag: string; tagColor: string; iconBg: string; icon: string; iconStroke: string; title: string; body: string; delay: number }) {
  return (
    <div className="col-md-6 col-lg-3" data-reveal data-delay={delay}>
      <div className="od-card" style={cardBase}>
        <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 13, color: "#C5CDD5" }}>{n}</div>
        <div className="d-flex align-items-center justify-content-center" style={{ margin: "16px 0 10px", width: 42, height: 42, borderRadius: 11, background: iconBg }}>
          <Icon path={icon} stroke={iconStroke} />
        </div>
        <div style={{ fontFamily: "var(--font-sans)", fontWeight: 700, fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase", color: tagColor }}>{tag}</div>
        <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: 18, lineHeight: 1.25, color: "#0E2233", margin: "8px 0" }}>{title}</h3>
        <p style={{ fontFamily: "var(--font-sans)", fontSize: 14, lineHeight: 1.55, color: "#7E8F9C", margin: 0 }}>{body}</p>
      </div>
    </div>
  );
}

function DimCard({ n, desc }: { n: string; desc: string }) {
  return (
    <div className="col-sm-6 col-lg-3">
      <div style={{ height: "100%", background: "var(--color-bg-muted)", border: "1px solid var(--color-border)", borderRadius: 12, padding: "14px 16px" }}>
        <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 15, color: "#1B6FE3", marginBottom: 4 }}>{n}</div>
        <div style={{ fontFamily: "var(--font-sans)", fontSize: 13, lineHeight: 1.5, color: "#7E8F9C" }}>{desc}</div>
      </div>
    </div>
  );
}

function SkillRow({ id, desc }: { id: string; desc: string }) {
  return (
    <div className="col-12 col-md-6">
      <div className="d-flex align-items-baseline gap-2" style={{ fontSize: 14 }}>
        <code style={{ fontSize: 12.5, color: "#1B6FE3", background: "#EEF3FE", padding: "2px 7px", borderRadius: 6, whiteSpace: "nowrap" }}>{id}</code>
        <span style={{ color: "#5B6B7B" }}>{desc}</span>
      </div>
    </div>
  );
}

function SpecCard({ tag, tagBg, tagColor, title, body, delay, rail }: { tag: string; tagBg: string; tagColor: string; title: string; body: React.ReactNode; delay: number; rail?: boolean }) {
  return (
    <div className="col-md-6 col-lg-3" data-reveal data-delay={delay}>
      <div className="od-card" style={{ ...cardBase, padding: 24, overflow: "hidden" }}>
        {rail ? <span style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 4, background: "linear-gradient(180deg,#1B6FE3,#0FA3A3)" }} /> : null}
        <span className="d-inline-block" style={{ padding: "5px 11px", borderRadius: 999, background: tagBg, color: tagColor, fontFamily: "var(--font-sans)", fontWeight: 700, fontSize: 11, letterSpacing: "0.05em" }}>{tag}</span>
        <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: 17, lineHeight: 1.25, color: "#0E2233", margin: "14px 0 8px" }}>{title}</h3>
        <p style={{ fontFamily: "var(--font-sans)", fontSize: 13.5, lineHeight: 1.55, color: "#7E8F9C", margin: 0 }}>{body}</p>
      </div>
    </div>
  );
}

function PubblicoCard({ iconBg, icon, iconStroke, title, body, delay }: { iconBg: string; icon: string; iconStroke: string; title: string; body: string; delay: number }) {
  return (
    <div className="col-md-4" data-reveal data-delay={delay}>
      <div style={{ height: "100%", background: "rgba(255,255,255,.05)", border: "1px solid rgba(255,255,255,.12)", borderRadius: 18, padding: 30 }}>
        <span className="d-inline-flex align-items-center justify-content-center" style={{ width: 48, height: 48, borderRadius: 13, background: iconBg, marginBottom: 18 }}>
          <Icon path={icon} stroke={iconStroke} size={24} />
        </span>
        <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: 19, lineHeight: 1.25, color: "#fff", margin: "0 0 10px" }}>{title}</h3>
        <p style={{ fontFamily: "var(--font-sans)", fontSize: 14.5, lineHeight: 1.6, color: "#AFC0CE", margin: 0 }}>{body}</p>
      </div>
    </div>
  );
}

function SurfaceRow({ title, sub, badge }: { title: string; sub: string; badge: string }) {
  return (
    <div className="d-flex align-items-center justify-content-between gap-3" style={{ padding: "16px 18px", background: "#fff", border: "1px solid var(--color-border)", borderRadius: 12 }}>
      <div>
        <div style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: 15, lineHeight: 1.2, color: "#0E2233" }}>{title}</div>
        <div style={{ fontFamily: "var(--font-sans)", fontSize: 13, lineHeight: 1.4, color: "#7E8F9C", marginTop: 3 }}>{sub}</div>
      </div>
      <span className="flex-shrink-0" style={{ fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: 11, color: "#5B6B7B", background: "#EEF1F4", padding: "5px 10px", borderRadius: 6 }}>{badge}</span>
    </div>
  );
}

function CodeBlock({ lang, langBg, caption, children }: { lang: string; langBg: string; caption: string; children: string }) {
  return (
    <div style={{ background: "#0E2233", borderRadius: 14, overflow: "hidden", boxShadow: "0 12px 30px rgba(14,34,51,.18)" }}>
      <div className="d-flex align-items-center gap-2" style={{ padding: "11px 16px", borderBottom: "1px solid rgba(255,255,255,.08)" }}>
        <span style={{ fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: 11, color: "#fff", background: langBg, padding: "4px 9px", borderRadius: 5 }}>{lang}</span>
        <span style={{ fontFamily: "var(--font-sans)", fontSize: 12.5, color: "#8C9BA8" }}>{caption}</span>
      </div>
      <pre style={{ margin: 0, padding: "16px 18px", overflowX: "auto", fontFamily: "var(--font-mono)", fontSize: 12.5, lineHeight: 1.7, color: "#C7D2DC" }}>
        {children}
      </pre>
    </div>
  );
}

function FanOut() {
  return (
    <svg viewBox="0 0 1040 300" style={{ width: "100%", height: "auto" }} fontFamily="Titillium Web,sans-serif" role="img" aria-label="Diagramma: una domanda in linguaggio naturale viene smistata in parallelo ai tre specialisti CKAN, SDMX 2.1 e OSM, le cui risposte convergono in un agente di sintesi che produce una risposta unica con fonti citate.">
      <defs>
        <linearGradient id="fang" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#1B6FE3" />
          <stop offset="1" stopColor="#0FA3A3" />
        </linearGradient>
      </defs>
      {/* Connettori domanda → specialisti */}
      <path className="od-flow" d="M236 150 C 330 150, 330 55, 424 55" fill="none" stroke="#1B6FE3" strokeWidth="2.5" strokeDasharray="6 12" strokeLinecap="round" opacity=".9" />
      <path className="od-flow" d="M236 150 C 330 150, 330 150, 424 150" fill="none" stroke="#0FA3A3" strokeWidth="2.5" strokeDasharray="6 12" strokeLinecap="round" opacity=".9" />
      <path className="od-flow" d="M236 150 C 330 150, 330 245, 424 245" fill="none" stroke="#1FA971" strokeWidth="2.5" strokeDasharray="6 12" strokeLinecap="round" opacity=".9" />
      {/* Connettori specialisti → sintesi */}
      <path className="od-flow--slow" d="M612 55 C 706 55, 706 150, 800 150" fill="none" stroke="#AFC0CE" strokeWidth="2.5" strokeDasharray="6 12" strokeLinecap="round" />
      <path className="od-flow--slow" d="M612 150 C 706 150, 706 150, 800 150" fill="none" stroke="#AFC0CE" strokeWidth="2.5" strokeDasharray="6 12" strokeLinecap="round" />
      <path className="od-flow--slow" d="M612 245 C 706 245, 706 150, 800 150" fill="none" stroke="#AFC0CE" strokeWidth="2.5" strokeDasharray="6 12" strokeLinecap="round" />
      {/* Nodo domanda */}
      <g>
        <rect x="24" y="116" width="212" height="68" rx="16" fill="#0E2233" />
        <text x="48" y="146" fill="#fff" fontSize="16" fontWeight="700">Una domanda</text>
        <text x="48" y="167" fill="#AFC0CE" fontSize="12.5">in linguaggio naturale</text>
      </g>
      {/* Specialisti */}
      <g>
        <rect x="424" y="27" width="188" height="56" rx="14" fill="#fff" stroke="#1B6FE3" strokeWidth="2" />
        <circle className="od-pulse" cx="448" cy="55" r="5" fill="#1B6FE3" />
        <text x="466" y="51" fill="#0E2233" fontSize="14.5" fontWeight="700">CKAN</text>
        <text x="466" y="69" fill="#7E8F9C" fontSize="11.5">Cataloghi open</text>
      </g>
      <g>
        <rect x="424" y="122" width="188" height="56" rx="14" fill="#fff" stroke="#0FA3A3" strokeWidth="2" />
        <circle className="od-pulse" cx="448" cy="150" r="5" fill="#0FA3A3" />
        <text x="466" y="146" fill="#0E2233" fontSize="14.5" fontWeight="700">SDMX 2.1</text>
        <text x="466" y="164" fill="#7E8F9C" fontSize="11.5">ISTAT · Eurostat · OCSE</text>
      </g>
      <g>
        <rect x="424" y="217" width="188" height="56" rx="14" fill="#fff" stroke="#1FA971" strokeWidth="2" />
        <circle className="od-pulse" cx="448" cy="245" r="5" fill="#1FA971" />
        <text x="466" y="241" fill="#0E2233" fontSize="14.5" fontWeight="700">OSM</text>
        <text x="466" y="259" fill="#7E8F9C" fontSize="11.5">Geocoding + mappa</text>
      </g>
      {/* Sintesi */}
      <g>
        <rect x="800" y="112" width="216" height="76" rx="18" fill="url(#fang)" />
        <text x="826" y="146" fill="#fff" fontSize="16" fontWeight="700">Sintesi</text>
        <text x="826" y="167" fill="rgba(255,255,255,.88)" fontSize="12">Risposta unica · fonti citate</text>
      </g>
    </svg>
  );
}
