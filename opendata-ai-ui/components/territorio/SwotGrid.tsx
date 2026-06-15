import type { VoceSwot } from "@/lib/types";
import { CitationLink } from "./CitationLink";

const QUADRANTS: { key: string; title: string; accent: string }[] = [
  { key: "forze", title: "Forze", accent: "var(--color-success)" },
  { key: "debolezze", title: "Debolezze", accent: "var(--color-danger)" },
  { key: "opportunita", title: "Opportunità", accent: "var(--color-primary)" },
  { key: "minacce", title: "Minacce", accent: "var(--color-warning)" },
];

function Quadrant({
  title,
  accent,
  voci,
}: {
  title: string;
  accent: string;
  voci: VoceSwot[];
}) {
  return (
    <section
      className="card h-100 shadow-sm"
      aria-label={`SWOT — ${title}`}
      style={{ borderTop: `3px solid ${accent}` }}
    >
      <div className="card-body">
        <h3 className="h6 fw-bold mb-3" style={{ color: accent }}>
          {title}
        </h3>
        {voci.length === 0 ? (
          <p className="small text-muted mb-0">
            Nessuna voce con evidenza verificabile.
          </p>
        ) : (
          <ul className="list-unstyled mb-0 d-flex flex-column gap-3">
            {voci.map((voce, i) => (
              <li key={i}>
                <p className="mb-1">{voce.testo}</p>
                <div className="d-flex flex-column gap-1">
                  {voce.evidenze.map((e, j) => (
                    <CitationLink key={j} evidenza={e} />
                  ))}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

/** I 4 quadranti SWOT; ogni voce porta le sue evidenze cliccabili. */
export function SwotGrid({ swot }: { swot: Record<string, VoceSwot[]> }) {
  return (
    <div className="row g-3">
      {QUADRANTS.map((q) => (
        <div key={q.key} className="col-12 col-md-6">
          <Quadrant title={q.title} accent={q.accent} voci={swot[q.key] ?? []} />
        </div>
      ))}
    </div>
  );
}
