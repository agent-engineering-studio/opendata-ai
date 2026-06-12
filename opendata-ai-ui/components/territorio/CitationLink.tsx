import type { Evidenza } from "@/lib/types";

const FONTE_LABEL: Record<string, string> = {
  istat: "ISTAT",
  opencoesione: "OpenCoesione",
  ckan: "Open data",
  eurostat: "Eurostat",
  oecd: "OCSE",
  osm: "OpenStreetMap",
  ispra: "ISPRA",
};

const FONTE_BADGE: Record<string, string> = {
  istat: "bg-warning text-white",
  opencoesione: "bg-success text-white",
  ckan: "bg-primary text-white",
  eurostat: "bg-secondary text-white",
  oecd: "bg-danger text-white",
  osm: "bg-info text-white",
  ispra: "bg-dark text-white",
};

/**
 * Una singola evidenza: chip della fonte, cosa dice il dato, e il link
 * risolvibile. È il cuore "verificabile" della scheda: ogni claim ha qui
 * la sua fonte cliccabile.
 */
export function CitationLink({ evidenza }: { evidenza: Evidenza }) {
  const label = FONTE_LABEL[evidenza.fonte] ?? evidenza.fonte;
  return (
    <div className="d-flex align-items-start gap-2 small">
      <span
        className={`badge flex-shrink-0 ${FONTE_BADGE[evidenza.fonte] ?? "bg-secondary text-white"}`}
      >
        {label}
      </span>
      <span style={{ color: "var(--color-text-muted)" }}>
        {evidenza.dettaglio}{" "}
        <a
          href={evidenza.url}
          target="_blank"
          rel="noreferrer"
          className="text-decoration-underline"
          style={{ wordBreak: "break-all" }}
        >
          verifica la fonte
        </a>
      </span>
    </div>
  );
}
