/*
 * Le 8 lenti analitiche del verticale Territorio.
 *
 * Sezione informativa (sempre visibile nell'intro) che dichiara COSA copre
 * l'analisi: ogni lente è un incrocio dato↔attuato che alimenta SWOT, proposte e
 * idee, ancorato a una fonte pubblica comunale. Specchio UI dei generatori
 * deterministici del backend (factory `_resolve_*` + guardrail per-fonte): se si
 * aggiunge/rimuove una lente lato backend, aggiornare anche questo elenco.
 */

type Lente = {
  icona: string;
  titolo: string;
  cosa: string;
  fonte: string;
};

const LENTI: readonly Lente[] = [
  {
    icona: "🛍️",
    titolo: "Commercio",
    cosa: "Base imprenditoriale e densità commerciale — dove rigenerare il commercio o istituire un DUC.",
    fonte: "ISTAT ASIA + OpenStreetMap",
  },
  {
    icona: "🏛️",
    titolo: "Turismo & cultura",
    cosa: "Asset culturali e capacità ricettiva — patrimonio sottoutilizzato e gap di posti letto.",
    fonte: "OpenStreetMap + ISTAT",
  },
  {
    icona: "💼",
    titolo: "Lavoro",
    cosa: "Occupazione, disoccupazione giovanile, NEET e competenze del territorio.",
    fonte: "ISTAT 8milaCensus",
  },
  {
    icona: "🚌",
    titolo: "Trasporti & mobilità",
    cosa: "Trasporto pubblico, nodo ferroviario e accessibilità — criticità e dipendenza dall'auto.",
    fonte: "OpenStreetMap",
  },
  {
    icona: "🤝",
    titolo: "Welfare",
    cosa: "Fragilità demografica (invecchiamento, dipendenza) e carico sui servizi alla persona.",
    fonte: "ISTAT + OpenCoesione",
  },
  {
    icona: "🎓",
    titolo: "Istruzione",
    cosa: "Dotazione di scuole per ordine — gap di offerta e pendolarismo scolastico.",
    fonte: "MIUR Open Data",
  },
  {
    icona: "⛰️",
    titolo: "Ambiente",
    cosa: "Rischio idrogeologico (frane e alluvioni) — vincolo di pianificazione e mitigazione.",
    fonte: "ISPRA IdroGEO",
  },
  {
    icona: "⚕️",
    titolo: "Sanità",
    cosa: "Farmacie e presìdi di prossimità — accessibilità ai servizi sanitari di base.",
    fonte: "Ministero della Salute",
  },
];

export function LentiAnalitiche() {
  return (
    <details className="mb-4 no-print">
      <summary className="fw-semibold" style={{ cursor: "pointer" }}>
        Le 8 lenti analitiche{" "}
        <span className="fw-normal text-muted">— cosa esamina l&apos;analisi e da quali fonti</span>
      </summary>
      <div className="row row-cols-1 row-cols-md-2 g-3 mt-1">
        {LENTI.map((l) => (
          <div className="col" key={l.titolo}>
            <div className="card h-100 border-0 shadow-sm">
              <div className="card-body py-3">
                <div className="d-flex align-items-start gap-2">
                  <span aria-hidden="true" style={{ fontSize: "1.4rem", lineHeight: 1 }}>
                    {l.icona}
                  </span>
                  <div>
                    <h3 className="h6 mb-1">{l.titolo}</h3>
                    <p className="small text-muted mb-2">{l.cosa}</p>
                    <span className="badge rounded-pill text-bg-light border">{l.fonte}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
      <p className="small text-muted mt-2 mb-0">
        Ogni lente è un incrocio tra ciò che i dati pubblici dicono e ciò che è stato
        attuato; alimenta SWOT, proposte e idee, sempre ancorata alla sua fonte.
      </p>
    </details>
  );
}
