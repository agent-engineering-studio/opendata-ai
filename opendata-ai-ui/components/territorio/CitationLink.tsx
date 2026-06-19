import type { Evidenza } from "@/lib/types";
import { resolveSource } from "@/lib/sources";

const FONTE_LABEL: Record<string, string> = {
  istat: "ISTAT",
  opencoesione: "OpenCoesione",
  ckan: "Open data",
  eurostat: "Eurostat",
  oecd: "OCSE",
  osm: "OpenStreetMap",
  ispra: "ISPRA",
  kg: "Analisi precedente",
  web: "Web",
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
  web: "bg-info text-white",
};

/**
 * Una singola evidenza: chip della fonte, cosa dice il dato, e il link
 * risolvibile. È il cuore "verificabile" della scheda: ogni claim ha qui
 * la sua fonte cliccabile.
 */
export function CitationLink({ evidenza }: { evidenza: Evidenza }) {
  const label = FONTE_LABEL[evidenza.fonte] ?? evidenza.fonte;
  // Il KG ora è memoria di ANALISI passate (riuso), non dati ufficiali.
  const daAnalisi = evidenza.tier === "documentale" || evidenza.fonte === "kg";
  // Marketing (Pezzo 10): precedente esterno da cui prendere spunto, non prova.
  const esterna = evidenza.fonte_tipo === "ispirazione_esterna" || evidenza.fonte === "web";
  // I locator sintetici kg:// non sono URL navigabili — niente link rotto.
  const linkable = /^https?:\/\//.test(evidenza.url);
  // Fonte chiara per il display: file/API → sito di origine; OSM/Overpass → null
  // (nessun link: la mappa mostra già il dettaglio).
  const resolved = linkable ? resolveSource(evidenza.url) : null;
  return (
    <div className="d-flex align-items-start gap-2 small">
      <span
        className={`badge flex-shrink-0 ${FONTE_BADGE[evidenza.fonte] ?? "bg-secondary text-white"}`}
      >
        {label}
      </span>
      {daAnalisi ? (
        <span
          className="badge flex-shrink-0 border text-dark bg-white"
          title="Spunto da un'analisi precedente riusata dalla memoria (KG), non un dato aperto ufficiale"
        >
          analisi precedente
        </span>
      ) : null}
      {esterna ? (
        <span
          className="badge flex-shrink-0 border text-dark bg-white"
          title="Iniziativa di un altro ente da cui prendere spunto — ispirazione, non prova per questo comune"
        >
          ispirazione esterna
        </span>
      ) : null}
      <span style={{ color: "var(--color-text-muted)" }}>
        {evidenza.dettaglio}{" "}
        {resolved ? (
          <a
            href={resolved.href}
            target="_blank"
            rel="noreferrer"
            className="text-decoration-underline"
            style={{ wordBreak: "break-all" }}
          >
            verifica la fonte
          </a>
        ) : !linkable ? (
          <span className="fst-italic" style={{ wordBreak: "break-all" }}>
            rif. {evidenza.url}
          </span>
        ) : null /* http ma fonte nascosta (OSM): nessun link, basta la mappa */}
      </span>
    </div>
  );
}
