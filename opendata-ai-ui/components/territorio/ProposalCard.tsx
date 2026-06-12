import type { Proposta } from "@/lib/types";
import { CitationLink } from "./CitationLink";
import { FeasibilityBadge } from "./FeasibilityBadge";

function ratioPct(ratio: number | null | undefined): string | null {
  if (ratio === null || ratio === undefined) return null;
  return `${Math.round(ratio * 100)}%`;
}

export function ProposalCard({ proposta }: { proposta: Proposta }) {
  const ratio = ratioPct(proposta.fattibilita.spend_ratio_storico);
  return (
    <article className="card shadow-sm">
      <div className="card-body">
        <div className="d-flex align-items-start justify-content-between gap-2 mb-2">
          <h3 className="h6 fw-bold mb-0">{proposta.titolo}</h3>
          <FeasibilityBadge livello={proposta.fattibilita.livello} />
        </div>

        <p className="mb-2">{proposta.descrizione}</p>

        <p className="small mb-2" style={{ color: "var(--color-text-muted)" }}>
          <strong>Perché questo livello di fattibilità:</strong>{" "}
          {proposta.fattibilita.motivazione}
          {ratio ? ` (capacità di spesa storica: ${ratio})` : null}
        </p>

        {proposta.finanziamento ? (
          <div className="rounded p-2 mb-2 small" style={{ backgroundColor: "var(--color-bg-muted)" }}>
            <strong>Linea di finanziamento:</strong> {proposta.finanziamento.linea}
            {proposta.finanziamento.stato ? ` — ${proposta.finanziamento.stato}` : null}{" "}
            <a
              href={proposta.finanziamento.fonte_url}
              target="_blank"
              rel="noreferrer"
              className="text-decoration-underline"
            >
              fonte
            </a>
          </div>
        ) : (
          <p className="small fst-italic mb-2" style={{ color: "var(--color-text-muted)" }}>
            Nessuna linea di finanziamento individuata nelle evidenze raccolte.
          </p>
        )}

        <div className="d-flex flex-column gap-1">
          {proposta.evidenze.map((e, i) => (
            <CitationLink key={i} evidenza={e} />
          ))}
        </div>
      </div>
    </article>
  );
}
