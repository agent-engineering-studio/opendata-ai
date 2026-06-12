import type { Evidenza } from "@/lib/types";

const FONTE_LABEL: Record<string, string> = {
  istat: "ISTAT",
  opencoesione: "OpenCoesione",
  ckan: "Open data",
  eurostat: "Eurostat",
  oecd: "OCSE",
  osm: "OpenStreetMap",
  ispra: "ISPRA",
  kg: "Documenti PA",
};

const FONTE_BADGE: Record<string, string> = {
  istat: "bg-warning text-white",
  opencoesione: "bg-success text-white",
  ckan: "bg-primary text-white",
  eurostat: "bg-secondary text-white",
  oecd: "bg-danger text-white",
  osm: "bg-info text-white",
  ispra: "bg-dark text-white",
  kg: "bg-secondary text-white",
};

/**
 * Una singola evidenza: chip della fonte, cosa dice il dato, e il link
 * risolvibile. È il cuore "verificabile" della scheda: ogni claim ha qui
 * la sua fonte cliccabile.
 */
export function CitationLink({ evidenza }: { evidenza: Evidenza }) {
  const label = FONTE_LABEL[evidenza.fonte] ?? evidenza.fonte;
  const documentale = evidenza.tier === "documentale" || evidenza.fonte === "kg";
  // I locator sintetici kg:// non sono URL navigabili — niente link rotto.
  const linkable = /^https?:\/\//.test(evidenza.url);
  return (
    <div className="d-flex align-items-start gap-2 small">
      <span
        className={`badge flex-shrink-0 ${FONTE_BADGE[evidenza.fonte] ?? "bg-secondary text-white"}`}
      >
        {label}
      </span>
      {documentale ? (
        <span
          className="badge flex-shrink-0 border text-dark bg-white"
          title="Fatto tratto da un documento comunale ingerito (delibera, piano, bilancio), non da un dato aperto certificato"
        >
          documento comunale
        </span>
      ) : null}
      <span style={{ color: "var(--color-text-muted)" }}>
        {evidenza.dettaglio}{" "}
        {linkable ? (
          <a
            href={evidenza.url}
            target="_blank"
            rel="noreferrer"
            className="text-decoration-underline"
            style={{ wordBreak: "break-all" }}
          >
            verifica la fonte
          </a>
        ) : (
          <span className="fst-italic" style={{ wordBreak: "break-all" }}>
            rif. {evidenza.url}
          </span>
        )}
      </span>
    </div>
  );
}
