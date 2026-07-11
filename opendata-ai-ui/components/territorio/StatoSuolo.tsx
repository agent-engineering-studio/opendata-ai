import type { SoilRecord } from "@/lib/types";
import { ConfidenzaBadge } from "./ConfidenzaBadge";

/* Sezione "Stato reale del suolo" (Parte V, #130): per ogni area candidata mostra
 * il record riconciliato §4.5 — tag OSM dichiarato → uso reale/destinazione/vincoli
 * → classificazione → azione consigliata, con badge di confidenza. I campi "da
 * verificare" sono resi ESPLICITAMENTE (mai nascosti); la proprietà è "accertata o
 * da verificare, mai presunta pubblica" (§6). */

const CLASSIFICAZIONE: Record<string, { label: string; className: string }> = {
  BROWNFIELD: { label: "Brownfield (contaminato)", className: "bg-danger text-white" },
  VINCOLATO: { label: "Vincolato", className: "bg-warning text-white" },
  FRANGIA: { label: "Frangia urbana", className: "bg-info text-white" },
  DISMESSO: { label: "Dismesso", className: "bg-secondary text-white" },
  LIBERO: { label: "Libero", className: "bg-success text-white" },
  SPAZIO_PUBBLICO: { label: "Spazio pubblico", className: "bg-primary text-white" },
  DA_VERIFICARE: { label: "Da verificare", className: "bg-light text-dark border" },
};

const DA_VERIFICARE = "da verificare";

function Campo({ etichetta, valore }: { etichetta: string; valore: string }) {
  const daVerificare = valore.trim().toLowerCase() === DA_VERIFICARE;
  return (
    <div className="col-sm-6">
      <div className="small text-muted">{etichetta}</div>
      <div className={daVerificare ? "fst-italic text-secondary" : ""}>{valore}</div>
    </div>
  );
}

function RecordCard({ r }: { r: SoilRecord }) {
  const cls = CLASSIFICAZIONE[r.classificazione] ?? CLASSIFICAZIONE.DA_VERIFICARE;
  const titolo = r.nome || r.id_geometria;
  return (
    <div className="card mb-3">
      <div className="card-body">
        <div className="d-flex flex-wrap justify-content-between align-items-start gap-2 mb-2">
          <h3 className="h6 mb-0">
            {r.url ? (
              <a href={r.url} target="_blank" rel="noopener noreferrer">{titolo}</a>
            ) : (
              titolo
            )}
            {typeof r.area_mq === "number" && (
              <span className="text-muted small ms-2">· {r.area_mq.toLocaleString("it-IT")} m²</span>
            )}
          </h3>
          <div className="d-flex gap-2">
            <span className={`badge ${cls.className}`}>{cls.label}</span>
            <ConfidenzaBadge livello={r.confidenza} />
          </div>
        </div>
        <div className="row g-2">
          <Campo etichetta="Tag OSM" valore={r.tag_osm} />
          <Campo etichetta="Uso reale" valore={r.uso_reale} />
          <Campo etichetta="Destinazione (PUG/PRG)" valore={r.destinazione_pug} />
          <Campo etichetta="Vincoli" valore={r.vincoli} />
          <Campo etichetta="Proprietà" valore={r.proprieta} />
          <Campo etichetta="Catasto" valore={r.catasto} />
          <Campo etichetta="Causa di abbandono" valore={r.causa_abbandono} />
          <Campo etichetta="Discrepanza OSM ↔ realtà" valore={r.discrepanza_osm} />
        </div>
        <div className="mt-2">
          <span className="small text-muted">Azione consigliata: </span>
          <span>{r.azione_consigliata}</span>
        </div>
        {r.caveat.length > 0 && (
          <ul className="small text-muted mt-2 mb-0">
            {r.caveat.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function StatoSuolo({ records }: { records: SoilRecord[] }) {
  if (!records.length) return null;
  return (
    <section aria-label="Stato reale del suolo" className="mb-4">
      <h2 className="h5">Stato reale del suolo</h2>
      <div className="alert alert-info small" style={{ borderLeft: "4px solid var(--bs-primary)" }}>
        OpenStreetMap descrive ciò che è <em>mappato</em>, non lo stato giuridico o reale del
        suolo. Ogni area confronta il tag OSM con le fonti ufficiali disponibili; l&apos;esito ha
        una <strong>confidenza</strong> esplicita e i campi non verificabili restano
        &laquo;da verificare&raquo;. La <strong>proprietà</strong> è dichiarata accertata o da
        verificare, <strong>mai presunta pubblica</strong>.
      </div>
      {records.map((r) => (
        <RecordCard key={r.id_geometria} r={r} />
      ))}
    </section>
  );
}
