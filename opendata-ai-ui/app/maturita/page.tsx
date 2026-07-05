"use client";

import { Suspense, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { downloadScorecardPdf, type Guida } from "@/lib/scorecardPdf";
import { GUIDA_PATH, guideHref, recGuide, GAP_GUIDE } from "@/lib/maturityGuidance";
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

type DimensionBreakdown = {
  dimension: string;
  label: string;
  score: number;
  description: string;
  drivers: { label: string; value: number }[];
  weakest: string[];
};

type Sector = {
  code: string;
  label: string;
  n_datasets: number;
  share: number;
  is_core: boolean;
  present: boolean;
  priority: number | null;
};

type Coverage = {
  entity_type: string;
  coverage_score: number;
  sectors: Sector[];
  missing_core: Sector[];
  hvd_present: string[];
  hvd_missing: string[];
  n_classified: number;
  n_unclassified: number;
};

// Azione della gap analysis (#50): una raccomandazione classificata per sforzo.
type AzioneGap = {
  code: string;
  dimension: string;
  dimension_label: string;
  severity: string;
  tipo: "quick_win" | "strategico";
  messaggio: string;
  affected_count: number;
  sul_collo_di_bottiglia: boolean;
};

// Gap analysis: prossimo livello + collo di bottiglia + azioni ordinate in roadmap.
type Gap = {
  livello_attuale: string;
  prossimo_livello: string | null;
  punti_al_prossimo: number | null;
  collo_di_bottiglia: string;
  collo_di_bottiglia_label: string;
  azioni: AzioneGap[];
  quick_win: AzioneGap[];
  strategiche: AzioneGap[];
};

// Confronto con enti simili (#50): posizione nel cluster + mediane.
type PeerComparison = {
  cluster_label: string;
  count: number;
  rank: number | null;
  better_than_pct: number | null;
  median_overall: number;
  median_dimensions: Dimensions;
};

type Scorecard = {
  entity: { id: number; name: string; type: string | null; region: string | null };
  assessed_at: string;
  level: string;
  overall: number;
  dimensions: Dimensions;
  weights?: Partial<Dimensions>;
  recommendations: Recommendation[];
  dimension_breakdown?: DimensionBreakdown[];
  coverage?: Coverage | null;
  gap?: Gap | null;
  peer_comparison?: PeerComparison | null;
  n_datasets: number | null;
  truncated: boolean | null;
  insufficient_data?: boolean;
  guida?: Guida | null;
  unmet_reuse_demand?: { count: number; items: string[]; penalty: number };
};

// Etichette leggibili delle 6 categorie HVD (Reg. UE 2023/138) — allineate a
// opendata_core.maturity.coverage.HVD_LABELS.
const HVD_LABELS: Record<string, string> = {
  geospatial: "Geospaziale",
  earth_observation_environment: "Osservazione della Terra e ambiente",
  meteorological: "Meteorologici",
  statistics: "Statistici",
  companies_ownership: "Imprese e proprietà",
  mobility: "Mobilità",
};
const ENTITY_TYPE_LABEL: Record<string, string> = {
  comune: "comune",
  regione: "Regione",
  provincia: "Provincia",
  ente: "ente",
};

type Portfolio = {
  count: number;
  pct_hvd: number | null;
  pct_open_license: number | null;
  avg_freshness_days: number | null;
  avg_stars: number | null;
  avg_reuse: number | null;
};

type FaseId = "portale" | "analisi" | "punteggio" | "salvataggio";

type Stato =
  | { fase: "idle" }
  | { fase: "loading"; corrente: FaseId | null; fatte: FaseId[]; nota: string | null }
  | { fase: "errore"; messaggio: string }
  | { fase: "risultato"; scorecard: Scorecard };

// Ordine + etichette delle fasi dell'assessment (in linea con gli eventi
// emessi da /maturity/assess/stream).
const FASI: { id: FaseId; label: string }[] = [
  { id: "portale", label: "Raccolta dei dataset dal portale" },
  { id: "analisi", label: "Analisi semantica e domanda di riuso" },
  { id: "punteggio", label: "Calcolo dei punteggi (4 dimensioni ODM)" },
  { id: "salvataggio", label: "Salvataggio e scorecard" },
];

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
const DIM_DESC: Record<string, string> = {
  policy:
    "governance del dato — licenze aperte e metadati DCAT-AP_IT, la base che rende i dataset legalmente riutilizzabili e trovabili sul catalogo nazionale",
  portal:
    "presenza sul portale — quanti dataset l'ente espone e quanto sono ben indicizzati e accessibili",
  quality:
    "qualità dei dataset — formati aperti e machine-readable, aggiornamento regolare e completezza: quanto i dati sono davvero usabili",
  impact:
    "impatto e riuso — dataset ad alto valore (HVD) e domanda di riuso soddisfatta: quanto i dati si trasformano in servizi e valore per il territorio",
};
const RANK_LEAD = ["La leva principale", "Seconda priorità", "Terzo intervento", "Infine"];
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

/** Cattura un nodo e lo scarica come PNG (usato dal pulsante "Esporta immagine" dei grafici). */
async function exportNodePng(node: HTMLElement | null, slug: string) {
  if (!node) return;
  const data = await captureNode(node);
  if (!data) return;
  const a = document.createElement("a");
  a.href = data;
  a.download = `${slug}.png`;
  a.click();
}

/**
 * Cornice di un grafico: titolo + pulsante "Esporta immagine" (cattura solo il
 * grafico, non il pulsante) + un'eventuale nota esplicativa sopra il grafico.
 */
function ChartFrame({
  title,
  fileSlug,
  hint,
  children,
}: {
  title: string;
  fileSlug: string;
  hint?: React.ReactNode;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  return (
    <div>
      <div className="d-flex align-items-center justify-content-between gap-2 mb-1">
        <h3 className="h6 text-slate-500 mb-0">{title}</h3>
        <button
          type="button"
          className="btn btn-link btn-sm p-0 text-decoration-none"
          style={{ fontSize: 12 }}
          onClick={() => exportNodePng(ref.current, fileSlug)}
        >
          ⬇ Esporta immagine
        </button>
      </div>
      {hint}
      <div ref={ref} className="bg-white" style={{ padding: 4 }}>
        {children}
      </div>
    </div>
  );
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
    setStato({ fase: "loading", corrente: "portale", fatte: [], nota: null });
    setPortfolio(null);
    try {
      const token = await getToken();
      const resp = await apiFetch("/maturity/assess/stream", {
        method: "POST",
        token,
        body: JSON.stringify({
          entity: name,
          comune_nome: name,
          istat_code: istat.trim() || undefined,
        }),
      });
      if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`);

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let scorecard: Scorecard | null = null;
      const fatte: FaseId[] = [];

      // Legge l'NDJSON riga per riga aggiornando il feed di stato.
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          let ev: Record<string, unknown>;
          try {
            ev = JSON.parse(line);
          } catch {
            continue;
          }
          if (ev.event === "result") {
            scorecard = ev.scorecard as Scorecard;
          } else if (ev.event === "error") {
            throw new Error(String(ev.message ?? "Errore"));
          } else if (ev.event === "status") {
            const phase = ev.phase as FaseId;
            if (ev.state === "end") {
              if (!fatte.includes(phase)) fatte.push(phase);
            }
            const idx = FASI.findIndex((f) => f.id === phase);
            const next = FASI[idx + 1]?.id ?? null;
            const corrente: FaseId | null =
              ev.state === "start" ? phase : next && !fatte.includes(next) ? next : null;
            const nota =
              phase === "portale" && ev.state === "end" && typeof ev.n_datasets === "number"
                ? `${ev.n_datasets} dataset trovati`
                : null;
            setStato({ fase: "loading", corrente, fatte: [...fatte], nota });
          }
          // heartbeat / cache: nessun aggiornamento di fase richiesto.
        }
      }

      if (!scorecard) throw new Error("Nessun risultato ricevuto.");
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
    <div className="container py-4">
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

      {stato.fase === "loading" ? <AssessProgress stato={stato} /> : null}

      {stato.fase === "errore" ? (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-700" style={{ fontSize: 14 }}>
          Errore nell&apos;assessment: {stato.messaggio}
        </div>
      ) : null}

      {stato.fase === "risultato" ? (
        <ScorecardView scorecard={stato.scorecard} portfolio={portfolio} />
      ) : null}
    </div>
  );
}

/** Feed di avanzamento granulare durante la valutazione (no stato di "freeze"). */
function AssessProgress({
  stato,
}: {
  stato: { fase: "loading"; corrente: FaseId | null; fatte: FaseId[]; nota: string | null };
}) {
  return (
    <div className="rounded border bg-bg-muted p-3" style={{ maxWidth: 560 }} aria-live="polite">
      <p className="mb-2" style={{ fontSize: 14, fontWeight: 600 }}>
        Valutazione in corso…
      </p>
      <ul className="list-unstyled d-flex flex-column gap-2 mb-0">
        {FASI.map((f) => {
          const done = stato.fatte.includes(f.id);
          const active = stato.corrente === f.id;
          const color = done ? "#059669" : active ? "#2563eb" : "#94a3b8";
          return (
            <li key={f.id} className="d-flex align-items-center gap-2" style={{ fontSize: 14 }}>
              <span
                aria-hidden="true"
                className={active ? "spinner-border spinner-border-sm" : ""}
                style={
                  active
                    ? { width: 14, height: 14, color }
                    : {
                        width: 14,
                        height: 14,
                        borderRadius: "50%",
                        background: done ? color : "transparent",
                        border: done ? "none" : `2px solid ${color}`,
                        display: "inline-block",
                      }
                }
              />
              <span style={{ color: active || done ? "#0f172a" : "#94a3b8" }}>
                {f.label}
                {done && f.id === "portale" && stato.nota ? (
                  <span className="text-slate-500"> · {stato.nota}</span>
                ) : null}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function GuidaView({ guida }: { guida: Guida }) {
  return (
    <div className="rounded border border-primary bg-bg-muted p-4">
      {/* Disclaimer: punteggio 0 / nessun dataset → non è un giudizio, è il punto di
          partenza. Link alla guida operativa completa. */}
      <div className="alert alert-warning mb-3" role="note">
        <strong>Nessun open data valutabile per questo ente.</strong> Il punteggio resta a 0 perché
        sul catalogo nazionale non risultano (ancora) dataset: non è un giudizio negativo, è il punto
        di partenza tipico. Ecco come avviare la pubblicazione — la{" "}
        <Link href={GUIDA_PATH} className="alert-link">
          guida completa passo passo
        </Link>{" "}
        spiega ogni passaggio in dettaglio.
      </div>
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
        <p className="text-slate-500 fst-italic mt-3 mb-2" style={{ fontSize: 12 }}>{guida.nota}</p>
      ) : null}
      <Link href={GUIDA_PATH} className="btn btn-primary btn-sm mt-2">
        Apri la guida completa per avviare gli open data
      </Link>
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

/** Spiegazione per dimensione: cosa misura + sotto-metriche (dalla più debole). */
function DimensionBreakdownView({ breakdown }: { breakdown: DimensionBreakdown[] }) {
  return (
    <div>
      <h3 className="h6 text-slate-500">Come si legge il punteggio</h3>
      <p className="text-slate-500 mb-3" style={{ fontSize: 13 }}>
        Ogni dimensione è la media di alcune sotto-metriche. Qui sotto cosa misura e quali
        voci la trainano in basso (le più deboli per prime).
      </p>
      <div className="row g-3">
        {breakdown.map((b) => (
          <div className="col-md-6" key={b.dimension}>
            <div className="rounded border p-3 h-100">
              <div className="d-flex align-items-baseline justify-content-between mb-1">
                <strong style={{ fontSize: 14 }}>{b.label}</strong>
                <span className="badge bg-primary">{Math.round(b.score)}/100</span>
              </div>
              <p className="text-slate-600 mb-2" style={{ fontSize: 12 }}>{b.description}</p>
              <ul className="list-unstyled d-flex flex-column gap-1 mb-0">
                {b.drivers.map((d) => {
                  const weak = b.weakest.includes(d.label);
                  return (
                    <li key={d.label} className="d-flex align-items-center gap-2" style={{ fontSize: 12 }}>
                      <span style={{ flex: 1, color: weak ? "#b45309" : "#475569" }}>
                        {weak ? "⚠ " : ""}
                        {d.label}
                      </span>
                      <div style={{ width: 90, height: 6, background: "#eef0f3", borderRadius: 3 }}>
                        <div
                          style={{
                            width: `${Math.round(d.value)}%`,
                            height: "100%",
                            borderRadius: 3,
                            background: d.value < 40 ? "#dc2626" : d.value < 70 ? "#d97706" : "#059669",
                          }}
                        />
                      </div>
                      <span className="text-slate-400" style={{ width: 30, textAlign: "right" }}>
                        {Math.round(d.value)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Copertura tematica: settori coperti vs. collection ottimale + categorie HVD. */
function CoverageView({ coverage }: { coverage: Coverage }) {
  const etLabel = ENTITY_TYPE_LABEL[coverage.entity_type] ?? coverage.entity_type;
  const core = coverage.sectors.filter((s) => s.is_core);
  const extra = coverage.sectors.filter((s) => !s.is_core && s.present);
  const maxN = Math.max(1, ...core.map((s) => s.n_datasets));
  return (
    <div>
      <h3 className="h6 text-slate-500">Copertura per settore</h3>
      <p className="text-slate-500 mb-3" style={{ fontSize: 13 }}>
        Quanto il catalogo copre i settori attesi per un ente di tipo{" "}
        <strong>{etLabel}</strong>: copertura{" "}
        <strong>{Math.round(coverage.coverage_score)}%</strong> dei settori chiave
        ({core.filter((s) => s.present).length}/{core.length}).
      </p>
      <div className="row g-3">
        {/* Settori core: barra con conteggio, evidenza sugli assenti */}
        <div className="col-lg-7">
          <ul className="list-unstyled d-flex flex-column gap-2 mb-0">
            {core.map((s) => (
              <li key={s.code} className="d-flex align-items-center gap-2" style={{ fontSize: 13 }}>
                <span style={{ flex: 1, color: s.present ? "#0f172a" : "#b45309" }}>
                  {s.present ? "" : "⚠ "}
                  {s.label}
                </span>
                <div style={{ width: 120, height: 8, background: "#eef0f3", borderRadius: 4 }}>
                  <div
                    style={{
                      width: `${Math.round((s.n_datasets / maxN) * 100)}%`,
                      height: "100%",
                      borderRadius: 4,
                      background: s.present ? "#2563eb" : "transparent",
                    }}
                  />
                </div>
                <span className="text-slate-500" style={{ width: 64, textAlign: "right" }}>
                  {s.n_datasets} dataset
                </span>
              </li>
            ))}
          </ul>
          {extra.length ? (
            <p className="text-slate-400 mt-2 mb-0" style={{ fontSize: 12 }}>
              Altri settori presenti: {extra.map((s) => s.label).join(", ")}.
            </p>
          ) : null}
        </div>

        {/* Categorie HVD (Reg. UE 2023/138) */}
        <div className="col-lg-5">
          <div className="text-slate-500 mb-1" style={{ fontSize: 12, fontWeight: 600 }}>
            Dati ad elevato valore (HVD) · {coverage.hvd_present.length}/6
          </div>
          <div className="d-flex flex-wrap gap-1">
            {coverage.hvd_present.map((h) => (
              <span key={h} className="badge" style={{ background: "#059669", color: "white", fontSize: 11 }}>
                ✓ {HVD_LABELS[h] ?? h}
              </span>
            ))}
            {coverage.hvd_missing.map((h) => (
              <span key={h} className="badge" style={{ background: "#f1f5f9", color: "#64748b", fontSize: 11 }}>
                {HVD_LABELS[h] ?? h}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Cosa manca per una collection ottimale */}
      {coverage.missing_core.length ? (
        <div className="alert alert-warning mt-3 mb-0" role="note">
          <strong>Cosa manca per una collection ottimale.</strong> Per il ruolo di questo ente
          mancano dataset in {coverage.missing_core.length} settori chiave, in ordine di priorità:
          <ol className="mb-0 mt-1" style={{ fontSize: 13 }}>
            {coverage.missing_core.map((s) => (
              <li key={s.code}>{s.label}</li>
            ))}
          </ol>
        </div>
      ) : (
        <p className="text-success mt-2 mb-0" style={{ fontSize: 13 }}>
          Tutti i settori chiave per questo tipo di ente sono coperti.
        </p>
      )}
    </div>
  );
}

/** Lista di azioni gap (quick-win o strategiche) con badge gravità + flag collo di bottiglia. */
function AzioniList({ azioni }: { azioni: AzioneGap[] }) {
  return (
    <ul className="list-unstyled d-flex flex-column gap-2 mb-0">
      {azioni.map((a) => (
        <li key={a.code} className="d-flex align-items-start gap-2" style={{ fontSize: 13 }}>
          <span
            className="badge rounded-pill flex-shrink-0"
            style={{ backgroundColor: SEVERITY_COLOR[a.severity] ?? "#64748b", color: "white" }}
          >
            {a.severity}
          </span>
          <span>
            {a.messaggio}
            <span className="text-slate-400"> · {a.dimension_label}</span>
            {a.sul_collo_di_bottiglia ? (
              <span className="badge bg-warning-subtle text-warning-emphasis ms-1 align-middle" style={{ fontSize: 11 }}>
                ⚑ collo di bottiglia
              </span>
            ) : null}
          </span>
        </li>
      ))}
    </ul>
  );
}

/**
 * Gap analysis (#50): "le mosse che contano di più". Consuma il campo `gap`
 * autoritativo del backend — prossimo livello, collo di bottiglia e azioni
 * divise tra quick-win (correzioni rapide sui dataset esistenti) e strategiche
 * (richiedono di pubblicare nuovi dati). Complementare al radar "Come migliorare".
 */
function GapRoadmapView({ gap }: { gap: Gap }) {
  if (gap.quick_win.length === 0 && gap.strategiche.length === 0) return null;
  return (
    <div>
      <h3 className="h6 text-slate-500">Le mosse che contano di più</h3>
      <p className="text-slate-600 mb-3" style={{ fontSize: 13 }}>
        {gap.prossimo_livello && gap.punti_al_prossimo != null ? (
          <>
            Da <strong>{gap.livello_attuale}</strong> a{" "}
            <strong>{gap.prossimo_livello}</strong> mancano{" "}
            <strong>{Math.round(gap.punti_al_prossimo)} punti</strong>. Il{" "}
            <strong>collo di bottiglia</strong> è <strong>{gap.collo_di_bottiglia_label}</strong>:
            è lì che conviene concentrare gli interventi (segnalati con ⚑).
          </>
        ) : (
          <>
            Livello massimo (<strong>{gap.livello_attuale}</strong>). Il margine residuo più
            ampio è su <strong>{gap.collo_di_bottiglia_label}</strong>.
          </>
        )}
      </p>
      <div className="row g-3">
        <div className="col-md-6">
          <div className="rounded border p-3 h-100">
            <div className="fw-semibold mb-1" style={{ fontSize: 14 }}>
              <span aria-hidden>⚡ </span>Facili e rapide
            </div>
            <p className="text-slate-500 mb-2" style={{ fontSize: 12 }}>
              Si correggono sui dataset già pubblicati: licenza, metadati, formato, aggiornamento.
            </p>
            {gap.quick_win.length ? (
              <AzioniList azioni={gap.quick_win} />
            ) : (
              <p className="text-slate-500 mb-0" style={{ fontSize: 13 }}>
                Nessuna correzione rapida in sospeso.
              </p>
            )}
          </div>
        </div>
        <div className="col-md-6">
          <div className="rounded border p-3 h-100">
            <div className="fw-semibold mb-1" style={{ fontSize: 14 }}>
              <span aria-hidden>🎯 </span>Strategiche
            </div>
            <p className="text-slate-500 mb-2" style={{ fontSize: 12 }}>
              Richiedono di pubblicare nuovi dati o coprire settori e dataset ad alto valore.
            </p>
            {gap.strategiche.length ? (
              <AzioniList azioni={gap.strategiche} />
            ) : (
              <p className="text-slate-500 mb-0" style={{ fontSize: 13 }}>
                Nessun intervento strategico in sospeso.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Confronto con enti simili (#50): dove si posiziona l'ente nel cluster (stesso
 * tipo) e come si confronta, dimensione per dimensione, con la mediana dei pari.
 */
function PeerComparisonView({
  pc,
  dimensions,
  entityName,
  fileSlug,
}: {
  pc: PeerComparison;
  dimensions: Dimensions;
  entityName: string;
  fileSlug: string;
}) {
  const hint = (
    <p className="text-slate-600 mb-3" style={{ fontSize: 13 }}>
      Tra i <strong>{pc.count} {pc.cluster_label}</strong> valutati,{" "}
      <strong>{entityName}</strong>
      {pc.rank != null ? (
        <>
          {" "}è al <strong>{pc.rank}° posto</strong>
          {pc.better_than_pct != null ? (
            <> — fa meglio del <strong>{pc.better_than_pct}%</strong> degli enti simili</>
          ) : null}
          . Mediana del gruppo: <strong>{Math.round(pc.median_overall)}/100</strong>.
        </>
      ) : (
        <>. Mediana del gruppo: <strong>{Math.round(pc.median_overall)}/100</strong>.</>
      )}
    </p>
  );
  return (
    <ChartFrame title="Confronto con enti simili" fileSlug={fileSlug} hint={hint}>
      <ul className="list-unstyled d-flex flex-column gap-2 mb-0" style={{ maxWidth: 640 }}>
        {DIM_KEYS.map((k) => {
          const mine = dimensions[k];
          const med = pc.median_dimensions[k];
          const delta = Math.round(mine - med);
          const deltaColor = delta > 0 ? "#059669" : delta < 0 ? "#dc2626" : "#64748b";
          return (
            <li key={k} className="d-flex align-items-center gap-2" style={{ fontSize: 13 }}>
              <span style={{ width: 80, color: "#475569" }}>{DIM_LABEL[k]}</span>
              {/* Barra: punteggio dell'ente, con tacca sulla mediana del cluster */}
              <div style={{ position: "relative", flex: 1, height: 10, background: "#eef0f3", borderRadius: 5 }}>
                <div
                  style={{
                    width: `${Math.round(mine)}%`,
                    height: "100%",
                    borderRadius: 5,
                    background: delta >= 0 ? "#2563eb" : "#d97706",
                  }}
                />
                <span
                  title={`Mediana ${pc.cluster_label}: ${Math.round(med)}`}
                  style={{
                    position: "absolute",
                    left: `calc(${Math.round(med)}% - 1px)`,
                    top: -3,
                    width: 2,
                    height: 16,
                    background: "#0f172a",
                  }}
                />
              </div>
              <span style={{ width: 36, textAlign: "right", color: "#0f172a" }}>{Math.round(mine)}</span>
              <span style={{ width: 56, textAlign: "right", color: deltaColor, fontVariantNumeric: "tabular-nums" }}>
                {delta > 0 ? `+${delta}` : delta} vs
              </span>
              <span style={{ width: 24, textAlign: "left", color: "#64748b" }}>{Math.round(med)}</span>
            </li>
          );
        })}
      </ul>
      <p className="text-slate-400 mt-2 mb-0" style={{ fontSize: 11 }}>
        La tacca verticale è la mediana degli enti dello stesso tipo; il numero a destra il loro valore.
      </p>
    </ChartFrame>
  );
}

/** "Come migliorare": leve ordinate per impatto sul punteggio complessivo. */
function ImproveView({
  leve,
  nextLevel,
}: {
  leve: ReturnType<typeof buildImprovements>["leve"];
  nextLevel: ReturnType<typeof buildImprovements>["nextLevel"];
}) {
  return (
    <div>
      <h3 className="h6 text-slate-500">Come migliorare</h3>
      {nextLevel ? (
        <p className="mb-2" style={{ fontSize: 14 }}>
          Mancano <strong>{Math.round(nextLevel.gap)} punti</strong> per raggiungere il livello{" "}
          <strong>{nextLevel.name}</strong>. Gli interventi a maggiore impatto sul punteggio
          complessivo:
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
        <ul className="list-unstyled d-flex flex-column gap-3 mb-0">
          {leve.map((l, i) => (
            <li key={l.key}>
              <div className="d-flex align-items-baseline gap-2 flex-wrap mb-1">
                <span className="badge bg-primary">fino a +{Math.round(l.potential)} pti</span>
                <strong style={{ fontSize: 14 }}>
                  {RANK_LEAD[i] ?? "Inoltre"}: {l.label}
                </strong>
                <span className="text-slate-400" style={{ fontSize: 12 }}>
                  oggi {Math.round(l.score)}/100
                </span>
              </div>
              <p className="text-slate-600 mb-1" style={{ fontSize: 13 }}>
                Riguarda la {DIM_DESC[l.key]}. Portarla verso 100 vale fino a{" "}
                {Math.round(l.potential)} punti sul punteggio complessivo.
              </p>
              {l.recs.length ? (
                <ul className="text-slate-600 mb-0" style={{ fontSize: 13, paddingLeft: 20 }}>
                  {l.recs.map((r) => (
                    <li key={r.code}>{r.message}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-slate-500 mb-0" style={{ fontSize: 13 }}>
                  Nessun intervento puntuale rilevato qui: si tratta di consolidare e mantenere i
                  risultati già raggiunti su questa dimensione.
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
      <p className="text-slate-400 mt-2 mb-0" style={{ fontSize: 11 }}>
        Il potenziale è il guadagno massimo sul punteggio complessivo portando la dimensione a 100
        (pesata secondo il modello ODM).
      </p>
    </div>
  );
}

function ScorecardView({ scorecard, portfolio }: { scorecard: Scorecard; portfolio: Portfolio | null }) {
  const { getToken } = useAuth();
  const radarRef = useRef<HTMLDivElement>(null);
  const slug = (scorecard.entity.name || "ente").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  const insufficient = scorecard.insufficient_data && scorecard.guida;
  const { dimensions, level, overall } = scorecard;
  const radarData = DIM_KEYS.map((k) => ({ dim: DIM_LABEL[k], value: dimensions[k] }));
  const levelColor = LEVEL_COLOR[level] ?? "#334155";
  const { leve, nextLevel } = buildImprovements(scorecard);
  const [esportandoMd, setEsportandoMd] = useState(false);

  async function exportPdf() {
    const radarPng = radarRef.current ? (await captureNode(radarRef.current)) ?? undefined : undefined;
    await downloadScorecardPdf(scorecard, { radarPng, portfolio, improvements: { leve, nextLevel } });
  }

  // Export Markdown embeddabile (riepilogo + link, o disclaimer + guida quando i
  // dati mancano): è il backend a renderizzarlo — un solo punto di verità.
  async function exportMarkdown() {
    setEsportandoMd(true);
    try {
      const token = await getToken();
      const res = await apiFetch(`/maturity/entities/${scorecard.entity.id}/scorecard.md`, { token });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const md = await res.text();
      const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `maturita-${slug || "ente"}.md`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } finally {
      setEsportandoMd(false);
    }
  }

  return (
    <div className="d-flex flex-column gap-3">
      {/* Toolbar export */}
      <div className="d-flex gap-2">
        <button type="button" className="btn btn-primary btn-sm" onClick={exportPdf}>
          Esporta PDF
        </button>
        <button
          type="button"
          className="btn btn-outline-primary btn-sm"
          onClick={exportMarkdown}
          disabled={esportandoMd}
          title="Scarica un riepilogo Markdown incorporabile in siti esterni"
        >
          {esportandoMd ? "Generazione…" : "Esporta Markdown"}
        </button>
      </div>

      <div className="d-flex flex-column gap-4 bg-white p-3 rounded">
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
            {/* GRAFICI in alto: radar 4 dimensioni + confronto con enti simili */}
            <div className="row g-4">
              <div className="col-lg-6">
                <ChartFrame title="Dimensioni" fileSlug={`maturita-${slug || "ente"}-dimensioni`}>
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
                </ChartFrame>
              </div>

              {/* Confronto con enti simili (#50): posizione nel cluster + per dimensione */}
              {scorecard.peer_comparison ? (
                <div className="col-lg-6">
                  <PeerComparisonView
                    pc={scorecard.peer_comparison}
                    dimensions={scorecard.dimensions}
                    entityName={scorecard.entity.name}
                    fileSlug={`maturita-${slug || "ente"}-confronto`}
                  />
                </div>
              ) : null}
            </div>

            {/* CARD: mosse, spiegazione punteggio, copertura, valore */}
            {/* Gap analysis (#50): mosse facili vs strategiche, collo di bottiglia */}
            {scorecard.gap ? <GapRoadmapView gap={scorecard.gap} /> : null}

            {/* Spiegazione per dimensione (Fase B): cosa misura ogni punteggio */}
            {scorecard.dimension_breakdown && scorecard.dimension_breakdown.length ? (
              <DimensionBreakdownView breakdown={scorecard.dimension_breakdown} />
            ) : null}

            {/* Copertura tematica/settoriale (Fase A): collection ottimale */}
            {scorecard.coverage ? <CoverageView coverage={scorecard.coverage} /> : null}

            {/* Valore del patrimonio (unito alla maturità) */}
            {portfolio && portfolio.count > 0 ? <ValoreCard pf={portfolio} /> : null}

            {/* IN BASSO: come migliorare (leve) + raccomandazioni su come colmarle */}
            <ImproveView leve={leve} nextLevel={nextLevel} />

            {/* Raccomandazioni complete: ogni gap rimanda alla sezione della guida che lo risolve */}
            <div>
              <h3 className="h6 text-slate-500">Raccomandazioni e come colmarle</h3>
              {scorecard.recommendations.length === 0 ? (
                <p className="text-slate-500" style={{ fontSize: 14 }}>
                  Nessuna raccomandazione: l&apos;ente soddisfa le soglie principali.
                </p>
              ) : (
                <ul className="list-unstyled d-flex flex-column gap-3">
                  {scorecard.recommendations.map((r) => {
                    const g = recGuide(r.code);
                    return (
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
                          {g ? (
                            <>
                              <div className="text-slate-600 mt-1" style={{ fontSize: 13 }}>
                                {g.consiglio}
                              </div>
                              <Link
                                href={guideHref(g.anchor)}
                                className="d-inline-block mt-1"
                                style={{ fontSize: 13 }}
                              >
                                Guida: {g.sezione} →
                              </Link>
                            </>
                          ) : null}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* Gap di domanda di riuso (anello valore⇄maturità): penalizzano l'Impatto */}
            {scorecard.unmet_reuse_demand && scorecard.unmet_reuse_demand.count > 0 ? (
              <div>
                <h3 className="h6 text-slate-500">Domanda di riuso non soddisfatta</h3>
                <p className="text-slate-600 mb-2" style={{ fontSize: 13 }}>
                  Le analisi di Territorio segnalano dati richiesti ma non ancora pubblicati: questi gap
                  riducono l&apos;Impatto. {GAP_GUIDE.consiglio}
                </p>
                <ul className="text-slate-600" style={{ fontSize: 13, paddingLeft: 20 }}>
                  {scorecard.unmet_reuse_demand.items.map((it, i) => (
                    <li key={i}>{it}</li>
                  ))}
                </ul>
                <Link href={guideHref(GAP_GUIDE.anchor)} style={{ fontSize: 13 }}>
                  Guida: {GAP_GUIDE.sezione} →
                </Link>
              </div>
            ) : null}
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
