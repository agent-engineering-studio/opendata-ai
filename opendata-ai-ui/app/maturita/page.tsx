"use client";

import { Suspense, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { downloadScorecardPdf, type Guida } from "@/lib/scorecardPdf";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { DashboardGate } from "@/components/DashboardGate";

/*
 * Maturità open data di un ente (modello ODM 2025). POST /maturity/assess →
 * 4 dimensioni + livello + raccomandazioni + pesi; in più carichiamo il valore del
 * patrimonio (GET /value/portfolio?entity_id=) per lo stesso ente. Niente trend:
 * al suo posto un piano "come salire di livello" ordinato per impatto sul punteggio.
 */

type Recommendation = {
  code: string;
  severity: string;
  dimension: string;
  message: string;
  affected_count: number;
};

type Dimensions = { policy: number; portal: number; quality: number; impact: number };

type Scorecard = {
  entity: { id: number; name: string; type: string | null; region: string | null };
  assessed_at: string;
  level: string;
  overall: number;
  dimensions: Dimensions;
  weights?: Partial<Dimensions>;
  recommendations: Recommendation[];
  n_datasets: number | null;
  truncated: boolean | null;
  insufficient_data?: boolean;
  guida?: Guida | null;
};

type Portfolio = {
  count: number;
  pct_hvd: number | null;
  pct_open_license: number | null;
  avg_freshness_days: number | null;
  avg_stars: number | null;
  avg_reuse: number | null;
};

type Stato =
  | { fase: "idle" }
  | { fase: "loading" }
  | { fase: "errore"; messaggio: string }
  | { fase: "risultato"; scorecard: Scorecard };

const LEVEL_COLOR: Record<string, string> = {
  Beginner: "#dc2626",
  Follower: "#d97706",
  "Fast-tracker": "#2563eb",
  "Trend-setter": "#059669",
};

const SEVERITY_COLOR: Record<string, string> = {
  alta: "#dc2626",
  media: "#d97706",
  bassa: "#64748b",
};

const DIM_KEYS = ["policy", "portal", "quality", "impact"] as const;
const DIM_LABEL: Record<string, string> = {
  policy: "Policy",
  portal: "Portale",
  quality: "Qualità",
  impact: "Impatto",
};
const WEIGHTS_FALLBACK: Dimensions = { policy: 0.25, portal: 0.25, quality: 0.3, impact: 0.2 };
// Soglie ODM 2025 crescenti sul punteggio complessivo.
const ODM_LEVELS: [number, string][] = [
  [0, "Beginner"],
  [40, "Follower"],
  [60, "Fast-tracker"],
  [80, "Trend-setter"],
];

/** Leve di miglioramento ordinate per potenziale = (100 − dim) × peso (= guadagno max sul complessivo). */
function buildImprovements(sc: Scorecard) {
  const w = { ...WEIGHTS_FALLBACK, ...(sc.weights ?? {}) };
  const leve = DIM_KEYS.map((k) => {
    const score = sc.dimensions[k];
    const weight = (w[k] ?? WEIGHTS_FALLBACK[k]) as number;
    return {
      key: k,
      label: DIM_LABEL[k],
      score,
      potential: (100 - score) * weight,
      recs: sc.recommendations.filter((r) => r.dimension === k),
    };
  })
    .filter((d) => d.potential >= 1)
    .sort((a, b) => b.potential - a.potential);
  const next = ODM_LEVELS.find(([t]) => t > sc.overall);
  return { leve, nextLevel: next ? { name: next[1], gap: next[0] - sc.overall } : null };
}

async function captureNode(node: HTMLElement): Promise<string | null> {
  try {
    const { toPng } = await import("html-to-image");
    return await toPng(node, { backgroundColor: "#ffffff", pixelRatio: 2, cacheBust: true });
  } catch {
    return null;
  }
}

function MaturitaInner() {
  const { getToken } = useAuth();
  const params = useSearchParams();
  const [entity, setEntity] = useState(params.get("entity") ?? "");
  const [istat, setIstat] = useState(params.get("istat") ?? "");
  const [stato, setStato] = useState<Stato>({ fase: "idle" });
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);

  async function assess(e?: React.FormEvent) {
    e?.preventDefault();
    const name = entity.trim();
    if (!name) return;
    setStato({ fase: "loading" });
    setPortfolio(null);
    try {
      const token = await getToken();
      const resp = await apiFetch("/maturity/assess", {
        method: "POST",
        token,
        body: JSON.stringify({
          entity: name,
          comune_nome: name,
          istat_code: istat.trim() || undefined,
        }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const scorecard = (await resp.json()) as Scorecard;
      setStato({ fase: "risultato", scorecard });
      // Valore del patrimonio dello stesso ente (best-effort, non blocca la scorecard).
      const eid = scorecard.entity?.id;
      if (eid && !scorecard.insufficient_data) {
        try {
          const rv = await apiFetch(`/value/portfolio?entity_id=${eid}`, { token });
          if (rv.ok) setPortfolio((await rv.json()) as Portfolio);
        } catch {
          /* il valore è opzionale */
        }
      }
    } catch (err) {
      setStato({ fase: "errore", messaggio: err instanceof Error ? err.message : String(err) });
    }
  }

  return (
    <main id="main-content" className="container py-4">
      <h1 className="h3 mb-1">Maturità open data</h1>
      <p className="text-slate-500 mb-3" style={{ fontSize: 14 }}>
        Valuta quanto sono completi, aperti e riutilizzabili gli open data di un{" "}
        <strong>ente</strong> (comune, Regione, provincia, agenzia…) secondo il modello
        ODM 2025, e indica concretamente dove intervenire per migliorare. Per gli enti
        senza open data viene proposta una guida operativa per avviarli.
      </p>

      <form onSubmit={assess} className="d-flex flex-wrap gap-2 mb-4" style={{ maxWidth: 720 }}>
        <input
          type="text"
          className="form-control"
          style={{ flex: 2, minWidth: 240 }}
          placeholder="Ente (nome o organizzazione CKAN, es. Regione Puglia, Comune di Bari)"
          value={entity}
          onChange={(ev) => setEntity(ev.target.value)}
        />
        <input
          type="text"
          className="form-control"
          style={{ flex: 1, minWidth: 150, maxWidth: 220 }}
          placeholder="ISTAT comune (opz.)"
          value={istat}
          onChange={(ev) => setIstat(ev.target.value)}
          title="Solo per i comuni: il codice ISTAT abilita il fallback sul portale open-data regionale. Lascia vuoto per Regioni/agenzie."
        />
        <button type="submit" className="btn btn-primary" disabled={stato.fase === "loading"}>
          {stato.fase === "loading" ? "Valutazione…" : "Valuta"}
        </button>
      </form>

      {stato.fase === "errore" ? (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-700" style={{ fontSize: 14 }}>
          Errore nell&apos;assessment: {stato.messaggio}
        </div>
      ) : null}

      {stato.fase === "risultato" ? (
        <ScorecardView scorecard={stato.scorecard} portfolio={portfolio} />
      ) : null}
    </main>
  );
}

function GuidaView({ guida }: { guida: Guida }) {
  return (
    <div className="rounded border border-primary bg-bg-muted p-4">
      <h3 className="h5 mb-2">{guida.titolo}</h3>
      <p className="text-slate-600" style={{ fontSize: 14 }}>{guida.premessa}</p>
      <ol className="d-flex flex-column gap-3 mt-3" style={{ paddingLeft: 18 }}>
        {guida.passi.map((p, i) => (
          <li key={i}>
            <strong>{p.titolo}</strong>
            <div className="text-slate-600" style={{ fontSize: 14 }}>{p.descrizione}</div>
            {(p.riferimenti ?? []).map((r) => (
              <div key={r.url} style={{ fontSize: 13 }}>
                <a href={r.url} target="_blank" rel="noopener noreferrer">{r.label} →</a>
              </div>
            ))}
          </li>
        ))}
      </ol>
      {guida.nota ? (
        <p className="text-slate-500 fst-italic mt-3 mb-0" style={{ fontSize: 12 }}>{guida.nota}</p>
      ) : null}
    </div>
  );
}

function ValoreCard({ pf }: { pf: Portfolio }) {
  const kpi = (label: string, value: string) => (
    <div className="col">
      <div className="h5 mb-0 text-primary">{value}</div>
      <div className="small text-muted">{label}</div>
    </div>
  );
  return (
    <div>
      <h3 className="h6 text-slate-500">Valore del patrimonio</h3>
      <p className="text-slate-500 mb-2" style={{ fontSize: 13 }}>
        Quanto valgono, in pratica, i {pf.count} dataset appena valutati: copertura ad alto
        valore (HVD), apertura della licenza, freschezza e potenziale di riuso.
      </p>
      <div className="row g-3 text-center">
        {kpi("Dataset", String(pf.count))}
        {kpi("Alto valore (HVD)", pf.pct_hvd != null ? `${Math.round(pf.pct_hvd)}%` : "—")}
        {kpi("Licenza aperta", pf.pct_open_license != null ? `${Math.round(pf.pct_open_license)}%` : "—")}
        {kpi("Stelle medie", pf.avg_stars != null ? pf.avg_stars.toFixed(1) : "—")}
        {kpi("Riuso medio", pf.avg_reuse != null ? pf.avg_reuse.toFixed(1) : "—")}
      </div>
    </div>
  );
}

function ScorecardView({ scorecard, portfolio }: { scorecard: Scorecard; portfolio: Portfolio | null }) {
  const cardRef = useRef<HTMLDivElement>(null);
  const radarRef = useRef<HTMLDivElement>(null);
  const slug = (scorecard.entity.name || "ente").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  const insufficient = scorecard.insufficient_data && scorecard.guida;
  const { dimensions, level, overall } = scorecard;
  const radarData = DIM_KEYS.map((k) => ({ dim: DIM_LABEL[k], value: dimensions[k] }));
  const levelColor = LEVEL_COLOR[level] ?? "#334155";
  const { leve, nextLevel } = buildImprovements(scorecard);

  async function exportPng() {
    if (!cardRef.current) return;
    const data = await captureNode(cardRef.current);
    if (!data) return;
    const a = document.createElement("a");
    a.href = data;
    a.download = `maturita-${slug || "ente"}.png`;
    a.click();
  }

  async function exportPdf() {
    const radarPng = radarRef.current ? (await captureNode(radarRef.current)) ?? undefined : undefined;
    await downloadScorecardPdf(scorecard, radarPng);
  }

  return (
    <div className="d-flex flex-column gap-3">
      {/* Toolbar export */}
      <div className="d-flex gap-2">
        <button type="button" className="btn btn-primary btn-sm" onClick={exportPdf}>
          Esporta PDF
        </button>
        <button type="button" className="btn btn-outline-primary btn-sm" onClick={exportPng}>
          Esporta PNG
        </button>
      </div>

      <div ref={cardRef} className="d-flex flex-column gap-4 bg-white p-3 rounded">
        {/* Header */}
        <div className="d-flex flex-wrap align-items-center gap-3">
          <div>
            <h2 className="h4 mb-0">{scorecard.entity.name}</h2>
            <span className="text-slate-500" style={{ fontSize: 13 }}>
              {scorecard.entity.type ?? "ente"}
              {scorecard.entity.region ? ` · ${scorecard.entity.region}` : ""} ·{" "}
              {scorecard.n_datasets ?? 0} dataset valutati
              {scorecard.truncated ? " (campione)" : ""}
            </span>
          </div>
          <span
            className="badge rounded-pill px-3 py-2"
            style={{ backgroundColor: levelColor, color: "white", fontSize: 14 }}
          >
            {level} · {overall.toFixed(0)}/100
          </span>
        </div>

        {insufficient ? (
          <GuidaView guida={scorecard.guida!} />
        ) : (
          <>
            <div className="row g-4">
              {/* Radar 4 dimensioni */}
              <div className="col-lg-6">
                <h3 className="h6 text-slate-500">Dimensioni</h3>
                <div ref={radarRef} style={{ height: 320, backgroundColor: "#ffffff" }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart data={radarData} outerRadius="70%">
                      <PolarGrid />
                      <PolarAngleAxis dataKey="dim" tick={{ fontSize: 12 }} />
                      <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                      <Radar dataKey="value" stroke="#2563eb" fill="#2563eb" fillOpacity={0.4} />
                      <Tooltip />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Come salire di livello (al posto del trend) */}
              <div className="col-lg-6">
                <h3 className="h6 text-slate-500">Come migliorare</h3>
                {nextLevel ? (
                  <p className="mb-2" style={{ fontSize: 14 }}>
                    Mancano <strong>{Math.round(nextLevel.gap)} punti</strong> per raggiungere il
                    livello <strong>{nextLevel.name}</strong>. Gli interventi a maggiore impatto
                    sul punteggio complessivo:
                  </p>
                ) : (
                  <p className="mb-2" style={{ fontSize: 14 }}>
                    Livello massimo raggiunto. Margini di consolidamento per dimensione:
                  </p>
                )}
                {leve.length === 0 ? (
                  <p className="text-slate-500" style={{ fontSize: 14 }}>
                    Tutte le dimensioni sono già al massimo: nessun intervento prioritario.
                  </p>
                ) : (
                  <ul className="list-unstyled d-flex flex-column gap-2 mb-0">
                    {leve.map((l) => (
                      <li key={l.key}>
                        <div className="d-flex align-items-baseline gap-2">
                          <span className="badge bg-primary">+{Math.round(l.potential)} pti</span>
                          <strong style={{ fontSize: 14 }}>Rafforza {l.label}</strong>
                          <span className="text-slate-400" style={{ fontSize: 12 }}>({Math.round(l.score)}/100)</span>
                        </div>
                        {l.recs.length ? (
                          <ul className="text-slate-600 mb-0" style={{ fontSize: 13, paddingLeft: 20 }}>
                            {l.recs.map((r) => (
                              <li key={r.code}>{r.message}</li>
                            ))}
                          </ul>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
                <p className="text-slate-400 mt-2 mb-0" style={{ fontSize: 11 }}>
                  Il potenziale è il guadagno massimo sul punteggio complessivo portando la
                  dimensione a 100 (pesata secondo il modello ODM).
                </p>
              </div>
            </div>

            {/* Valore del patrimonio (unito alla maturità) */}
            {portfolio && portfolio.count > 0 ? <ValoreCard pf={portfolio} /> : null}

            {/* Raccomandazioni complete */}
            <div>
              <h3 className="h6 text-slate-500">Raccomandazioni</h3>
              {scorecard.recommendations.length === 0 ? (
                <p className="text-slate-500" style={{ fontSize: 14 }}>
                  Nessuna raccomandazione: l&apos;ente soddisfa le soglie principali.
                </p>
              ) : (
                <ul className="list-unstyled d-flex flex-column gap-2">
                  {scorecard.recommendations.map((r) => (
                    <li key={r.code} className="d-flex align-items-start gap-2">
                      <span
                        className="badge rounded-pill"
                        style={{ backgroundColor: SEVERITY_COLOR[r.severity] ?? "#64748b", color: "white" }}
                      >
                        {r.severity}
                      </span>
                      <span style={{ fontSize: 14 }}>
                        {r.message}
                        <span className="text-slate-400"> · {r.dimension}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <DashboardGate>
      <Suspense fallback={<div className="container py-4 text-slate-500">Caricamento…</div>}>
        <MaturitaInner />
      </Suspense>
    </DashboardGate>
  );
}
